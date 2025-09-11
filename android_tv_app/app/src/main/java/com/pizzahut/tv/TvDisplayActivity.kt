package com.pizzahut.tv

import android.graphics.Color
import android.os.Bundle
import android.widget.ImageView
import android.widget.VideoView // legacy kept until fully removed
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.pizzahut.tv.api.ApiClient
import com.pizzahut.tv.databinding.ActivityTvDisplayBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import android.util.LruCache
import android.graphics.BitmapFactory
import android.graphics.drawable.AnimatedImageDrawable
import android.graphics.ImageDecoder
import android.net.Uri
import android.view.KeyEvent
import androidx.activity.OnBackPressedCallback
import android.widget.TextView
import android.content.Intent
import java.io.File
import java.util.Date
import java.util.Calendar
import java.text.SimpleDateFormat
import java.util.Locale
import com.pizzahut.tv.api.HeartbeatReq
import android.util.Log
private const val TAG = "PHTV"

class TvDisplayActivity : AppCompatActivity() {
    // Made public so extension functions can access
    lateinit var binding: ActivityTvDisplayBinding
    // ExoPlayer instance (initialized lazily within playlist loop). Not private so extension function can access.
    var exoPlayer: com.google.android.exoplayer2.ExoPlayer? = null
    // Keep a reference to legacy VideoView so we can hide/stop it properly
    var legacyVideoView: VideoView? = null
    // Small persistent debug overlay
    var debugOverlay: TextView? = null
    // Manual controls hooks
    var manualNext: (() -> Unit)? = null
    var manualPrev: (() -> Unit)? = null
    private var heartbeatJob: Job? = null
    private var hbIndicator: TextView? = null
    // Periodic per-item OK ping so dashboard lights stay green while item is displayed
    private var itemOkPingJob: Job? = null
    // Reusable HTTP client used by ExoPlayer and media probes
    var mediaHttpClient: okhttp3.OkHttpClient? = null
    // Screen transform like web player: orientation 'vertical' rotates stage 90deg; rotation adds extra degrees
    var orientationMode: String = "default" // 'vertical' | 'horizontal' | 'default'
    var displayRotation: Int = 0 // 0|90|180|270
    // Developer toggle: allow sliced videos to play on emulator (default false)
    fun isEmuSliceVideoForced(): Boolean {
        // Default ON so emulator plays sliced videos unless explicitly turned OFF
        return try { getSharedPreferences("phtv_dev", MODE_PRIVATE).getBoolean("emu_slice_video_force", true) } catch (_: Exception) { true }
    }
    fun setEmuSliceVideoForced(on: Boolean) {
        try { getSharedPreferences("phtv_dev", MODE_PRIVATE).edit().putBoolean("emu_slice_video_force", on).apply() } catch (_: Exception) { }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    com.pizzahut.tv.api.PairCodeHolder.init(applicationContext)
    // Pick up any server override persisted from SetupActivity
    ApiClient.initFromPrefs(applicationContext)
        // If a pairCode was injected when launching this Activity, persist it immediately
        try {
            intent?.getStringExtra("pairCode")?.let { injected ->
                if (injected.isNotBlank()) {
                    val prefs = getSharedPreferences("phtv", MODE_PRIVATE)
                    prefs.edit().putString("pairCode", injected.trim()).apply()
                }
            }
        } catch (_: Exception) { }
        binding = ActivityTvDisplayBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.message.text = "Loading playlist..."

        // Create / attach image & video containers
        val imageView = ImageView(this).apply {
            setBackgroundColor(Color.BLACK)
            adjustViewBounds = true
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            // Match webplayer: fill and crop
            scaleType = ImageView.ScaleType.CENTER_CROP
        }
        // ExoPlayer-based video surface (replaces VideoView for faster start & caching)
    val playerView = com.google.android.exoplayer2.ui.StyledPlayerView(this).apply {
            setBackgroundColor(Color.BLACK)
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            useController = false
            visibility = ImageView.GONE
            // Ensure we can clip/crop slices: prefer TextureView and zoom to fill
            try {
                this.resizeMode = com.google.android.exoplayer2.ui.AspectRatioFrameLayout.RESIZE_MODE_ZOOM
            } catch (_: Exception) {}
            try {
                // 2 == SURFACE_TYPE_TEXTURE_VIEW in PlayerView
                val cls = com.google.android.exoplayer2.ui.PlayerView::class.java
                val m = cls.methods.firstOrNull { it.name == "setSurfaceType" && it.parameterTypes.size == 1 }
                m?.invoke(this, 2)
            } catch (_: Exception) { }
        }
    // Add media views behind the existing status message (index 0 => back)
    binding.root.addView(playerView, 0)
    binding.root.addView(imageView, 0)

        // Temporary overlay instructions to allow reconfiguration
        val overlay = TextView(this).apply {
            text = "Back = Change Screen  |  Menu = Full Setup"
            setTextColor(Color.WHITE)
            textSize = 14f
            setBackgroundColor(0x66000000)
            setPadding(24,12,24,12)
        }
        val overlayParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    binding.root.addView(overlay, overlayParams)
        overlay.postDelayed({ overlay.animate().alpha(0f).setDuration(600).withEndAction { binding.root.removeView(overlay) } }, 8000)

        // Persistent top-left debug overlay
        debugOverlay = TextView(this).apply {
            setTextColor(Color.GREEN)
            textSize = 12f
            setBackgroundColor(0x33000000)
            setPadding(16, 8, 16, 8)
        }
        val dbgParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        binding.root.addView(debugOverlay, dbgParams)
        // Show current base URL briefly to verify connection target
        try {
            val emuForce = if (isEmuSliceVideoForced()) "ON" else "OFF"
            debugOverlay?.text = ("Base: " + ApiClient.baseUrl + "\nEmuSliceVideo: " + emuForce).take(80)
            debugOverlay?.postDelayed({ debugOverlay?.text = "" }, 6000)
        } catch (_: Exception) {}

        // Small heartbeat indicator (top-right)
        hbIndicator = TextView(this).apply {
            text = "HB..."
            setTextColor(Color.YELLOW)
            textSize = 12f
            setBackgroundColor(0x33000000)
            setPadding(12, 6, 12, 6)
        }
        val hbParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        (hbParams as? ViewGroup.MarginLayoutParams)?.let { it.rightMargin = 16; it.topMargin = 8 }
        binding.root.addView(hbIndicator, hbParams)

    val prefs = getSharedPreferences("phtv", MODE_PRIVATE)
    val extraStore = intent.getStringExtra("storeId")?.trim().orEmpty()
    val savedStore = prefs.getString("storeId", null)?.trim().orEmpty()
    val storeId = if (extraStore.isNotEmpty()) extraStore else if (savedStore.isNotEmpty()) savedStore else "0000"
    val extraScreen = intent.getStringExtra("screenId")?.trim().orEmpty()
    val savedScreen = prefs.getString("screenId", null)?.trim().orEmpty()
    val screenId = if (extraScreen.isNotEmpty()) extraScreen else if (savedScreen.isNotEmpty()) savedScreen else "screen1"

    binding.message.text = "Store $storeId / Screen $screenId\nLoading playlist..."

        // Intercept system back using dispatcher (more reliable than onBackPressed override on some TV builds)
    onBackPressedDispatcher.addCallback(this, object: OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
        startActivity(Intent(this@TvDisplayActivity, ChangeScreenActivity::class.java))
        finish()
            }
        })

        // Kick off initial and periodic refresh & rotation
    startPlaylistLoop(storeId, screenId, imageView, playerView)
    startHeartbeatLoop(storeId, screenId)
    }

    // Apply rotation/scale similar to web tv_view/player: rotate 90 for vertical, then add displayRotation, and scale to fit when 90/270
    fun applyOrientationTransform() {
        try {
            val baseRot = if (orientationMode.equals("vertical", ignoreCase = true)) 90 else 0
            var total = ((baseRot + displayRotation) % 360 + 360) % 360
            val vw = resources.displayMetrics.widthPixels.coerceAtLeast(1)
            val vh = resources.displayMetrics.heightPixels.coerceAtLeast(1)
            var scale = 1f
            if (total % 180 == 90) {
                // When rotated, match shortest side vs longest to keep content fully visible
                val sx = vw.toFloat() / vh.toFloat()
                val sy = vh.toFloat() / vw.toFloat()
                scale = kotlin.math.max(0.01f, kotlin.math.min(5f, kotlin.math.min(sx, sy)))
            }
            // Apply to root container
            binding.root.pivotX = 0f; binding.root.pivotY = 0f
            binding.root.rotation = total.toFloat()
            binding.root.scaleX = scale
            binding.root.scaleY = scale
        } catch (_: Exception) { }
    }

    private fun launchSetupAndReset() {
        val prefs = getSharedPreferences("phtv", MODE_PRIVATE)
        prefs.edit().remove("storeId").remove("screenId").apply()
        startActivity(Intent(this, SetupActivity::class.java))
        finish()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        when (keyCode) {
            KeyEvent.KEYCODE_MENU -> { launchSetupAndReset(); return true }
            KeyEvent.KEYCODE_BACK -> { startActivity(Intent(this, ChangeScreenActivity::class.java)); finish(); return true }
            KeyEvent.KEYCODE_ESCAPE -> { startActivity(Intent(this, ChangeScreenActivity::class.java)); finish(); return true }
            // Manual controls for debugging rotation
            KeyEvent.KEYCODE_DPAD_RIGHT -> {
                try { manualNext?.invoke() } catch (_: Exception) {}
                return true
            }
            KeyEvent.KEYCODE_DPAD_LEFT -> {
                try { manualPrev?.invoke() } catch (_: Exception) {}
                return true
            }
        }
        return super.onKeyDown(keyCode, event)
    }

    // onBackPressed handled by dispatcher callback above

    override fun onKeyLongPress(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER) {
            launchSetupAndReset()
            return true
        }
        if (keyCode == KeyEvent.KEYCODE_DPAD_UP) {
            val newVal = !isEmuSliceVideoForced()
            setEmuSliceVideoForced(newVal)
            val msg = if (newVal) "Emu slice video: ON" else "Emu slice video: OFF"
            try {
                debugOverlay?.text = msg
                debugOverlay?.postDelayed({ debugOverlay?.text = "" }, 2500)
            } catch (_: Exception) {}
            return true
        }
        return super.onKeyLongPress(keyCode, event)
    }

    override fun onDestroy() {
    try { heartbeatJob?.cancel() } catch (_: Exception) {}
    heartbeatJob = null
        try { itemOkPingJob?.cancel() } catch (_: Exception) {}
        itemOkPingJob = null
        try {
            exoPlayer?.stop()
            exoPlayer?.clearMediaItems()
            exoPlayer?.release()
        } catch (_: Exception) {}
        exoPlayer = null
        legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
        super.onDestroy()
    }

    // Class-level helpers to manage per-item OK ping lifecycle
    fun cancelItemOkPing() {
        try { itemOkPingJob?.cancel() } catch (_: Exception) {}
        itemOkPingJob = null
    }
    fun startItemOkPing(storeId: String, screenId: String, file: String?, itemId: String?) {
        if (file.isNullOrBlank()) return
        cancelItemOkPing()
        itemOkPingJob = lifecycleScope.launch(Dispatchers.IO) {
            // Small initial delay to avoid racing immediate OK
            try { delay(20_000) } catch (_: Exception) { return@launch }
            while (isActive) {
                try {
                    ApiClient.service.postClientEvent(
                        com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)
                    )
                } catch (_: Exception) {}
                try { delay(25_000) } catch (_: Exception) { break }
            }
        }
    }

    private fun startHeartbeatLoop(storeId: String, screenId: String) {
        heartbeatJob?.cancel()
        heartbeatJob = lifecycleScope.launch(Dispatchers.IO) {
            while (isActive) {
                try {
                    ApiClient.service.sendHeartbeat(HeartbeatReq(storeId = storeId, screenId = screenId))
                    withContext(Dispatchers.Main) {
                        hbIndicator?.text = "HB ok"
                        hbIndicator?.setTextColor(0xFF00FF00.toInt())
                    }
                } catch (_: Exception) {
                    withContext(Dispatchers.Main) {
                        hbIndicator?.text = "HB fail"
                        hbIndicator?.setTextColor(0xFFFFFF00.toInt())
                    }
                }
                try { delay(30_000) } catch (_: Exception) { break }
            }
        }
    }

    // Mirror server-side scheduling rules so device respects dashboard schedule windows/days
    fun filterBySchedule(items: List<com.pizzahut.tv.api.PlaylistItem>): List<com.pizzahut.tv.api.PlaylistItem> {
        if (items.isEmpty()) return emptyList()
    val now = Date()
    val cal = Calendar.getInstance().apply { time = now }
    val wd = when (cal.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY -> "mon"
            Calendar.TUESDAY -> "tue"
            Calendar.WEDNESDAY -> "wed"
            Calendar.THURSDAY -> "thu"
            Calendar.FRIDAY -> "fri"
            Calendar.SATURDAY -> "sat"
            else -> "sun"
        }

        fun parseTimeString(v: String?): Date? {
            if (v.isNullOrBlank()) return null
            return try {
                val isTimeOnly = v.length <= 8 && ":" in v && !v.contains("-")
                if (isTimeOnly) {
                    val parts = v.split(":").map { it.toIntOrNull() ?: 0 }
                    val c = Calendar.getInstance().apply { time = now }
                    c.set(Calendar.HOUR_OF_DAY, parts.getOrNull(0) ?: 0)
                    c.set(Calendar.MINUTE, parts.getOrNull(1) ?: 0)
                    c.set(Calendar.SECOND, parts.getOrNull(2) ?: 0)
                    c.set(Calendar.MILLISECOND, 0)
                    return c.time
                }
                if (v.length == 10 && v[4] == '-' && v[7] == '-') {
                    val d = SimpleDateFormat("yyyy-MM-dd", Locale.US).parse(v)
                    val c = Calendar.getInstance().apply { time = d!! }
                    c.set(Calendar.HOUR_OF_DAY, 0); c.set(Calendar.MINUTE, 0); c.set(Calendar.SECOND, 0); c.set(Calendar.MILLISECOND, 0)
                    return c.time
                }
                val fmts = arrayOf("yyyy-MM-dd'T'HH:mm:ss","yyyy-MM-dd HH:mm:ss","yyyy-MM-dd'T'HH:mm","yyyy-MM-dd HH:mm")
                var out: Date? = null
                for (f in fmts) {
                    try { out = SimpleDateFormat(f, Locale.US).parse(v); if (out != null) break } catch (_: Exception) {}
                }
                out
            } catch (_: Exception) { null }
        }

    fun intervalActive(s: String?, e: String?, days: List<String>?): Boolean {
            if ((s.isNullOrBlank()) && (e.isNullOrBlank())) return false
            fun isTimeOnly(v: String?): Boolean = v != null && v.length <= 8 && ":" in v && !v.contains("-")
            fun isDateOnly(v: String?): Boolean = v != null && v.length == 10 && v[4] == '-' && v[7] == '-'
            fun isAbsolute(v: String?): Boolean = v != null && (v.contains('T') || isDateOnly(v))
            val hasAbsolute = isAbsolute(s) || isAbsolute(e)
            // If using absolute dates, ignore weekday gating as it's a one-off interval
            if (!hasAbsolute && !days.isNullOrEmpty()) {
                val norm = days.map { it.lowercase(Locale.US).take(3) }
                if (!norm.contains(wd)) return false
            }
            val ws = parseTimeString(s)
            var we = parseTimeString(e)
            // Normalize date-only single-sided windows to same-day boundaries
            if (!e.isNullOrBlank() && isDateOnly(e) && we != null) {
                val c = Calendar.getInstance().apply { time = we }
                c.set(Calendar.HOUR_OF_DAY, 23); c.set(Calendar.MINUTE, 59); c.set(Calendar.SECOND, 59); c.set(Calendar.MILLISECOND, 999)
                we = c.time
            }
            if (!s.isNullOrBlank() && isDateOnly(s) && e.isNullOrBlank() && ws != null) {
                // start is date-only with no end -> end of same day
                val c = Calendar.getInstance().apply { time = ws }
                c.set(Calendar.HOUR_OF_DAY, 23); c.set(Calendar.MINUTE, 59); c.set(Calendar.SECOND, 59); c.set(Calendar.MILLISECOND, 999)
                we = c.time
            }
            if (!e.isNullOrBlank() && isDateOnly(e) && s.isNullOrBlank() && we != null) {
                // end is date-only with no start -> start of same day
                val c = Calendar.getInstance().apply { time = we }
                c.set(Calendar.HOUR_OF_DAY, 0); c.set(Calendar.MINUTE, 0); c.set(Calendar.SECOND, 0); c.set(Calendar.MILLISECOND, 0)
                // reuse ws var
                @Suppress("NAME_SHADOWING")
                val wsLocal = c.time
                return if (now.after(wsLocal) && now.before(we) || now == wsLocal || now == we) true else false
            }
            val timeOnly = (isTimeOnly(s) || isTimeOnly(e))
            if (ws != null && we != null) {
                if (we.before(ws)) {
                    if (!timeOnly) {
                        val c = Calendar.getInstance().apply { time = we }
                        c.add(Calendar.DATE, 1)
                        val wePlus = c.time
                        return (now.after(ws) || now == ws) && (now.before(wePlus) || now == wePlus)
                    }
                    return now.after(ws) || now.before(we)
                }
                return (now.after(ws) || now == ws) && (now.before(we) || now == we)
            }
            if (ws != null && now.before(ws)) return false
            if (we != null && now.after(we)) return false
            return true
        }

        val enabled = items.filter { it.enabled != false }
        val scheduled = mutableListOf<com.pizzahut.tv.api.PlaylistItem>()
        val fallback = mutableListOf<com.pizzahut.tv.api.PlaylistItem>()
        for (it in enabled) {
            val windows = it.schedule ?: emptyList()
            var inWin = false
            if (windows.isNotEmpty()) {
                for (w in windows) { if (intervalActive(w.start, w.end, w.days)) { inWin = true; break } }
            }
            if (inWin) { scheduled.add(it); continue }
            if (!it.start.isNullOrBlank() || !it.end.isNullOrBlank()) {
                // Treat non-restrictive time gating as "no schedule" so it doesn't suppress others.
                fun isTimeOnly(v: String?): Boolean = v != null && v.length <= 8 && ":" in v && !v.contains("-")
                val s = it.start?.trim()
                val e = it.end?.trim()
                val days = it.days ?: emptyList()
                val zeroStartNoEnd = (s != null && isTimeOnly(s) && (s == "0:0:0" || s == "00:00" || s == "00:00:00") && (e.isNullOrBlank())) && days.isEmpty()
                val endAtDayMaxNoStart = (e != null && isTimeOnly(e) && (e == "23:59" || e == "23:59:59") && (s.isNullOrBlank())) && days.isEmpty()
                if (zeroStartNoEnd || endAtDayMaxNoStart) {
                    // Consider as fallback (i.e., always-on, non-restrictive)
                    fallback.add(it)
                } else {
                    if (intervalActive(s, e, days)) scheduled.add(it) else fallback.add(it)
                }
            } else fallback.add(it)
        }
        val activeSet = if (scheduled.isNotEmpty()) scheduled else fallback.filter { it.repeat != false }
        if (activeSet.isEmpty()) return emptyList()
        return if (scheduled.isNotEmpty()) scheduled else activeSet
    }
}

