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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    com.pizzahut.tv.api.PairCodeHolder.init(applicationContext)
        binding = ActivityTvDisplayBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.message.text = "Loading playlist..."

        // Create / attach image & video containers
        val imageView = ImageView(this).apply {
            setBackgroundColor(Color.BLACK)
            adjustViewBounds = true
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            scaleType = ImageView.ScaleType.MATRIX // we'll control crop for split mode
        }
        // ExoPlayer-based video surface (replaces VideoView for faster start & caching)
        val playerView = com.google.android.exoplayer2.ui.StyledPlayerView(this).apply {
            setBackgroundColor(Color.BLACK)
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            useController = false
            visibility = ImageView.GONE
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
            debugOverlay?.text = ("Base: " + ApiClient.baseUrl).take(60)
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
    val storeId = intent.getStringExtra("storeId") ?: prefs.getString("storeId", null) ?: "0000"
    val screenId = intent.getStringExtra("screenId") ?: prefs.getString("screenId", null) ?: "screen1"

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

    fun applySplitCropForImage(item: com.pizzahut.tv.api.PlaylistItem) {
        try {
            val s = item.syncRef
            val mode = s?.mode?.lowercase() ?: ""
            val order = (s?.order ?: 0).coerceAtLeast(0)
            val count = (s?.count ?: 0)
            // Reset
            imageView.imageMatrix = android.graphics.Matrix()
            if (mode == "split-h" && count > 1) {
                // Compute pan so that we show only the segment [order/count] horizontally
                val w = imageView.width.takeIf { it > 0 } ?: binding.root.width
                val h = imageView.height.takeIf { it > 0 } ?: binding.root.height
                if (w > 0 && h > 0) {
                    // Scale to cover then translate horizontally
                    val d = imageView.drawable ?: return
                    val dw = d.intrinsicWidth.toFloat()
                    val dh = d.intrinsicHeight.toFloat()
                    if (dw > 0 && dh > 0) {
                        val scale = maxOf(w / dw, h / dh)
                        val segW = w.toFloat()
                        val totalW = segW * count
                        val centerX = (order + 0.5f) * segW
                        val targetX = centerX - (w / 2f)
                        val m = android.graphics.Matrix()
                        m.setScale(scale, scale)
                        // Translate so that the visible window starts at targetX in the scaled space
                        val scaledW = dw * scale
                        val maxOffset = (scaledW - totalW).coerceAtLeast(0f)
                        val offset = (targetX / totalW) * maxOffset
                        m.postTranslate(-offset, (h - dh * scale) / 2f)
                        imageView.imageMatrix = m
                    }
                }
            }
        } catch (_: Exception) {}
    }

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
                    applySplitCropForImage(originalItems.find { it.id == itemId } ?: originalItems.firstOrNull { it.file == file } ?: com.pizzahut.tv.api.PlaylistItem(id=null,file=file, url=null, enabled=true, duration=10, repeat=true, linkNext=false, start=null, end=null, schedule= emptyList(), days= emptyList(), mediaType="image", syncRef=null))
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
                        applySplitCropForImage(originalItems.find { it.id == itemId } ?: originalItems.firstOrNull { it.file == file } ?: com.pizzahut.tv.api.PlaylistItem(id=null,file=file, url=null, enabled=true, duration=10, repeat=true, linkNext=false, start=null, end=null, schedule= emptyList(), days= emptyList(), mediaType="image", syncRef=null))
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
                    applySplitCropForImage(originalItems.find { it.id == itemId } ?: originalItems.firstOrNull { it.file == file } ?: com.pizzahut.tv.api.PlaylistItem(id=null,file=file, url=null, enabled=true, duration=10, repeat=true, linkNext=false, start=null, end=null, schedule= emptyList(), days= emptyList(), mediaType="image", syncRef=null))
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
        val okClient = okhttp3.OkHttpClient.Builder().build()
        val okFactory = com.google.android.exoplayer2.ext.okhttp.OkHttpDataSource.Factory(okClient)
        val upstream = com.google.android.exoplayer2.upstream.DefaultDataSource.Factory(this, okFactory)
        cacheDataSourceFactory = com.google.android.exoplayer2.upstream.cache.CacheDataSource.Factory()
            .setCache(simpleCache)
            .setUpstreamDataSourceFactory(upstream)
            .setFlags(com.google.android.exoplayer2.upstream.cache.CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
        val renderersFactory = com.google.android.exoplayer2.DefaultRenderersFactory(this)
            .setEnableDecoderFallback(true)
            .setExtensionRendererMode(com.google.android.exoplayer2.DefaultRenderersFactory.EXTENSION_RENDERER_MODE_OFF)
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
    // Compute ms until the next cadence boundary for a sync group; returns null if no sync
    fun msUntilNextSyncBoundary(item: com.pizzahut.tv.api.PlaylistItem?): Long? {
        val start = item?.syncRef?.startEpoch ?: return null
        val durSec = (item.duration ?: 10).coerceAtLeast(1)
        val nowMs = System.currentTimeMillis()
        val startMs = start * 1000L
        if (nowMs < startMs) return (startMs - nowMs).coerceAtLeast(0L)
        val d = durSec * 1000L
        val elapsed = (nowMs - startMs) % d
        val remain = d - elapsed
        return remain.coerceAtLeast(0L)
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
            // Prefer /media (range streaming) for videos; fallback to static if needed
            val videoUrlPrimary = ApiClientImageHelper.buildVideoUrl(file)
            val videoUrlFallback = if (!next.url.isNullOrBlank() && next.url!!.startsWith("http", true)) next.url!! else ApiClientImageHelper.buildImageUrl(file)
            binding.message.text = "VID ${file.take(18)}"
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
                    vv.setVideoURI(Uri.parse(videoUrlFallback))
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
                        // Schedule rotation according to playlist duration, aligned to sync cadence if provided
                        val defaultDurMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                        val alignMs = msUntilNextSyncBoundary(next)
                        cancelScheduled()
                        scheduledRotation = Runnable {
                            try { vv.stopPlayback() } catch (_: Exception) {}
                            vv.visibility = ImageView.GONE
                            showAndSchedule()
                        }
                        vv.postDelayed(scheduledRotation!!, (alignMs ?: defaultDurMs))
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
                                // Apply split crop by translating the video surface within the playerView
                                try {
                                    val s = next.syncRef
                                    val mode = s?.mode?.lowercase() ?: ""
                                    val order = (s?.order ?: 0).coerceAtLeast(0)
                                    val count = (s?.count ?: 0)
                                    if (mode == "split-h" && count > 1) {
                                        val segWidth = playerView.width
                                        if (segWidth > 0) {
                                            val total = segWidth * count
                                            val centerX = (order + 0.5f) * segWidth
                                            val target = centerX - (segWidth / 2f)
                                            // Use content frame translation to pan horizontally over a larger virtual canvas
                                            val content = playerView.videoSurfaceView ?: playerView
                                            content.translationX = -target
                                            // Scale to cover height if needed
                                            content.scaleX = count.toFloat()
                                            content.pivotX = 0f
                                        }
                                    } else {
                                        val content = playerView.videoSurfaceView ?: playerView
                                        content.translationX = 0f
                                        content.scaleX = 1f
                                    }
                                } catch (_: Exception) {}
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
                            binding.message.text = ("Err ${error.errorCodeName}" + (error.message?.let { ":"+it.take(20) } ?: "")).take(60)
                            val playerRef = exoPlayer ?: return
                            lifecycleScope.launch(Dispatchers.IO) {
                                try { ApiClient.service.postClientEvent(com.pizzahut.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = f, itemId = next.id, error = error.message)) } catch (_: Exception) {}
                            }
                            // First error: try static fallback path once
                            if (!triedStaticFallbackForCurrent) {
                                triedStaticFallbackForCurrent = true
                                try {
                                    playerRef.clearMediaItems()
                                    playerRef.setMediaSource(buildMediaSource(if (!next.url.isNullOrBlank() && next.url!!.startsWith("http", true)) next.url!! else ApiClientImageHelper.buildImageUrl(f)))
                                    playerRef.prepare(); playerRef.playWhenReady = true
                                    binding.message.text = ("StaticFB ${f.take(10)}").take(60)
                    // Don't report success yet; wait for READY state to confirm
                                    return
                                } catch (_: Exception) { /* fall through */ }
                            }
                            // Second failure: skip to next instead of legacy unless explicit fallback needed
                            cancelScheduled()
                            // Mild delay to avoid tight loop
                            playerView.postDelayed({ showAndSchedule() }, 500)
                        }
                    })
                    playerListenersAttached = true
                }
                player.setMediaSource(buildMediaSource(videoUrlPrimary))
                player.prepare(); player.playWhenReady = true
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
                                playerRef.setMediaSource(buildMediaSource(if (!next.url.isNullOrBlank() && next.url!!.startsWith("http", true)) next.url!! else ApiClientImageHelper.buildImageUrl(file)))
                                playerRef.prepare(); playerRef.playWhenReady = true
                                binding.message.text = ("StaticFB ${file.take(10)}").take(60)
                            } catch (_: Exception) {
                                cancelScheduled(); playerView.postDelayed({ showAndSchedule() }, 300)
                            }
                        } else {
                            cancelScheduled(); playerView.postDelayed({ showAndSchedule() }, 300)
                        }
                    }
                }
                playerView.postDelayed(videoStallWatch!!, 8_000L)
                // Schedule rotation based on playlist duration, align to cadence when available
                val defaultDurMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                val alignMs = msUntilNextSyncBoundary(next)
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
                playerView.postDelayed(scheduledRotation!!, (alignMs ?: defaultDurMs))
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
                val defaultDurMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                val alignMs = msUntilNextSyncBoundary(next)
                cancelScheduled()
                // If load succeeded, the ping was already started inside loadAnimatedOrStatic
                scheduledRotation = Runnable { showAndSchedule() }
                imageView.postDelayed(scheduledRotation!!, (alignMs ?: defaultDurMs))
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
                val resp = ApiClient.service.getPlaylist(storeId, screenId, com.pizzahut.tv.api.PairCodeHolder.codeOrNull())
                val original = resp.playlist ?: emptyList()
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