object ApiClientImageHelper {
    private fun isAbsolute(u: String?): Boolean = u != null && (u.startsWith("http://", ignoreCase = true) || u.startsWith("https://", ignoreCase = true))
    fun buildImageUrl(filename: String): String = if (isAbsolute(filename)) filename else ApiClient.baseUrl + "static/uploads/" + filename
    fun buildVideoUrl(filename: String): String = if (isAbsolute(filename)) filename else ApiClient.baseUrl + "media/" + filename // new ranged streaming endpoint
    // Unified builder used by loadAnimatedOrStatic (images & animated assets live in static/uploads)
    fun buildFileUrl(filename: String): String = if (isAbsolute(filename)) filename else buildImageUrl(filename)
}

// Simple in-memory bitmap cache (approx ~8MB default)
object ImageMemoryCache {
    private val maxKb = (Runtime.getRuntime().maxMemory() / 1024).toInt()
    private val cacheSize = maxKb / 16 // use 1/16th of available mem
    private val lru = object: LruCache<String, android.graphics.Bitmap>(cacheSize) {
        override fun sizeOf(key: String, value: android.graphics.Bitmap): Int = value.byteCount / 1024
    }
    fun get(key: String) = lru.get(key)
    fun put(key: String, bmp: android.graphics.Bitmap) { if (get(key) == null) lru.put(key, bmp) }
}

// App-wide singleton media cache to avoid lock conflicts across Activity restarts
object AppMediaCacheHolder {
    @Volatile private var simpleCache: com.google.android.exoplayer2.upstream.cache.SimpleCache? = null
    @Synchronized fun get(context: android.content.Context): com.google.android.exoplayer2.upstream.cache.SimpleCache {
        val existing = simpleCache
        if (existing != null) return existing
        val dir = File(context.applicationContext.cacheDir, "mediaCache").apply { mkdirs() }
        val evictor = com.google.android.exoplayer2.upstream.cache.LeastRecentlyUsedCacheEvictor(200L * 1024 * 1024)
        val db = com.google.android.exoplayer2.database.StandaloneDatabaseProvider(context.applicationContext)
        val sc = com.google.android.exoplayer2.upstream.cache.SimpleCache(dir, evictor, db)
        simpleCache = sc
        return sc
    }
}

suspend fun fetchBitmap(urlStr: String): android.graphics.Bitmap? = withContext(Dispatchers.IO) {
    ImageMemoryCache.get(urlStr)?.let { return@withContext it }
    try {
        val url = URL(urlStr)
        val conn = url.openConnection() as HttpURLConnection
        conn.connectTimeout = 3000
        conn.readTimeout = 4000
        conn.instanceFollowRedirects = true
        conn.inputStream.use { inp ->
            val bmp = BitmapFactory.decodeStream(inp)
            if (bmp != null) ImageMemoryCache.put(urlStr, bmp)
            bmp
        }
    } catch (e: Exception) { null }
}

// --- Rotation & periodic fetching helpers ---
private data class ActivePlaylist(var items: List<com.pizzahut.tv.api.PlaylistItem>, var index: Int = 0)

private fun TvDisplayActivity.startPlaylistLoop(storeId: String, screenId: String, imageView: ImageView, playerView: com.google.android.exoplayer2.ui.StyledPlayerView) {
    val state = ActivePlaylist(emptyList())
    var originalItems: List<com.pizzahut.tv.api.PlaylistItem> = emptyList()
    val refreshIntervalMs = 5_000L // refresh playlist every 5s for quicker backend responses
    fun pickNext(): com.pizzahut.tv.api.PlaylistItem? {
        if (state.items.isEmpty()) return null
        if (state.index >= state.items.size) state.index = 0
        return state.items[state.index++]
    }

    fun prefetchNext(nextItem: com.pizzahut.tv.api.PlaylistItem?) {
        val pref = nextItem?.url
        val nf = nextItem?.file ?: return
        val nurl = when {
            pref != null && pref.startsWith("http", true) -> pref
            else -> ApiClientImageHelper.buildImageUrl(nf)
        }
        if (ImageMemoryCache.get(nurl) == null) {
            lifecycleScope.launch(Dispatchers.IO) { fetchBitmap(nurl) }
        }
    }

    // Keep extension sets in sync with Flask backend /supported_extensions endpoint
    val videoExts = setOf("mp4","webm","ogg","mov","avi","mkv","m4v")
    val animatedExts = setOf("gif","webp")
    // Advanced still formats allowed by backend but not always decodable on all Android API levels.
    // heic/heif: API >= 28, avif: API >= 31, svg/tiff require custom decoding libs (not bundled) -> will likely fail and be skipped.
    val advancedStillExts = setOf("avif","heic","heif","svg","tif","tiff")

    fun isVideo(file: String) = videoExts.any { file.endsWith(".$it", true) }
    fun isAnimated(file: String) = animatedExts.any { file.endsWith(".$it", true) }
    fun isAdvancedStill(file: String) = advancedStillExts.any { file.endsWith(".$it", true) }

    fun loadAnimatedOrStatic(file: String, itemId: String?, preferredUrl: String?, onDone: (Boolean) -> Unit) {
        val url = if (!preferredUrl.isNullOrBlank() && preferredUrl.startsWith("http", true)) preferredUrl else ApiClientImageHelper.buildFileUrl(file)
        lifecycleScope.launch {
            if (isAnimated(file) && android.os.Build.VERSION.SDK_INT >= 28) {
                val drawable = withContext(Dispatchers.IO) {
                    try {
                        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                            connectTimeout = 4000; readTimeout = 6000
                        }
                        conn.inputStream.use { inp ->
                            val bytes = inp.readBytes()
                            val source = ImageDecoder.createSource(bytes)
                            ImageDecoder.decodeDrawable(source)
                        }
                    } catch (e: Exception) { null }
                }
                if (drawable != null) {
                    imageView.setImageDrawable(drawable)
                    if (drawable is AnimatedImageDrawable) drawable.start()
                    binding.message.text = file.take(50)
                    // report success
                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                    // start periodic ok ping to keep dashboard green while displayed
                    startItemOkPing(storeId, screenId, file, itemId)
                    onDone(true)
                } else {
                    // fallback to bitmap path
                    val bmp = withContext(Dispatchers.IO) { fetchBitmap(url) }
                    if (bmp != null) {
                        imageView.setImageBitmap(bmp)
                        binding.message.text = file.take(50)
                        try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                        startItemOkPing(storeId, screenId, file, itemId)
                        onDone(true)
                    } else {
                        binding.message.text = "Load failed: $file".take(60)
                        try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "bitmap decode failed")) } catch (_: Exception) {}
                        onDone(false)
                    }
                }
            } else {
                val bmp = withContext(Dispatchers.IO) { fetchBitmap(url) }
                if (bmp != null) {
                    imageView.setImageBitmap(bmp)
                    binding.message.text = file.take(50)
                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                    startItemOkPing(storeId, screenId, file, itemId)
                    onDone(true)
                } else {
                    binding.message.text = "Load failed: $file".take(60)
                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "image fetch failed")) } catch (_: Exception) {}
                    onDone(false)
                }
            }
        }
    }

    // --- ExoPlayer setup with simple least-recent disk cache ---
    // Build (or reuse) ExoPlayer + cache stack
    var cacheDataSourceFactory: com.google.android.exoplayer2.upstream.cache.CacheDataSource.Factory? = null
    // Player lifecycle helpers
    var playerListenersAttached = false
    var currentVideoFile: String? = null
    var triedStaticFallbackForCurrent = false
    fun ensurePlayer() : com.google.android.exoplayer2.ExoPlayer {
        val existing = exoPlayer
        if (existing != null) return existing
    val simpleCache = AppMediaCacheHolder.get(this)
        val okClientBuilder = okhttp3.OkHttpClient.Builder()
            .addInterceptor { chain ->
                val original = chain.request()
                val builder = original.newBuilder()
                // Propagate pairing header so gated media endpoints work
                try {
                    val code = com.pizzahut.tv.api.PairCodeHolder.get()
                    if (!code.isNullOrBlank()) builder.addHeader("X-User-Code", code)
                } catch (_: Exception) {}
                // Ensure Accept header favors MP4 when no explicit type was set
                if (original.header("Accept").isNullOrBlank()) {
                    builder.addHeader("Accept", "video/mp4,video/*;q=0.9,*/*;q=0.8")
                }
                if (original.header("User-Agent").isNullOrBlank()) {
                    builder.header("User-Agent", "ExoPlayer (Android TV)")
                }
                chain.proceed(builder.build())
            }
            .connectTimeout(5, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(8, java.util.concurrent.TimeUnit.SECONDS)
        // Attach basic HTTP logging to observe status codes and redirects
        try {
            val httpLogger = okhttp3.logging.HttpLoggingInterceptor { msg -> Log.d("OkHttp", msg) }
            httpLogger.level = okhttp3.logging.HttpLoggingInterceptor.Level.BASIC
            okClientBuilder.addInterceptor(httpLogger)
        } catch (_: Exception) {}
        val okClient = okClientBuilder.build()
        mediaHttpClient = okClient
    val okFactory = com.google.android.exoplayer2.ext.okhttp.OkHttpDataSource.Factory(okClient)
        val upstream = com.google.android.exoplayer2.upstream.DefaultDataSource.Factory(this, okFactory)
        cacheDataSourceFactory = com.google.android.exoplayer2.upstream.cache.CacheDataSource.Factory()
            .setCache(simpleCache)
            .setUpstreamDataSourceFactory(upstream)
            .setFlags(com.google.android.exoplayer2.upstream.cache.CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
        val renderersFactory = com.google.android.exoplayer2.DefaultRenderersFactory(this)
            .setEnableDecoderFallback(true)
            .setExtensionRendererMode(com.google.android.exoplayer2.DefaultRenderersFactory.EXTENSION_RENDERER_MODE_PREFER)
    val built = com.google.android.exoplayer2.ExoPlayer.Builder(this)
            .setRenderersFactory(renderersFactory)
            .setSeekForwardIncrementMs(5_000)
            .setSeekBackIncrementMs(5_000)
            .build().also { playerView.player = it }
    // Repeat handled by playlist timing, not ExoPlayer internal repeat
    built.repeatMode = com.google.android.exoplayer2.Player.REPEAT_MODE_OFF
    built.shuffleModeEnabled = false
        exoPlayer = built
        return built
    }

    fun buildMediaSource(url: String): com.google.android.exoplayer2.source.MediaSource {
    val item = if (url.endsWith(".mp4", true) || url.contains("/media/") ) {
            com.google.android.exoplayer2.MediaItem.Builder()
                .setUri(url)
                .setMimeType(com.google.android.exoplayer2.util.MimeTypes.VIDEO_MP4)
                .build()
        } else com.google.android.exoplayer2.MediaItem.fromUri(url)
        val cacheFactory = cacheDataSourceFactory
        val progressiveFactory = com.google.android.exoplayer2.source.ProgressiveMediaSource.Factory(
            cacheFactory ?: com.google.android.exoplayer2.upstream.DefaultDataSource.Factory(this)
        )
    return progressiveFactory.createMediaSource(item)
    }

    suspend fun probeMedia(url: String): String = withContext(Dispatchers.IO) {
        val client = mediaHttpClient ?: return@withContext "no-client"
        return@withContext try {
            val req = okhttp3.Request.Builder()
                .url(url)
                .addHeader("Range", "bytes=0-1023")
                .addHeader("Accept", "video/mp4,video/*;q=0.9,*/*;q=0.8")
                .build()
            client.newCall(req).execute().use { resp ->
                val code = resp.code
                val ct = resp.header("Content-Type") ?: ""
                val cl = resp.header("Content-Length") ?: ""
                "HTTP $code ct=${ct.take(24)} len=${cl.take(12)}"
            }
        } catch (e: Exception) { "ERR ${e.message}" }
    }

    suspend fun probeCode(url: String): Int? = withContext(Dispatchers.IO) {
        val client = mediaHttpClient ?: return@withContext null
        return@withContext try {
            val req = okhttp3.Request.Builder()
                .url(url)
                .addHeader("Range", "bytes=0-1")
                .build()
            client.newCall(req).execute().use { it.code }
        } catch (_: Exception) { null }
    }

    suspend fun headOk(url: String, timeoutMs: Int = 4000): Pair<Boolean,String?> = withContext(Dispatchers.IO) {
        return@withContext try {
            val u = URL(url)
            val c = (u.openConnection() as HttpURLConnection).apply {
                requestMethod = "HEAD"; connectTimeout = timeoutMs; readTimeout = timeoutMs
            }
            val code = c.responseCode
            val len = c.getHeaderField("Content-Length")
            Pair(code in 200..299, "HEAD $code len=$len")
        } catch (e: Exception) { Pair(false, e.message) }
    }

    var scheduledRotation: Runnable? = null
    var videoStallWatch: Runnable? = null
    var scheduleTick: Runnable? = null
    var showNext: (() -> Unit)? = null
    var currentItemFile: String? = null
    // Align next switch to sync_ref.start_epoch cadence (like web player)
    fun alignedDelayMs(baseDurMs: Long, sref: com.pizzahut.tv.api.SyncRef?): Long {
        if (baseDurMs <= 0L || sref == null) return baseDurMs
        val startEpoch = sref.startEpoch ?: return baseDurMs
        return try {
            val nowSec = System.currentTimeMillis() / 1000L
            val durSec = (baseDurMs / 1000L).coerceAtLeast(1L)
            val elapsed = (nowSec - startEpoch).coerceAtLeast(0L)
            val mod = elapsed % durSec
            val remainSec = if (mod == 0L) durSec else (durSec - mod)
            val ms = remainSec * 1000L
            // Keep within sane bounds to avoid instant flips
            ms.coerceIn(300L, baseDurMs)
        } catch (_: Exception) { baseDurMs }
    }
    fun cancelScheduled() {
        scheduledRotation?.let {
            imageView.removeCallbacks(it)
            playerView.removeCallbacks(it)
        }
        scheduledRotation = null
        videoStallWatch?.let {
            imageView.removeCallbacks(it)
            playerView.removeCallbacks(it)
        }
        videoStallWatch = null
        scheduleTick?.let {
            imageView.removeCallbacks(it)
            playerView.removeCallbacks(it)
        }
        scheduleTick = null
        // Do not cancel itemOkPingJob here; it's tied to the active item.
        // Ping will be cancelled when switching items at the top of showAndSchedule() or onDestroy().
    }
    // Define schedule tick before showAndSchedule; use a function reference to avoid forward declaration issues
    fun ensureScheduleTick() {
        if (scheduleTick != null) return
        scheduleTick = Runnable {
            try {
                if (originalItems.isNotEmpty()) {
                    val newFiltered = filterBySchedule(originalItems)
                    val cur = currentItemFile
                    val containsCurrent = cur != null && newFiltered.any { it.file == cur }
                    if (state.items.isEmpty() && newFiltered.isNotEmpty()) {
                        state.items = newFiltered; state.index = 0
                    } else if (!containsCurrent) {
                        // Current item no longer active -> interrupt and reschedule next
                        cancelScheduled()
                        state.items = newFiltered; state.index = 0
                        showNext?.invoke(); return@Runnable
                    }
                }
            } catch (_: Exception) { }
            // Watchdog: if rotation task was lost but we have items, kick it
            if (scheduledRotation == null && state.items.isNotEmpty()) {
                showNext?.invoke(); return@Runnable
            }
        imageView.postDelayed(scheduleTick!!, 1_000L)
        }
        imageView.postDelayed(scheduleTick!!, 1_000L)
    }

    fun showAndSchedule() {
    // Switching context to the next item: stop ping from previous item
    cancelItemOkPing()
        // Re-filter on each step for near real-time schedule flips
        if (originalItems.isNotEmpty()) {
            val newFiltered = filterBySchedule(originalItems)
            val currentFiles = state.items.mapNotNull { it.file }
            val newFiles = newFiltered.mapNotNull { it.file }
            if (newFiles != currentFiles) {
                val currentIndexFile = state.items.getOrNull((state.index - 1).coerceAtLeast(0))?.file
                state.items = newFiltered
                state.index = if (currentIndexFile != null) {
                    val idx = newFiltered.indexOfFirst { it.file == currentIndexFile }
                    if (idx >= 0) (idx + 1) % (newFiltered.size.coerceAtLeast(1)) else 0
                } else 0
            } else if (state.items.isEmpty() && newFiltered.isNotEmpty()) {
                state.items = newFiltered; state.index = 0
            }
        }
    ensureScheduleTick()
        var next = pickNext()
        // Avoid selecting the same item twice in a row when multiple items exist
        if (next != null && next.file != null && next.file == currentItemFile && state.items.size > 1) {
            next = pickNext()
        }
    debugOverlay?.text = "idx=${state.index}/${state.items.size} cur=${currentItemFile ?: "-"}"
        if (next?.file == null) {
            binding.message.text = "No items currently scheduled"
            imageView.postDelayed({ showAndSchedule() }, 5_000L)
            return
        }
    val file = next.file!!
        currentItemFile = file
        if (isVideo(file)) {
            imageView.visibility = ImageView.GONE
            playerView.visibility = ImageView.VISIBLE
            // Ensure message is above player
            binding.message.bringToFront()
            // Helper: detect emulator (AOSP TV on x86 etc.)
            fun isEmulatorDevice(): Boolean {
                return try {
                    val fp = android.os.Build.FINGERPRINT.lowercase()
                    val model = android.os.Build.MODEL.lowercase()
                    val brand = android.os.Build.BRAND.lowercase()
                    fp.contains("generic") || fp.contains("unknown") ||
                            model.contains("google_sdk") || model.contains("emulator") || model.contains("sdk_gphone") || model.contains("aosp tv on x86") ||
                            brand.contains("generic")
                } catch (_: Exception) { false }
            }
            // If this item is part of a split group, wrap the given view to only show the assigned slice (idempotent)
            fun applySegmentWrapTo(targetView: android.view.View) {
                try {
                    val sref = next.syncRef
                    val mode = sref?.mode?.lowercase() ?: "split-h"
                    val order = (sref?.order ?: 0).coerceAtLeast(0)
                    val count = (sref?.count ?: 0).coerceAtLeast(0)
                    val isH = (mode == "split-h" || mode.isBlank())
                    val isV = (mode == "split-v")
                    if (!(((isH || isV) && count > 1))) {
                        // No split: if already wrapped, just normalize transforms
                        val maybeInner = targetView.parent as? android.widget.FrameLayout
                        if (maybeInner?.tag == "seg-inner") {
                            maybeInner.pivotX = 0f; maybeInner.pivotY = 0f
                            maybeInner.scaleX = 1f
                            maybeInner.scaleY = 1f
                            maybeInner.translationX = 0f
                            maybeInner.translationY = 0f
                        }
                        // Also schedule a re-apply after layout
                        targetView.postDelayed({
                            try {
                                val inner2 = targetView.parent as? android.widget.FrameLayout
                                if (inner2?.tag == "seg-inner") { inner2.pivotX = 0f; inner2.pivotY = 0f; inner2.scaleX = 1f; inner2.scaleY = 1f; inner2.translationX = 0f; inner2.translationY = 0f }
                            } catch (_: Exception) {}
                        }, 120)
                        return
                    }
                    val currentParent = targetView.parent as? ViewGroup ?: return
                    // If already wrapped (parent tagged as seg-inner), just update transforms
                    if (currentParent is android.widget.FrameLayout && currentParent.tag == "seg-inner") {
                        val inner = currentParent
                        inner.pivotX = 0f; inner.pivotY = 0f
                        val wrapView = (inner.parent as? android.view.View)
                        val wrapWidth = wrapView?.width?.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                        val wrapHeight = wrapView?.height?.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                        if (isH) {
                            inner.scaleX = count.toFloat(); inner.scaleY = 1f
                            inner.translationX = - (order * wrapWidth.toFloat()); inner.translationY = 0f
                        } else {
                            inner.scaleY = count.toFloat(); inner.scaleX = 1f
                            inner.translationY = - (order * wrapHeight.toFloat()); inner.translationX = 0f
                        }
                        // Re-apply again shortly in case dimensions were 0 at first
                        targetView.postDelayed({
                            try {
                                val innerR = targetView.parent as? android.widget.FrameLayout
                                if (innerR is android.widget.FrameLayout && innerR.tag == "seg-inner") {
                                    val wrapView2 = (innerR.parent as? android.view.View)
                                    val w2 = wrapView2?.width?.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                                    val h2 = wrapView2?.height?.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                                    if (isH) {
                                        innerR.scaleX = count.toFloat(); innerR.scaleY = 1f
                                        innerR.translationX = - (order * w2.toFloat()); innerR.translationY = 0f
                                    } else {
                                        innerR.scaleY = count.toFloat(); innerR.scaleX = 1f
                                        innerR.translationY = - (order * h2.toFloat()); innerR.translationX = 0f
                                    }
                                }
                            } catch (_: Exception) {}
                        }, 120)
                        return
                    }
                    // Wrap once: replace playerView with wrap(inner(playerView)) at same index
                    val originalParent = currentParent
                    val originalIndex = originalParent.indexOfChild(targetView)
                    val originalLp = targetView.layoutParams
                    // Create containers and move view
                    val wrap = android.widget.FrameLayout(this).apply {
                        tag = "seg-wrap"
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                        clipToPadding = true; clipChildren = true
                    }
                    val inner = android.widget.FrameLayout(this).apply {
                        tag = "seg-inner"
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                    }
                    try { originalParent.removeView(targetView) } catch (_: Exception) {}
                    inner.addView(targetView, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
                    wrap.addView(inner)
                    // Insert wrapper back at the same position with previous layout params if available
                    if (originalIndex >= 0) originalParent.addView(wrap, originalIndex, originalLp)
                    else originalParent.addView(wrap)
                    // Apply transforms for slice
                    inner.pivotX = 0f; inner.pivotY = 0f
                    val wrapWidth = wrap.width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                    val wrapHeight = wrap.height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                    if (isH) {
                        inner.scaleX = count.toFloat(); inner.scaleY = 1f
                        inner.translationX = - (order * wrapWidth.toFloat()); inner.translationY = 0f
                    } else {
                        inner.scaleY = count.toFloat(); inner.scaleX = 1f
                        inner.translationY = - (order * wrapHeight.toFloat()); inner.translationX = 0f
                    }
                    // Re-apply after layout to ensure correct measured dims
                    targetView.postDelayed({
                        try {
                            val innerR = targetView.parent as? android.widget.FrameLayout
                            val wrapR = innerR?.parent as? android.widget.FrameLayout
                            if (innerR != null && wrapR != null) {
                                val w2 = wrapR.width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                                val h2 = wrapR.height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                                if (isH) {
                                    innerR.scaleX = count.toFloat(); innerR.scaleY = 1f
                                    innerR.translationX = - (order * w2.toFloat()); innerR.translationY = 0f
                                } else {
                                    innerR.scaleY = count.toFloat(); innerR.scaleX = 1f
                                    innerR.translationY = - (order * h2.toFloat()); innerR.translationX = 0f
                                }
                            }
                        } catch (_: Exception) {}
                    }, 120)
                } catch (_: Exception) {}
            }
            // Apply wrap for video view
            applySegmentWrapTo(playerView)
            // Determine if we should force-static for emulator on sliced media
            val isSlice = (next.syncRef?.count ?: 0) > 1
            val emulatorSliceWanted = isSlice && isEmulatorDevice() && !isEmuSliceVideoForced()
            // Prefer absolute URL from server when provided; otherwise use /media. Fallback to the alternate, then static image.
            val absUrl = next.url?.takeIf { it.startsWith("http", true) }
            val mediaUrl = ApiClientImageHelper.buildVideoUrl(file)
            val staticUrl = ApiClientImageHelper.buildImageUrl(file)
            val videoUrlPrimary = absUrl ?: mediaUrl
            val videoUrlFallback = if (absUrl != null) mediaUrl else staticUrl
            // Clarify normal vs sync-slice in label similar to web player
            runCatching {
                val sref = next.syncRef
                val cnt = (sref?.count ?: 0)
                if (cnt > 1) {
                    val modeCh = (sref?.mode?.lowercase() ?: "h").let { if (it.contains('v')) 'V' else 'H' }
                    val ord = (sref?.order ?: 0)
                    binding.message.text = ("SYNC ${modeCh}${cnt} #${ord}  " + file.take(18)).take(60)
                } else {
                    binding.message.text = ("VID " + file.take(18)).take(60)
                }
            }.onFailure { binding.message.text = "VID ${file.take(18)}" }
            fun showStaticFallback() {
                try {
                    try { exoPlayer?.stop(); exoPlayer?.clearMediaItems() } catch (_: Exception) {}
                    legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
                    playerView.visibility = ImageView.GONE
                    imageView.visibility = ViewGroup.VISIBLE
                    // Apply split-slice cropping for images too (matches web player)
                    runCatching {
                        val sref = next.syncRef
                        val mode = sref?.mode?.lowercase() ?: "split-h"
                        val order = (sref?.order ?: 0).coerceAtLeast(0)
                        val count = (sref?.count ?: 0).coerceAtLeast(0)
                        val isH = (mode == "split-h" || mode.isBlank())
                        val isV = (mode == "split-v")
                        if ((isH || isV) && count > 1) {
                            val currentParent = imageView.parent as? ViewGroup
                            if (currentParent != null) {
                                // If already wrapped, update transforms else wrap now
                                val maybeInner = imageView.parent as? android.widget.FrameLayout
                                if (maybeInner?.tag == "seg-inner") {
                                    val inner = maybeInner
                                    inner.pivotX = 0f; inner.pivotY = 0f
                                    val wrapView = (inner.parent as? android.view.View)
                                    val wrapWidth = wrapView?.width?.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                                    val wrapHeight = wrapView?.height?.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                                    if (isH) {
                                        inner.scaleX = count.toFloat(); inner.scaleY = 1f
                                        inner.translationX = - (order * wrapWidth.toFloat()); inner.translationY = 0f
                                    } else {
                                        inner.scaleY = count.toFloat(); inner.scaleX = 1f
                                        inner.translationY = - (order * wrapHeight.toFloat()); inner.translationX = 0f
                                    }
                                } else {
                                    val originalIndex = currentParent.indexOfChild(imageView)
                                    val originalLp = imageView.layoutParams
                                    val wrap = android.widget.FrameLayout(this).apply {
                                        tag = "seg-wrap"
                                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                                        clipToPadding = true; clipChildren = true
                                    }
                                    val inner = android.widget.FrameLayout(this).apply {
                                        tag = "seg-inner"
                                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                                    }
                                    try { currentParent.removeView(imageView) } catch (_: Exception) {}
                                    inner.addView(imageView, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
                                    wrap.addView(inner)
                                    if (originalIndex >= 0) currentParent.addView(wrap, originalIndex, originalLp) else currentParent.addView(wrap)
                                    inner.pivotX = 0f; inner.pivotY = 0f
                                    val wrapWidth = wrap.width.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                                    val wrapHeight = wrap.height.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                                    if (isH) {
                                        inner.scaleX = count.toFloat(); inner.scaleY = 1f
                                        inner.translationX = - (order * wrapWidth.toFloat()); inner.translationY = 0f
                                    } else {
                                        inner.scaleY = count.toFloat(); inner.scaleX = 1f
                                        inner.translationY = - (order * wrapHeight.toFloat()); inner.translationX = 0f
                                    }
                                }
                            }
                        } else {
                            // Not split: if previously wrapped, reset transforms
                            val maybeInner = imageView.parent as? android.widget.FrameLayout
                            if (maybeInner?.tag == "seg-inner") {
                                maybeInner.pivotX = 0f; maybeInner.pivotY = 0f
                                maybeInner.scaleX = 1f
                                maybeInner.scaleY = 1f
                                maybeInner.translationX = 0f
                                maybeInner.translationY = 0f
                            }
                        }
                    }
                    binding.message.bringToFront()
                    // If this was a sliced item, ensure the image is wrapped the same way for correct cropping
                    if ((next.syncRef?.count ?: 0) > 1) {
                        applySegmentWrapTo(imageView)
                    }
                    // If the original file is a video, try thumbnail candidates (.jpg/.png) under static/uploads
                    val lower = file.lowercase()
                    val isVid = lower.endsWith(".mp4") || lower.endsWith(".webm") || lower.endsWith(".mkv") || lower.endsWith(".mov") || lower.endsWith(".avi") || lower.endsWith(".m4v")
                    if (isVid) {
                        val base = file.substringBeforeLast('.')
                        val jpg = ApiClientImageHelper.buildImageUrl(base + ".jpg")
                        val png = ApiClientImageHelper.buildImageUrl(base + ".png")
                        // If server provided absolute URL, try same-location jpg/png first (useful with CDNs)
                        val absBase = absUrl?.substringBeforeLast('.')
                        val absJpg = absBase?.plus(".jpg")
                        val absPng = absBase?.plus(".png")
                        lifecycleScope.launch {
                            // order: abs jpg -> abs png -> local jpg -> local png -> animated/static fallback
                            val bmpJ = withContext(Dispatchers.IO) {
                                absJpg?.let { fetchBitmap(it) } ?: fetchBitmap(jpg)
                            }
                            if (bmpJ != null) {
                                imageView.setImageBitmap(bmpJ)
                                val label = if (absJpg != null) "abs.jpg" else "jpg"
                                binding.message.text = ("Thumb ${base.take(14)}.$label").take(60)
                                Log.w(TAG, "using static jpg thumb for " + file)
                            } else {
                                val bmpP = withContext(Dispatchers.IO) {
                                    absPng?.let { fetchBitmap(it) } ?: fetchBitmap(png)
                                }
                                if (bmpP != null) {
                                    imageView.setImageBitmap(bmpP)
                                    val label = if (absPng != null) "abs.png" else "png"
                                    binding.message.text = ("Thumb ${base.take(14)}.$label").take(60)
                                    Log.w(TAG, "using static png thumb for " + file)
                                } else {
                                    // Fallback to attempt loading the same path under static (may be an animated asset)
                                    loadAnimatedOrStatic(file, next.id, staticUrl) { _ -> }
                                    Log.w(TAG, "using static fallback (no thumb) for " + file)
                                }
                            }
                        }
                    } else {
                        loadAnimatedOrStatic(file, next.id, staticUrl) { _ -> }
                        Log.w(TAG, "using static fallback for " + file)
                    }
                } catch (_: Exception) {}
            }
            // Emulator safeguard: if slice on emulator, use static path and skip ExoPlayer setup
            if (emulatorSliceWanted) {
                binding.message.text = ("Slice static (emu) ${file.take(10)}").take(60)
                showStaticFallback()
                // Schedule rotation based on playlist duration
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                val aligned = alignedDelayMs(durMs, next.syncRef)
                cancelScheduled()
                scheduledRotation = Runnable { showAndSchedule() }
                playerView.postDelayed(scheduledRotation!!, aligned)
                return
            }
            // Legacy VideoView fallback (added lazily)
            fun ensureLegacy(): VideoView {
                val existing = legacyVideoView
                if (existing != null) return existing
                val vv = VideoView(this)
                vv.layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                vv.setBackgroundColor(Color.BLACK)
                vv.visibility = ImageView.GONE // keep hidden until prepared
                // add behind message
                binding.root.addView(vv, 0)
                legacyVideoView = vv
                return vv
            }
        fun useLegacy() {
                try {
                    binding.message.text = "Legacy start ${file.take(16)}"
                    val vv = ensureLegacy()
                    playerView.visibility = ImageView.GONE
            // If fallback is a static image (no video), point legacy to the primary video URL instead
            val legacyUrl = if (videoUrlFallback.contains("/static/")) videoUrlPrimary else videoUrlFallback
            vv.setVideoURI(Uri.parse(legacyUrl))
                    vv.setOnPreparedListener { mp ->
                        // Do not loop automatically; we'll advance based on playlist duration
                        mp.isLooping = false
                        vv.visibility = ImageView.VISIBLE
                        vv.start()
                        binding.message.text = "Legacy PLAY ${file.take(14)}"
                        // Report success for legacy playback
                        lifecycleScope.launch(Dispatchers.IO) {
                            try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = next.id)) } catch (_: Exception) {}
                        }
                        // Start periodic ok ping while this legacy video is playing
                        startItemOkPing(storeId, screenId, file, next.id)
                        // Schedule rotation according to playlist duration
                        val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                        val aligned = alignedDelayMs(durMs, next.syncRef)
                        cancelScheduled()
                        scheduledRotation = Runnable {
                            try { vv.stopPlayback() } catch (_: Exception) {}
                            vv.visibility = ImageView.GONE
                            showAndSchedule()
                        }
                        vv.postDelayed(scheduledRotation!!, aligned)
                    }
                    vv.setOnErrorListener { _, what, extra ->
                        binding.message.text = "LegacyErr w=$what e=$extra"
                        lifecycleScope.launch(Dispatchers.IO) {
                            try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = next.id, error = "legacy error w=$what e=$extra")) } catch (_: Exception) {}
                        }
                        cancelScheduled()
                        try { vv.stopPlayback() } catch (_: Exception) {}
                        vv.visibility = ImageView.GONE
                        showAndSchedule()
                        true
                    }
                    // If legacy never prepares within 6s, skip to next
                    vv.postDelayed({
                        if (vv.visibility != ImageView.VISIBLE) {
                            cancelScheduled()
                            try { vv.stopPlayback() } catch (_: Exception) {}
                            vv.visibility = ImageView.GONE
                            binding.message.text = "Legacy timeout"
                            showAndSchedule()
                        }
                    }, 6_000L)
                } catch (e: Exception) {
                    binding.message.text = ("LegacyFail ${e.message}").take(60)
                    showAndSchedule()
                }
            }
            try {
                val player = ensurePlayer()
                // Attach listeners only once
                // Prepare new source
                currentVideoFile = file
                triedStaticFallbackForCurrent = false
                player.clearMediaItems()
                // Ensure legacy view is hidden when using ExoPlayer
                legacyVideoView?.visibility = ImageView.GONE
                if (!playerListenersAttached) {
                    player.addListener(object: com.google.android.exoplayer2.Player.Listener {
            override fun onPlaybackStateChanged(stateCode: Int) {
                            val f = currentVideoFile ?: "vid"
                            val label = when(stateCode){
                                com.google.android.exoplayer2.Player.STATE_IDLE -> "IDLE"
                                com.google.android.exoplayer2.Player.STATE_BUFFERING -> "BUF"
                                com.google.android.exoplayer2.Player.STATE_READY -> "READY"
                                com.google.android.exoplayer2.Player.STATE_ENDED -> "END"
                                else -> stateCode.toString()
                            }
                            Log.d(TAG, "state=" + label + " file=" + f)
                            binding.message.text = ("${f.take(12)} $label").take(60)
                            if (stateCode == com.google.android.exoplayer2.Player.STATE_READY) {
                                // Cancel stall watchdog once we are ready
                                videoStallWatch?.let { playerView.removeCallbacks(it); imageView.removeCallbacks(it) }
                                videoStallWatch = null
                                lifecycleScope.launch(Dispatchers.IO) {
                                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = f, itemId = next.id)) } catch (_: Exception) {}
                                }
                                // Start periodic ok ping while this video item is playing
                                startItemOkPing(storeId, screenId, f, next.id)
                            }
                            if (stateCode == com.google.android.exoplayer2.Player.STATE_ENDED) {
                                // Advance if natural end happens early
                                try { player.playWhenReady = false; player.stop(); player.clearMediaItems() } catch (_: Exception) {}
                                cancelScheduled()
                                showAndSchedule()
                            }
                        }
                        override fun onPlayerError(error: com.google.android.exoplayer2.PlaybackException) {
                            val f = currentVideoFile ?: "vid"
                            val emsg = error.message ?: ""
                            val hint = if (emsg.contains("CLEARTEXT", true) || emsg.contains("cleartext", true)) {
                                " (HTTP blocked)"
                            } else if (emsg.contains("403") || emsg.contains("401")) {
                                " (auth?)"
                            } else ""
                            Log.e(TAG, "playerError code=" + error.errorCodeName + " msg=" + (error.message ?: ""))
                            binding.message.text = ("Err ${error.errorCodeName}$hint" + (emsg.let { if (it.isNotBlank()) ":"+it.take(20) else "" })).take(60)
                            val playerRef = exoPlayer ?: return
                            lifecycleScope.launch(Dispatchers.IO) {
                                try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = f, itemId = next.id, error = error.message)) } catch (_: Exception) {}
                            }
                // First error: try static fallback path once
                            if (!triedStaticFallbackForCurrent) {
                                triedStaticFallbackForCurrent = true
                                try {
                    // Show static image instead of trying to stream it via ExoPlayer
                    binding.message.text = ("StaticFB ${f.take(10)}").take(60)
                    showStaticFallback(); return
                                } catch (_: Exception) { /* fall through */ }
                            }
                            // Second failure: try legacy player as last resort before skipping
                            try {
                                useLegacy(); return
                            } catch (_: Exception) {
                                // Skip to next
                                cancelScheduled()
                                playerView.postDelayed({ showAndSchedule() }, 500)
                            }
                        }
                    })
                    playerListenersAttached = true
                }
                player.setMediaSource(buildMediaSource(videoUrlPrimary))
                player.prepare(); player.playWhenReady = true
                
                // Apply video slicing for sync groups (same logic as images)
                runCatching {
                    val sref = next.syncRef
                    val mode = sref?.mode?.lowercase() ?: "split-h"
                    val order = (sref?.order ?: 0).coerceAtLeast(0)
                    val count = (sref?.count ?: 0).coerceAtLeast(0)
                    val isH = (mode == "split-h" || mode.isBlank())
                    val isV = (mode == "split-v")
                    
                    Log.d(TAG, "Video slicing check: mode=$mode, order=$order, count=$count, file=${next.file}")
                    
                    if ((isH || isV) && count > 1) {
                        Log.d(TAG, "Applying video slicing transforms...")
                        
                        // Delay to ensure playerView is ready
                        playerView.post {
                            runCatching {
                                // Apply the same segment wrapping to playerView as we do for imageView
                                applySegmentWrapTo(playerView)
                                
                                // Apply slice transformation to the wrapped container
                                val maybeInner = playerView.parent as? android.widget.FrameLayout
                                if (maybeInner?.tag == "seg-inner") {
                                    val inner = maybeInner
                                    inner.pivotX = 0f; inner.pivotY = 0f
                                    val wrapView = (inner.parent as? android.view.View)
                                    val wrapWidth = wrapView?.width?.takeIf { it > 0 } ?: resources.displayMetrics.widthPixels
                                    val wrapHeight = wrapView?.height?.takeIf { it > 0 } ?: resources.displayMetrics.heightPixels
                                    
                                    if (isH) {
                                        inner.scaleX = count.toFloat(); inner.scaleY = 1f
                                        inner.translationX = - (order * wrapWidth.toFloat()); inner.translationY = 0f
                                    } else {
                                        inner.scaleY = count.toFloat(); inner.scaleX = 1f
                                        inner.translationY = - (order * wrapHeight.toFloat()); inner.translationX = 0f
                                    }
                                    
                                    Log.d(TAG, "✅ Applied video slice: mode=$mode, order=$order, count=$count, scaleX=${inner.scaleX}, translateX=${inner.translationX}")
                                } else {
                                    Log.w(TAG, "Failed to find seg-inner container for video slicing")
                                }
                            }.onFailure { e ->
                                Log.e(TAG, "Error in video slicing post-delay: ${e.message}")
                            }
                        }
                    } else {
                        Log.d(TAG, "Video slicing not needed: isH=$isH, isV=$isV, count=$count")
                    }
                }.onFailure { e ->
                    Log.e(TAG, "Error in video slicing setup: ${e.message}")
                }
                
                // Proactive probe: if primary looks blocked (e.g., 403), try fallback automatically
        lifecycleScope.launch {
                    val primary = probeCode(videoUrlPrimary)
                    val goodPrimary = primary != null && (primary in 200..206 || primary in 300..399)
                    if (!goodPrimary && currentVideoFile == file) {
                        val fb = probeCode(videoUrlFallback)
                        val goodFb = fb != null && (fb in 200..206 || fb in 300..399)
            Log.d(TAG, "probe primary=" + (primary ?: -1) + " fb=" + (fb ?: -1) + " file=" + file)
                        if (goodFb && currentVideoFile == file && exoPlayer?.playbackState != com.google.android.exoplayer2.Player.STATE_READY) {
                            binding.message.text = ("HTTP ${primary ?: -1} → FB").take(60)
                            if (videoUrlFallback.startsWith(ApiClient.baseUrl + "static/")) {
                                showStaticFallback()
                            } else {
                                try {
                                    exoPlayer?.clearMediaItems()
                                    exoPlayer?.setMediaSource(buildMediaSource(videoUrlFallback))
                                    exoPlayer?.prepare(); exoPlayer?.playWhenReady = true
                                    Log.d(TAG, "switched to fallback for " + file)
                                } catch (_: Exception) {}
                            }
                        } else if (!goodFb && currentVideoFile == file) {
                            binding.message.text = ("Blocked P=${primary ?: -1} F=${fb ?: -1}").take(60)
                Log.w(TAG, "blocked primary=" + (primary ?: -1) + " fb=" + (fb ?: -1) + " for " + file)
                        }
                    }
                }
                // If we remain buffering for too long, try static fallback once, else skip
                videoStallWatch = Runnable {
                    val stillCurrent = currentVideoFile == file
                    val st = exoPlayer?.playbackState
                    if (stillCurrent && st != com.google.android.exoplayer2.Player.STATE_READY) {
                        val playerRef = exoPlayer
                        if (playerRef != null && !triedStaticFallbackForCurrent) {
                            triedStaticFallbackForCurrent = true
                            try {
                                playerRef.clearMediaItems()
                                val fbUrl = videoUrlFallback
                                if (fbUrl.startsWith(ApiClient.baseUrl + "static/")) {
                                    binding.message.text = ("StaticFB after stall ${file.take(10)}").take(60)
                                    Log.w(TAG, "stall -> static fallback " + file)
                                    showStaticFallback(); return@Runnable
                                } else {
                                    playerRef.setMediaSource(buildMediaSource(fbUrl))
                                    playerRef.prepare(); playerRef.playWhenReady = true
                                    binding.message.text = ("FB after stall ${file.take(10)}").take(60)
                                    Log.w(TAG, "stall -> fallback " + file)
                                }
                            } catch (_: Exception) {
                                try { Log.w(TAG, "stall -> legacy " + file); useLegacy(); return@Runnable } catch (_: Exception) {}
                                cancelScheduled(); playerView.postDelayed({ showAndSchedule() }, 300)
                            }
                        } else {
                            try { binding.message.text = "Legacy after stall"; Log.w(TAG, "legacy after stall " + file); useLegacy(); return@Runnable } catch (_: Exception) {}
                            cancelScheduled(); playerView.postDelayed({ showAndSchedule() }, 300)
                        }
                    }
                }
                playerView.postDelayed(videoStallWatch!!, 5_000L)
                // Schedule rotation based on playlist duration
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                val aligned = alignedDelayMs(durMs, next.syncRef)
                cancelScheduled()
                scheduledRotation = Runnable {
                    // Move to next item after configured duration
                    try {
                        player.playWhenReady = false
                        player.stop()
                        player.clearMediaItems()
                    } catch (_: Exception) {}
            legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
                    showAndSchedule()
                }
                playerView.postDelayed(scheduledRotation!!, aligned)
            } catch (e: Exception) {
                binding.message.text = ("ExoFail ${e.message}").take(60)
                useLegacy()
            }
        } else {
            // Skip formats we know we can't render without extra libs (e.g. svg / tiff) to avoid long black frames
            if (isAdvancedStill(file) && !(file.endsWith(".heic", true) || file.endsWith(".heif", true) || file.endsWith(".avif", true))) {
                binding.message.text = "Unsupported: ${file.take(40)}"
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, error = "unsupported still format")) } catch (_: Exception) {}
                }
                imageView.postDelayed({ showAndSchedule() }, 3000)
                return
            }
            // Image / animated
            try { exoPlayer?.stop(); exoPlayer?.clearMediaItems() } catch (_: Exception) {}
        legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
            playerView.visibility = ImageView.GONE
            imageView.visibility = ImageView.VISIBLE
            binding.message.bringToFront()
            loadAnimatedOrStatic(file, next.id, next.url) { success ->
                // Prefetch upcoming
                val upcoming = if (state.items.isNotEmpty()) {
                    val idx = if (state.index >= state.items.size) 0 else state.index
                    state.items.getOrNull(idx)
                } else null
                prefetchNext(upcoming)
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                val aligned = alignedDelayMs(durMs, next.syncRef)
                cancelScheduled()
                // If load succeeded, the ping was already started inside loadAnimatedOrStatic
                scheduledRotation = Runnable { showAndSchedule() }
                imageView.postDelayed(scheduledRotation!!, aligned)
            }
        }
    }
    // assign function reference to break forward-declaration cycle
    showNext = { showAndSchedule() }
    manualNext = { cancelScheduled(); showAndSchedule() }
    manualPrev = {
        cancelScheduled()
        if (state.items.isNotEmpty()) {
            state.index = if (state.index - 2 >= 0) state.index - 2 else (state.items.size + state.index - 2) % state.items.size
        }
        showAndSchedule()
    }

    fun applyNewList(all: List<com.pizzahut.tv.api.PlaylistItem>?) {
        val filtered = filterBySchedule(all ?: emptyList())
        val prevItems = state.items
        val prevFiles = prevItems.mapNotNull { it.file }
        val newFiles = filtered.mapNotNull { it.file }
        // If first assignment or previously empty, initialize
        if (prevItems.isEmpty()) {
            state.items = if (filtered.isEmpty()) emptyList() else filtered
            state.index = 0
            return
        }
        // If list content changed OR item IDs changed for same files, replace but preserve current position relative to current file.
        var idsChangedForSameFiles = false
        if (newFiles == prevFiles) {
            // Build file->id maps to detect when a server recreated an item (new id but same file)
            val prevMap = prevItems.associate { (it.file ?: "") to (it.id ?: "") }
            val newMap = filtered.associate { (it.file ?: "") to (it.id ?: "") }
            // If any file that exists in both maps has a different id, treat as a change
            idsChangedForSameFiles = newFiles.any { f -> (prevMap[f] ?: "") != (newMap[f] ?: "") }
        }
        if (newFiles != prevFiles || idsChangedForSameFiles) {
            val cur = currentItemFile
            state.items = filtered
            state.index = if (cur != null) {
                val idx = filtered.indexOfFirst { it.file == cur }
                if (idx >= 0) (idx + 1) % (filtered.size.coerceAtLeast(1)) else 0
            } else 0
            return
        }
        // No change: keep current list and index
    }

    fun fetchPlaylist() {
        binding.message.text = "Fetching playlist..."
        lifecycleScope.launch {
            try {
                val resp = ApiClient.service.getPlaylist(storeId, screenId)
                val original = resp.playlist ?: emptyList()
                // Mirror web orientation/rotation if provided by backend
                try {
                    orientationMode = resp.orientation?.lowercase() ?: orientationMode
                    displayRotation = resp.rotation ?: displayRotation
                    applyOrientationTransform()
                } catch (_: Exception) {}
                originalItems = original
                // Apply without resetting index if files are the same
                applyNewList(original)
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "playlist_reload")) } catch (_: Exception) {}
                }
                val cnt = state.items.size
                if (cnt > 0) {
                    binding.message.text = "${cnt} items loaded"
                    // If rotation hasn’t started or was cancelled, kick it off
                    if (scheduledRotation == null || currentItemFile == null || (imageView.drawable == null && playerView.visibility != ImageView.VISIBLE)) {
                        showAndSchedule()
                    }
                } else {
                    binding.message.text = if (original.isNotEmpty()) "No items currently scheduled" else "No items in playlist"
                }
            } catch (e: Exception) {
                binding.message.text = "Network error: ${e.message}".take(60)
            } finally {
                imageView.postDelayed({ fetchPlaylist() }, refreshIntervalMs)
            }
        }
    }

    fetchPlaylist()

    // (Release now handled in onDestroy)
}
