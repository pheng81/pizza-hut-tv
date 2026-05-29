package com.everydayadvertise.tv

import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.widget.ImageView
import android.widget.VideoView // legacy kept until fully removed
import android.view.ViewGroup
import android.view.TextureView
import android.view.SurfaceView
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.everydayadvertise.tv.api.ApiClient
import com.everydayadvertise.tv.databinding.ActivityTvDisplayBinding
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
import android.view.View
import androidx.activity.OnBackPressedCallback
import android.widget.TextView
import android.content.Intent
import java.io.File
import java.util.Date
import java.util.Calendar
import java.text.SimpleDateFormat
import java.util.Locale
import com.everydayadvertise.tv.api.HeartbeatReq

class TvDisplayActivity : AppCompatActivity() {
    // Made public so extension functions can access
    lateinit var binding: ActivityTvDisplayBinding
    // ExoPlayer instance (initialized lazily within playlist loop). Not private so extension function can access.
    var exoPlayer: com.google.android.exoplayer2.ExoPlayer? = null
    // Keep a reference to legacy VideoView so we can hide/stop it properly
    var legacyVideoView: VideoView? = null
    // WebView used for YouTube IFrame embeds
    var youTubeWebView: android.webkit.WebView? = null
    // Small persistent debug overlay
    var debugOverlay: TextView? = null
    // Manual controls hooks
    var manualNext: (() -> Unit)? = null
    var manualPrev: (() -> Unit)? = null
    private var heartbeatJob: Job? = null
    private var hbIndicator: TextView? = null
    // Periodic per-item OK ping so dashboard lights stay green while item is displayed
    private var itemOkPingJob: Job? = null
    // Track current rotation and orientation to detect dashboard changes
    var currentRotation: Int = 0
    var currentOrientation: String = "default"
    // Screen-level mute flag — toggled from the mobile app's speaker button
    var screenMuted: Boolean = false
    // Store references to media views for rotation
    var mainImageView: ImageView? = null
    // Secondary image view to enable crossfade transitions (Pi-style dissolve)
    var secondaryImageView: ImageView? = null
    // Track which image view is on top for crossfade
    private var usePrimaryAsFront: Boolean = true
    var mainPlayerView: SurfaceView? = null
    // Simple full-screen overlay to provide a quick fade reveal between items
    var transitionOverlay: View? = null

    // Helper to pre-rotate and scale bitmap to fill screen (like Pi client)
    fun prepareRotatedBitmap(original: Bitmap, degrees: Int): Bitmap {
        if (degrees == 0) return original
        
        return try {
            val matrix = android.graphics.Matrix()
            matrix.postRotate(degrees.toFloat())
            
            // Create rotated bitmap
            val rotated = Bitmap.createBitmap(original, 0, 0, original.width, original.height, matrix, true)
            
            android.util.Log.d("TvDisplayActivity", "Pre-rotated bitmap: ${original.width}x${original.height} -> ${rotated.width}x${rotated.height}, rotation=$degrees°")
            rotated
        } catch (e: Exception) {
            android.util.Log.e("TvDisplayActivity", "Failed to rotate bitmap", e)
            original
        }
    }

    fun applyRotation(degrees: Int) {
        // For video views, apply View rotation (ExoPlayer handles it well)
        // For images, we pre-rotate the bitmap instead of rotating the view
        runOnUiThread {
            try {
                mainPlayerView?.rotation = degrees.toFloat()
                android.util.Log.d("TvDisplayActivity", "Applied video rotation: $degrees°")
                debugOverlay?.text = "Rotation: $degrees°"
                debugOverlay?.postDelayed({ debugOverlay?.text = "" }, 3000)
            } catch (e: Exception) {
                android.util.Log.e("TvDisplayActivity", "Failed to apply rotation", e)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    com.everydayadvertise.tv.api.PairCodeHolder.init(applicationContext)
        binding = ActivityTvDisplayBinding.inflate(layoutInflater)
        setContentView(binding.root)
        // Keep the screen awake during playback
        try { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) } catch (_: Exception) {}
        binding.message.text = "Loading playlist..."

        // Create / attach image & video containers
        val imageView = ImageView(this).apply {
            setBackgroundColor(Color.BLACK)
            adjustViewBounds = false
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            scaleType = ImageView.ScaleType.CENTER_CROP
        }
        mainImageView = imageView  // Store reference for rotation
        // Create a second ImageView stacked identically for crossfades
        val imageView2 = ImageView(this).apply {
            setBackgroundColor(Color.BLACK)
            adjustViewBounds = false
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            scaleType = ImageView.ScaleType.CENTER_CROP
            alpha = 0f
            visibility = View.GONE
        }
        secondaryImageView = imageView2
        // ExoPlayer-based video surface using SurfaceView (more stable on many Android TV builds)
        val playerView = SurfaceView(this).apply {
            // Keep background on underlying imageView/root instead
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            visibility = ImageView.GONE
        }
        mainPlayerView = playerView  // Store reference for rotation
        try {
            // Allow message/debug overlays to render above SurfaceView
            playerView.setZOrderMediaOverlay(true)
        } catch (_: Exception) {}
    // Add media views behind the existing status message (index 0 => back)
    binding.root.addView(playerView, 0)
    // Add both image layers under the message; order ensures they sit behind overlays
    binding.root.addView(imageView2, 0)
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
            debugOverlay?.postDelayed({ 
                debugOverlay?.animate()?.alpha(0f)?.setDuration(600)?.withEndAction {
                    binding.root.removeView(debugOverlay)
                    debugOverlay = null
                }
            }, 3000)
        } catch (_: Exception) {}

        // Small heartbeat indicator (top-right) - DISABLED
        // hbIndicator = TextView(this).apply {
        //     text = "HB..."
        //     setTextColor(Color.YELLOW)
        //     textSize = 12f
        //     setBackgroundColor(0x33000000)
        //     setPadding(12, 6, 12, 6)
        // }
        // val hbParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        // (hbParams as? ViewGroup.MarginLayoutParams)?.let { it.rightMargin = 16; it.topMargin = 8 }
        // binding.root.addView(hbIndicator, hbParams)

        // Create a black overlay view we can briefly fade out to smooth transitions
        transitionOverlay = View(this).apply {
            setBackgroundColor(Color.BLACK)
            alpha = 0f
            visibility = View.GONE
        }
        val overlayFullParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        binding.root.addView(transitionOverlay, overlayFullParams)

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
        youTubeWebView?.let { try { it.loadUrl("about:blank"); it.removeAllViews() } catch (_: Exception) {}; it.visibility = android.view.View.GONE }
        super.onDestroy()
    }

    // Quick reveal: show a black overlay and fade it out rapidly to hide visual pops between items.
    // Keep this short to avoid disturbing sync logic. Called when the next item is ready to display.
    fun revealWithQuickFade(totalMs: Long = 250L) {
        val v = transitionOverlay ?: return
        runOnUiThread {
            try {
                v.animate()?.cancel()
                v.alpha = 1f
                v.visibility = View.VISIBLE
                v.bringToFront()
                v.animate().alpha(0f).setDuration(totalMs).withEndAction {
                    try { v.visibility = View.GONE } catch (_: Exception) {}
                }
            } catch (_: Exception) {}
        }
    }

    // Pi-style transitions with effects: crossfade, slide, zoom between two stacked ImageViews
    fun crossfadeToImage(setupFront: (ImageView) -> Unit, rotationDegrees: Float = 0f, durationMs: Long = 600L, effect: String? = null) {
        val a = mainImageView
        val b = secondaryImageView
        if (a == null || b == null) return
        // Decide which view becomes the new front layer
        val (front, back) = if (usePrimaryAsFront) Pair(b, a) else Pair(a, b)
        try {
            // Cancel any running animations and reset leftover transform state on both views
            try { front.animate().cancel() } catch (_: Exception) {}
            try { back.animate().cancel() } catch (_: Exception) {}
            front.translationX = 0f; front.translationY = 0f
            front.scaleX = 1f; front.scaleY = 1f; front.alpha = 0f
            back.translationX = 0f; back.translationY = 0f
            back.scaleX = 1f; back.scaleY = 1f; back.alpha = 1f

            // Prepare front with new content
            setupFront(front)
            // Apply rotation to view layer for animated assets; for static bitmaps we pre-rotate so keep 0
            try { front.rotation = rotationDegrees } catch (_: Exception) {}

            // Use parent/root dimensions for slides so width is never 0 (views may be GONE when measured)
            val rootW = try { (front.parent as? android.view.View)?.width?.takeIf { it > 0 } ?: front.rootView.width } catch (_: Exception) { 1920 }
            val rootH = try { (front.parent as? android.view.View)?.height?.takeIf { it > 0 } ?: front.rootView.height } catch (_: Exception) { 1080 }

            // Apply transition effect based on effect parameter
            val effectName = (effect ?: "fade").lowercase()
            when {
                effectName.contains("slide-l") || effectName.contains("slide_l") || effectName == "slide-left" -> {
                    // New image slides in from right; old image slides out to left
                    front.alpha = 1f
                    front.translationX = rootW.toFloat()
                    front.visibility = View.VISIBLE
                    front.animate().translationX(0f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                        back.translationX = 0f
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().translationX(-rootW.toFloat()).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName.contains("slide-r") || effectName.contains("slide_r") || effectName == "slide-right" -> {
                    // New image slides in from left; old image slides out to right
                    front.alpha = 1f
                    front.translationX = -rootW.toFloat()
                    front.visibility = View.VISIBLE
                    front.animate().translationX(0f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                        back.translationX = 0f
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().translationX(rootW.toFloat()).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName.contains("slide-up") || effectName.contains("slide_up") -> {
                    // New image slides in from bottom; old image slides out upward
                    front.alpha = 1f
                    front.translationY = rootH.toFloat()
                    front.visibility = View.VISIBLE
                    front.animate().translationY(0f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                        back.translationY = 0f
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().translationY(-rootH.toFloat()).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName.contains("slide-down") || effectName.contains("slide_down") -> {
                    // New image slides in from top; old image slides out downward
                    front.alpha = 1f
                    front.translationY = -rootH.toFloat()
                    front.visibility = View.VISIBLE
                    front.animate().translationY(0f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                        back.translationY = 0f
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().translationY(rootH.toFloat()).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName.contains("zoom-in") || effectName.contains("zoom_in") -> {
                    // Zoom in from 80% to 100%
                    front.scaleX = 0.8f
                    front.scaleY = 0.8f
                    front.alpha = 0f
                    front.visibility = View.VISIBLE
                    front.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().alpha(0f).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName.contains("zoom-out") || effectName.contains("zoom_out") -> {
                    // Zoom out from 120% to 100%
                    front.scaleX = 1.2f
                    front.scaleY = 1.2f
                    front.alpha = 0f
                    front.visibility = View.VISIBLE
                    front.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                    }.start()
                    if (back.visibility == View.VISIBLE && back.drawable != null) {
                        back.animate().alpha(0f).setDuration(durationMs).start()
                    } else {
                        back.visibility = View.GONE
                    }
                }
                effectName == "cut" -> {
                    // Instant cut — no animation
                    front.alpha = 1f
                    front.visibility = View.VISIBLE
                    try { back.setImageDrawable(null) } catch (_: Exception) {}
                    back.visibility = View.GONE
                }
                else -> {
                    // Default: fade / dissolve
                    front.alpha = 0f
                    front.visibility = View.VISIBLE
                    if (back.drawable == null) {
                        back.visibility = View.GONE
                    } else {
                        back.visibility = View.VISIBLE
                        back.alpha = 1f
                    }
                    front.animate().alpha(1f).setDuration(durationMs).withEndAction {
                        try { back.setImageDrawable(null) } catch (_: Exception) {}
                        back.visibility = View.GONE
                    }.start()
                    if (back.visibility == View.VISIBLE) {
                        back.animate().alpha(0f).setDuration(durationMs).start()
                    }
                }
            }
            usePrimaryAsFront = !usePrimaryAsFront
            // Keep overlays above images
            try { binding.message.bringToFront() } catch (_: Exception) {}
            try { debugOverlay?.bringToFront() } catch (_: Exception) {}
            try { transitionOverlay?.bringToFront() } catch (_: Exception) {}
        } catch (_: Exception) {}
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
                        com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)
                    )
                } catch (_: Exception) {}
                try { delay(25_000) } catch (_: Exception) { break }
            }
        }
    }

    private fun startHeartbeatLoop(storeId: String, screenId: String) {
        heartbeatJob?.cancel()
        heartbeatJob = lifecycleScope.launch(Dispatchers.IO) {
            // Get persistent device ID
            val deviceId = com.everydayadvertise.tv.api.DeviceIdHelper.get(applicationContext)
            while (isActive) {
                try {
                    ApiClient.service.sendHeartbeat(HeartbeatReq(
                        storeId = storeId, 
                        screenId = screenId,
                        deviceId = deviceId
                    ))
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

    // Mirror backup Pi client's schedule logic exactly (mm/dd/yyyy parsing, numeric weekdays)
    fun filterBySchedule(items: List<com.everydayadvertise.tv.api.PlaylistItem>): List<com.everydayadvertise.tv.api.PlaylistItem> {
        if (items.isEmpty()) return emptyList()
        // Use server-synced time (parity with backup) so schedule windows flip correctly regardless of device clock
        val serverNowMs = try { com.everydayadvertise.tv.sync.ServerTimeSync.getServerSyncedTime() } catch (_: Exception) { System.currentTimeMillis() }
        val nowDate = Date(serverNowMs)
        val now = Calendar.getInstance().apply { time = nowDate }
        val curDayNum = when (now.get(Calendar.DAY_OF_WEEK)) {
            Calendar.MONDAY -> 1
            Calendar.TUESDAY -> 2
            Calendar.WEDNESDAY -> 3
            Calendar.THURSDAY -> 4
            Calendar.FRIDAY -> 5
            Calendar.SATURDAY -> 6
            else -> 7
        }

        fun parseDashboardTime(v: String?): Date? {
            if (v.isNullOrBlank()) return null
            val t = v.trim()
            // Time only formats HH:MM or HH:MM:SS
            if (":" in t && !t.contains("/") && !t.contains("-")) {
                val parts = t.split(":")
                val h = parts.getOrNull(0)?.toIntOrNull() ?: 0
                val m = parts.getOrNull(1)?.toIntOrNull() ?: 0
                val s = parts.getOrNull(2)?.toIntOrNull() ?: 0
                val c = Calendar.getInstance().apply { time = nowDate }
                c.set(Calendar.HOUR_OF_DAY, h); c.set(Calendar.MINUTE, m); c.set(Calendar.SECOND, s); c.set(Calendar.MILLISECOND, 0)
                return c.time
            }
            // US date-only mm/dd/yyyy
            if (t.length == 10 && t[2] == '/' && t[5] == '/') {
                return try { SimpleDateFormat("MM/dd/yyyy", Locale.US).parse(t) } catch (_: Exception) { null }
            }
            // Full datetime mm/dd/yyyy HH:MM:SS or HH:MM
            arrayOf("MM/dd/yyyy HH:mm:ss", "MM/dd/yyyy HH:mm").forEach { fmt ->
                try { return SimpleDateFormat(fmt, Locale.US).parse(t) } catch (_: Exception) {}
            }
            // ISO fallbacks
            arrayOf("yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm", "yyyy-MM-dd HH:mm").forEach { fmt ->
                try { return SimpleDateFormat(fmt, Locale.US).parse(t) } catch (_: Exception) {}
            }
            return null
        }

        fun dayListMatches(days: List<String>?): Boolean {
            if (days.isNullOrEmpty()) return true
            // Support both numeric [1..7] and text [mon..sun]
            val nums = days.mapNotNull { d ->
                val dd = d.trim().lowercase(Locale.US)
                when {
                    dd.toIntOrNull() != null -> dd.toIntOrNull()
                    dd.startsWith("mon") -> 1
                    dd.startsWith("tue") -> 2
                    dd.startsWith("wed") -> 3
                    dd.startsWith("thu") -> 4
                    dd.startsWith("fri") -> 5
                    dd.startsWith("sat") -> 6
                    dd.startsWith("sun") -> 7
                    else -> null
                }
            }
            return nums.isEmpty() || nums.contains(curDayNum)
        }

        fun windowActive(s: String?, e: String?, days: List<String>?): Boolean {
            if (!dayListMatches(days)) return false
            if (s.isNullOrBlank() && e.isNullOrBlank()) return true
            val start = parseDashboardTime(s)
            var end = parseDashboardTime(e)
            val nowTime = nowDate
            // Debug schedule window evaluation
            try {
                android.util.Log.d(
                    "TvDisplayActivity",
                    "windowActive s=${s ?: "-"} e=${e ?: "-"} days=${days?.joinToString() ?: "-"} now=${now.time} -> start=${start?.time ?: "-"} end=${end?.time ?: "-"}"
                )
            } catch (_: Exception) {}
            fun isTimeOnly(v: String?): Boolean = v != null && ":" in v && !v.contains('/') && !v.contains('-')
            fun isDateOnly(v: String?): Boolean = v != null && v.length == 10 && v[2] == '/' && v[5] == '/'
            // Normalize date-only boundaries to be INCLUSIVE of the full end day
            if (!e.isNullOrBlank() && isDateOnly(e) && end != null) {
                val c = Calendar.getInstance().apply { time = end }
                // Add 1 second to make the comparison inclusive of 23:59:59
                c.set(Calendar.HOUR_OF_DAY, 23); c.set(Calendar.MINUTE, 59); c.set(Calendar.SECOND, 59); c.set(Calendar.MILLISECOND, 999)
                c.add(Calendar.MILLISECOND, 1)
                end = c.time
            }
            if (!s.isNullOrBlank() && isDateOnly(s) && e.isNullOrBlank() && start != null) {
                val c = Calendar.getInstance().apply { time = start }
                // Add 1 second to make single-date end inclusive
                c.set(Calendar.HOUR_OF_DAY, 23); c.set(Calendar.MINUTE, 59); c.set(Calendar.SECOND, 59); c.set(Calendar.MILLISECOND, 999)
                c.add(Calendar.MILLISECOND, 1)
                end = c.time
            }
            if (start != null && end != null) {
                if (end.before(start)) {
                    // Overnight wrap for time-only window (inclusive boundaries)
                    return if (isTimeOnly(s) || isTimeOnly(e)) {
                        // Time-only: after/equal start OR before/equal end
                        (nowTime.after(start) || nowTime == start) || (nowTime.before(end) || nowTime == end)
                    } else {
                        val c = Calendar.getInstance().apply { time = end }; c.add(Calendar.DATE, 1)
                        val endPlus = c.time
                        (nowTime.after(start) || nowTime == start) && (nowTime.before(endPlus) || nowTime == endPlus)
                    }
                }
                // Normal range: INCLUSIVE on both boundaries
                return (nowTime.after(start) || nowTime == start) && (nowTime.before(end) || nowTime == end)
            }
            if (start != null && nowTime.before(start)) return false
            if (end != null && nowTime.after(end)) return false
            return true
        }

        val out = ArrayList<com.everydayadvertise.tv.api.PlaylistItem>()
        for (it in items) {
            if (it.enabled == false) continue
            val windows = it.schedule ?: emptyList()
            val active = if (windows.isNotEmpty()) {
                windows.any { w -> windowActive(w.start, w.end, w.days) }
            } else {
                // Legacy single window
                if (!it.start.isNullOrBlank() || !it.end.isNullOrBlank() || !it.days.isNullOrEmpty()) {
                    windowActive(it.start, it.end, it.days)
                } else true
            }
            if (active) out.add(it)
        }
        return out
    }
}

object ApiClientImageHelper {
    private fun isAbsolute(u: String?): Boolean = u != null && (u.startsWith("http://", ignoreCase = true) || u.startsWith("https://", ignoreCase = true))
    fun buildImageUrl(filename: String): String = if (isAbsolute(filename)) filename else ApiClient.baseUrl + "static/uploads/" + filename
    fun buildVideoUrl(filename: String): String = if (isAbsolute(filename)) filename else ApiClient.baseUrl + "media/" + filename // new ranged streaming endpoint
    // Unified builder used by loadAnimatedOrStatic (images & animated assets live in static/uploads)
    fun buildFileUrl(filename: String): String = if (isAbsolute(filename)) filename else buildImageUrl(filename)
    // Some deployments serve uploads at /uploads instead of /static/uploads; use as a fallback
    fun buildImageUrlAlt(filename: String): String = if (isAbsolute(filename)) filename else ApiClient.baseUrl + "uploads/" + filename
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

// Fetch and decode bitmap with safe downsampling to prevent "Canvas: trying to draw too large bitmap" crashes.
// Large images from playlists (high-res marketing assets, etc.) can exceed Canvas draw limits (~100MB for some devices).
// This implementation:
// 1. Reads the image bytes into memory.
// 2. Probes bounds using inJustDecodeBounds to determine original dimensions.
// 3. Computes a power-of-two inSampleSize based on device screen size (we use 2x screen as a reasonable upper bound).
// 4. Decodes with downsampling and RGB_565 config for memory efficiency.
// 5. Catches OOM and retries with more aggressive downsampling if needed.
// The downsampled bitmap is cached in the in-memory LRU cache for reuse.
suspend fun fetchBitmap(urlStr: String): android.graphics.Bitmap? = withContext(Dispatchers.IO) {
    ImageMemoryCache.get(urlStr)?.let { return@withContext it }
    // Retry up to 2 times with modest backoff to handle transient network
    var attempt = 0
    var lastBmp: android.graphics.Bitmap? = null
    while (attempt < 2 && lastBmp == null) {
        attempt += 1
        try {
            val url = URL(urlStr)
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 7000
            conn.readTimeout = 10000
            conn.instanceFollowRedirects = true
            conn.useCaches = false
            conn.setRequestProperty("Cache-Control", "no-cache")
            conn.inputStream.use { inp ->
            // Read into memory so we can probe bounds and decode with sampling.
            val bytes = try { inp.readBytes() } catch (e: Exception) { return@withContext null }

            // First pass: decode bounds only to determine original size
            val boundsOpts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, boundsOpts)
            val outW = boundsOpts.outWidth
            val outH = boundsOpts.outHeight
            if (outW <= 0 || outH <= 0) return@withContext null

            // Target size: base on device screen to avoid allocating massively large bitmaps.
            val metrics = android.content.res.Resources.getSystem().displayMetrics
            val reqW = (metrics.widthPixels.coerceAtLeast(1) * 2) // allow up to 2x screen for some layouts
            val reqH = (metrics.heightPixels.coerceAtLeast(1) * 2)

            // Compute a power-of-two inSampleSize
            var inSampleSize = 1
            while (outW / inSampleSize > reqW || outH / inSampleSize > reqH) {
                inSampleSize = inSampleSize shl 1
            }

            val decodeOpts = BitmapFactory.Options().apply {
                this.inSampleSize = inSampleSize
                // Prefer a memory-friendly config for large images
                inPreferredConfig = Bitmap.Config.RGB_565
            }

            // Second pass: decode a downsampled bitmap
            val bmp = try {
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decodeOpts)
            } catch (oom: OutOfMemoryError) {
                // Try a more aggressive downsample if we OOM
                try {
                    decodeOpts.inSampleSize = decodeOpts.inSampleSize shl 1
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decodeOpts)
                } catch (_: Throwable) { null }
            } catch (e: Exception) { null }

            if (bmp != null) ImageMemoryCache.put(urlStr, bmp)
            lastBmp = bmp
        }
        } catch (_: Exception) {
            // backoff
            try { Thread.sleep((attempt * 250).toLong()) } catch (_: Exception) {}
        }
    }
    lastBmp
}

// --- Rotation & periodic fetching helpers ---
private data class ActivePlaylist(var items: List<com.everydayadvertise.tv.api.PlaylistItem>, var index: Int = 0)

private fun TvDisplayActivity.startPlaylistLoop(storeId: String, screenId: String, imageView: ImageView, playerView: SurfaceView) {
    val state = ActivePlaylist(emptyList())
    var originalItems: List<com.everydayadvertise.tv.api.PlaylistItem> = emptyList()
    val refreshIntervalMs = 5_000L // refresh playlist every 5s for quicker backend responses
    fun pickNext(): com.everydayadvertise.tv.api.PlaylistItem? {
        if (state.items.isEmpty()) return null
        if (state.index >= state.items.size) state.index = 0
        return state.items[state.index++]
    }

    fun prefetchNext(nextItem: com.everydayadvertise.tv.api.PlaylistItem?) {
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

    fun loadAnimatedOrStatic(file: String, itemId: String?, preferredUrl: String?, effect: String?, onDone: (Boolean) -> Unit) {
        // Build a list of candidate URLs; try preferred (absolute or relative), then static/uploads, then uploads
        val candidates = mutableListOf<String>()
        if (!preferredUrl.isNullOrBlank()) {
            if (preferredUrl.startsWith("http", true)) {
                candidates.add(preferredUrl)
            } else {
                // Treat as relative to baseUrl
                val rel = preferredUrl.trim().trimStart('/')
                try { candidates.add(ApiClient.baseUrl + rel) } catch (_: Exception) {}
            }
        }
        candidates.add(ApiClientImageHelper.buildFileUrl(file))
        candidates.add(ApiClientImageHelper.buildImageUrlAlt(file))
        // Deduplicate in case different builders produce same URL
        val tried = candidates.distinct().toMutableList()
        var usedUrl: String? = null
        lifecycleScope.launch {
            if (isAnimated(file) && android.os.Build.VERSION.SDK_INT >= 28) {
                    var drawable: AnimatedImageDrawable? = null
                    for (u in tried) {
                        val d = withContext(Dispatchers.IO) {
                            try {
                                val conn = (URL(u).openConnection() as HttpURLConnection).apply {
                                    connectTimeout = 7000; readTimeout = 10000
                                }
                                conn.inputStream.use { inp ->
                                    val bytes = inp.readBytes()
                                    val source = ImageDecoder.createSource(bytes)
                                // Avoid decoding full-resolution animated frames which can be enormous.
                                val metrics = android.content.res.Resources.getSystem().displayMetrics
                                val reqW = (metrics.widthPixels.coerceAtLeast(1) * 2)
                                val reqH = (metrics.heightPixels.coerceAtLeast(1) * 2)
                                    try {
                                        ImageDecoder.decodeDrawable(source) { decoder, info, _ ->
                                        // Downsample large animated images to a reasonable target size.
                                        decoder.setTargetSize(reqW, reqH)
                                        // Prefer software allocator to avoid unknown native memory growth in some devices.
                                        decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE)
                                    }
                                    } catch (e: Exception) {
                                        // Fall back to naive decode if header-based decoding fails
                                        ImageDecoder.decodeDrawable(source)
                                    }
                                }
                            } catch (e: Exception) { null }
                        }
                        if (d is AnimatedImageDrawable) { drawable = d; usedUrl = u; break }
                    }
                if (drawable != null) {
                    try {
                        // For animated images, use View rotation (can't pre-rotate animations)
                        val baseRotation = if (currentOrientation == "vertical") 90 else 0
                        val totalRotation = ((baseRotation + currentRotation) % 360 + 360) % 360
                        crossfadeToImage(setupFront = { iv ->
                            iv.setImageDrawable(drawable)
                            if (drawable is AnimatedImageDrawable) drawable.start()
                        }, rotationDegrees = totalRotation.toFloat(), effect = effect)

                        binding.message.text = file.take(50)
                        // report success
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                        // start periodic ok ping to keep dashboard green while displayed
                        startItemOkPing(storeId, screenId, file, itemId)
                        onDone(true)
                    } catch (e: Exception) {
                        // Defensive: if setImageDrawable fails (e.g., still too large despite downsampling), report failure
                        binding.message.text = "Draw failed: ${file.take(30)}"
                        android.util.Log.e("TvDisplayActivity", "setImageDrawable failed for $file", e)
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "setImageDrawable exception: ${e.message}")) } catch (_: Exception) {}
                        onDone(false)
                    }
                } else {
                    // fallback: try to fetch first frame as bitmap using candidates
                    var bmp: Bitmap? = null
                    for (u in tried) {
                        val b = withContext(Dispatchers.IO) { fetchBitmap(u) }
                        if (b != null) { bmp = b; usedUrl = u; break }
                    }
                    if (bmp != null) {
                        try {
                            // Calculate total rotation (base from orientation + manual rotation)
                            val baseRotation = if (currentOrientation == "vertical") 90 else 0
                            val totalRotation = ((baseRotation + currentRotation) % 360 + 360) % 360
                            
                            // Pre-rotate bitmap to fill screen properly (like Pi client)
                            val rotatedBmp = if (totalRotation != 0) prepareRotatedBitmap(bmp, totalRotation) else bmp
                            crossfadeToImage(setupFront = { iv -> iv.setImageBitmap(rotatedBmp) }, rotationDegrees = 0f, effect = effect)
                            binding.message.text = file.take(50)
                            try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                            startItemOkPing(storeId, screenId, file, itemId)
                            onDone(true)
                        } catch (e: Exception) {
                            binding.message.text = "Draw failed: ${file.take(30)}"
                            android.util.Log.e("TvDisplayActivity", "setImageBitmap failed for $file", e)
                            try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "setImageBitmap exception: ${e.message}")) } catch (_: Exception) {}
                            onDone(false)
                        }
                    } else {
                        binding.message.text = "Load failed: $file".take(60)
                        try { android.util.Log.w("TvDisplayActivity", "Animated image load failed for $file; tried=${tried.joinToString()}") } catch (_: Exception) {}
                        lifecycleScope.launch(Dispatchers.IO) {
                            try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "anim first-frame decode failed; tried=${tried.joinToString()}")) } catch (_: Exception) {}
                        }
                        onDone(false)
                    }
                }
            } else {
                // Try candidates until one succeeds
                var bmp: Bitmap? = null
                for (u in tried) {
                    val b = withContext(Dispatchers.IO) { fetchBitmap(u) }
                    if (b != null) { bmp = b; usedUrl = u; break }
                }
                if (bmp != null) {
                    try {
                        // Calculate total rotation (base from orientation + manual rotation)
                        val baseRotation = if (currentOrientation == "vertical") 90 else 0
                        val totalRotation = ((baseRotation + currentRotation) % 360 + 360) % 360
                        
                        // Pre-rotate bitmap to fill screen properly (like Pi client)
                        val rotatedBmp = if (totalRotation != 0) prepareRotatedBitmap(bmp, totalRotation) else bmp
                        crossfadeToImage(setupFront = { iv -> iv.setImageBitmap(rotatedBmp) }, rotationDegrees = 0f, effect = effect)
                        binding.message.text = file.take(50)
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = itemId)) } catch (_: Exception) {}
                        startItemOkPing(storeId, screenId, file, itemId)
                        onDone(true)
                    } catch (e: Exception) {
                        binding.message.text = "Draw failed: ${file.take(30)}"
                        android.util.Log.e("TvDisplayActivity", "setImageBitmap failed for $file", e)
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "setImageBitmap exception: ${e.message}")) } catch (_: Exception) {}
                        onDone(false)
                    }
                } else {
                    binding.message.text = ("Load failed: " + (file)).take(60)
                    try { android.util.Log.w("TvDisplayActivity", "Image load failed for $file; tried=${tried.joinToString()}") } catch (_: Exception) {}
                    lifecycleScope.launch(Dispatchers.IO) {
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = itemId, error = "image fetch failed; tried=${tried.joinToString()}")) } catch (_: Exception) {}
                    }
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
            .build().also { exo ->
                try { exo.setVideoSurfaceView(playerView) } catch (_: Exception) {}
            }
    // Repeat handled by playlist timing, not ExoPlayer internal repeat
    built.repeatMode = com.google.android.exoplayer2.Player.REPEAT_MODE_OFF
    built.shuffleModeEnabled = false
        // Safer default scaling to reduce buffer churn on some decoders
        try { built.videoScalingMode = com.google.android.exoplayer2.C.VIDEO_SCALING_MODE_SCALE_TO_FIT } catch (_: Exception) {}
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
    // Watchdog tracking to ensure we advance even if a posted Runnable is lost
    var currentItemDurationMs: Long = 10_000L
    var lastAdvanceAtMs: Long = 0L
    fun cancelScheduled() {
        // Cancel only per-item timers. Keep the global schedule tick running so the watchdog
        // can still advance if a posted rotation Runnable is lost by the framework.
        scheduledRotation?.let {
            imageView.removeCallbacks(it)
            playerView.removeCallbacks(it)
            binding.root.removeCallbacks(it)
        }
        scheduledRotation = null
        videoStallWatch?.let {
            imageView.removeCallbacks(it)
            playerView.removeCallbacks(it)
            binding.root.removeCallbacks(it)
        }
        videoStallWatch = null
        // Intentionally DO NOT cancel scheduleTick here.
        // scheduleTick drives schedule window changes and the watchdog.
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
                    val currentFiles = state.items.mapNotNull { it.file }
                    val newFiles = newFiltered.mapNotNull { it.file }
                    try { android.util.Log.d("TvDisplayActivity", "tick: cur=${cur ?: "-"} contains=${containsCurrent} files=${currentFiles.size}->${newFiles.size}") } catch (_: Exception) {}
                    if (state.items.isEmpty() && newFiltered.isNotEmpty()) {
                        state.items = newFiltered; state.index = 0
                    } else if (!containsCurrent) {
                        // Current item no longer active -> interrupt and switch to next scheduled item
                        cancelScheduled()
                        state.items = newFiltered; state.index = 0
                        showNext?.invoke(); return@Runnable
                    } else if (newFiles != currentFiles) {
                        // The active schedule set changed, but current item is still valid
                        // Update the list but DON'T interrupt - let current item finish its duration
                        state.items = newFiltered
                        // Preserve position: find current item in new list and set index to next after it
                        state.index = if (cur != null) {
                            val idx = newFiltered.indexOfFirst { it.file == cur }
                            if (idx >= 0) (idx + 1) % (newFiltered.size.coerceAtLeast(1)) else 0
                        } else 0
                        // DON'T call showNext here - let the scheduled rotation timer complete naturally
                    }
                }
                // Global watchdog: if for any reason the rotation runnable was lost or did not fire, force advance
                try {
                    val nowMs = android.os.SystemClock.elapsedRealtime()
                    val elapsed = nowMs - lastAdvanceAtMs
                    val threshold = (currentItemDurationMs + 1500L).coerceAtLeast(2500L)
                    if (elapsed > threshold && state.items.isNotEmpty()) {
                        android.util.Log.w("TvDisplayActivity", "watchdog: elapsed=${elapsed}ms > threshold=${threshold}ms, forcing advance")
                        cancelScheduled()
                        showNext?.invoke(); return@Runnable
                    }
                } catch (_: Exception) {}
            } catch (_: Exception) { }
            // Watchdog: if rotation task was lost but we have items, kick it
            if (scheduledRotation == null && state.items.isNotEmpty()) {
                try { android.util.Log.d("TvDisplayActivity", "tick: watchdog kick showNext()") } catch (_: Exception) {}
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
        val hasYoutubeProxyMp4 = file.startsWith("youtube:") &&
            !next.url.isNullOrBlank() &&
            next.url!!.startsWith("http", true) &&
            next.url!!.contains("/static/cache/youtube/") &&
            next.url!!.endsWith(".mp4", true)
        android.util.Log.d("TvDisplayActivity", "showAndSchedule -> ${file} (idx=${state.index-1}/${state.items.size})")
        if (file.startsWith("youtube:")) {
            if (hasYoutubeProxyMp4) {
                android.util.Log.d("TvDisplayActivity", "YOUTUBE_PATH=cached_mp4 url=${next.url}")
            } else {
                android.util.Log.d("TvDisplayActivity", "YOUTUBE_PATH=iframe id=${file.removePrefix("youtube:").trim()}")
            }
        }
        currentItemFile = file
        // Record the moment we switched to a new item for watchdog purposes
        try { lastAdvanceAtMs = android.os.SystemClock.elapsedRealtime() } catch (_: Exception) {}
        // ── YouTube IFrame embed via WebView ─────────────────────────────────
        if (file.startsWith("youtube:") && !hasYoutubeProxyMp4) {
            val videoId = file.removePrefix("youtube:").trim()
            if (videoId.isEmpty()) { showAndSchedule(); return }
            // Clear transient status text so no placeholder label appears before playback starts
            binding.message.text = ""
            binding.message.bringToFront()
            try { debugOverlay?.bringToFront() } catch (_: Exception) {}
            try { transitionOverlay?.bringToFront() } catch (_: Exception) {}

            val durMs = (next.duration ?: 10).coerceAtLeast(5) * 1000L
            currentItemDurationMs = durMs
            android.util.Log.d("TvDisplayActivity", "YouTube item duration=${next.duration} -> ${durMs}ms")
            // hqdefault is consistently available; maxresdefault is often missing and causes delay.
            val thumbUrl = "https://img.youtube.com/vi/$videoId/hqdefault.jpg"

            fun stopVideoPipelines() {
                try { exoPlayer?.stop(); exoPlayer?.clearMediaItems() } catch (_: Exception) {}
                legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
                playerView.visibility = ImageView.GONE
            }

            // Fallback: show YouTube thumbnail image when WebView can't play the video.
            // This handles real Android TV devices where WebView-based YouTube embedding is
            // blocked, missing, or crashes (older System WebView / restricted TV builds).
            fun showYouTubeThumbnailFallback(reason: String) {
                android.util.Log.w("TvDisplayActivity", "YouTube WebView unavailable ($reason); showing thumbnail for $videoId")
                cancelScheduled()
                try { youTubeWebView?.let { it.visibility = android.view.View.GONE; it.loadUrl("about:blank") } } catch (_: Exception) {}
                stopVideoPipelines()
                binding.message.text = "YT ${videoId.take(11)}"
                imageView.visibility = ImageView.VISIBLE
                secondaryImageView?.visibility = ImageView.GONE
                binding.message.bringToFront()
                try { debugOverlay?.bringToFront() } catch (_: Exception) {}
                try { transitionOverlay?.bringToFront() } catch (_: Exception) {}
                // YouTube thumbnail URL — always available, no WebView needed
                loadAnimatedOrStatic(thumbUrl, next.id, thumbUrl, next.effect) { _ ->
                    lifecycleScope.launch(Dispatchers.IO) {
                        try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = next.id)) } catch (_: Exception) {}
                    }
                    startItemOkPing(storeId, screenId, file, next.id)
                    cancelScheduled()
                    scheduledRotation = Runnable { showAndSchedule() }
                    imageView.postDelayed(scheduledRotation!!, durMs)
                }
            }

            val activity = this
            // Track whether loadDataWithBaseURL was called so error handlers know WebView is active
            var webViewLoaded = false
            var youtubeRevealed = false

            // Bridge frame: keep UI smooth by showing the video thumbnail while WebView buffers.
            lifecycleScope.launch {
                try {
                    val bmp = withContext(Dispatchers.IO) { fetchBitmap(thumbUrl) }
                    if (bmp != null && !youtubeRevealed) {
                        stopVideoPipelines()
                        imageView.visibility = ImageView.VISIBLE
                        secondaryImageView?.visibility = ImageView.GONE
                        crossfadeToImage(
                            setupFront = { iv -> iv.setImageBitmap(bmp) },
                            rotationDegrees = 0f,
                            durationMs = 220L,
                            effect = next.effect
                        )
                    }
                } catch (_: Exception) {}
            }

            fun revealYoutubeSurface(wv: android.webkit.WebView) {
                if (youtubeRevealed) return
                youtubeRevealed = true
                stopVideoPipelines()
                imageView.visibility = ImageView.GONE
                secondaryImageView?.visibility = ImageView.GONE
                wv.visibility = android.view.View.VISIBLE
                wv.bringToFront()
                binding.message.bringToFront()
                try { debugOverlay?.bringToFront() } catch (_: Exception) {}
                try { transitionOverlay?.bringToFront() } catch (_: Exception) {}
            }

            try {
                val wv = youTubeWebView ?: run {
                    val newWv = android.webkit.WebView(activity).apply {
                        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
                        visibility = android.view.View.GONE
                        settings.javaScriptEnabled = true
                        @Suppress("SetJavaScriptEnabled")
                        settings.mediaPlaybackRequiresUserGesture = false
                        settings.domStorageEnabled = true
                        settings.loadWithOverviewMode = true
                        settings.useWideViewPort = true
                        settings.allowContentAccess = true
                        settings.allowFileAccess = true
                        // Chrome UA required; also spoof desktop so YouTube doesn't restrict player config
                        settings.userAgentString = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        // WebChromeClient needed for HTML5 video/audio playback in WebView
                        webChromeClient = android.webkit.WebChromeClient()
                        // Custom client: detect main-frame errors and fall back to thumbnail
                        webViewClient = object : android.webkit.WebViewClient() {
                            override fun onReceivedError(
                                view: android.webkit.WebView?,
                                request: android.webkit.WebResourceRequest?,
                                error: android.webkit.WebResourceError?
                            ) {
                                if (android.os.Build.VERSION.SDK_INT >= 23 && request?.isForMainFrame == true && webViewLoaded) {
                                    android.util.Log.w("TvDisplayActivity", "YouTube main-frame error: ${error?.description}")
                                    runOnUiThread { showYouTubeThumbnailFallback("webview_error_${error?.errorCode}") }
                                }
                            }

                            override fun onRenderProcessGone(
                                view: android.webkit.WebView?,
                                detail: android.webkit.RenderProcessGoneDetail?
                            ): Boolean {
                                android.util.Log.e("TvDisplayActivity", "YouTube WebView render process gone. crashed=${detail?.didCrash()}")
                                runOnUiThread {
                                    try {
                                        // Fully tear down broken WebView instance and recover.
                                        val broken = youTubeWebView
                                        if (broken != null) {
                                            try { (broken.parent as? android.view.ViewGroup)?.removeView(broken) } catch (_: Exception) {}
                                            try { broken.destroy() } catch (_: Exception) {}
                                        }
                                        youTubeWebView = null
                                    } catch (_: Exception) {}
                                    showYouTubeThumbnailFallback("render_process_gone")
                                }
                                // We handled it; avoid app process crash.
                                return true
                            }
                        }
                    }
                    binding.root.addView(newWv, 0)
                    youTubeWebView = newWv
                    newWv
                }
                wv.visibility = android.view.View.GONE
                try { wv.removeJavascriptInterface("AndroidBridge") } catch (_: Exception) {}
                wv.addJavascriptInterface(object {
                    @android.webkit.JavascriptInterface
                    fun onVideoReady() {
                        runOnUiThread {
                            revealYoutubeSurface(wv)
                        }
                    }
                }, "AndroidBridge")
                // Use youtube-nocookie.com (more permissive) + origin param matching the base URL
                // WebChromeClient + loadDataWithBaseURL together unlock HTML5 autoplay in WebView
                val muteParam = if (screenMuted) "1" else "0"
                val ytHtml = """<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{margin:0;padding:0;background:#000}html,body{width:100%;height:100%;overflow:hidden}#p{position:absolute;top:0;left:0;width:100%;height:100%}</style>
</head><body>
<div id="p"></div>
<script>
var s=document.createElement('script');
s.src='https://www.youtube.com/iframe_api';
document.head.appendChild(s);
var player;
function onYouTubeIframeAPIReady(){
  player=new YT.Player('p',{
    width:'100%',height:'100%',
    videoId:'$videoId',
    playerVars:{autoplay:1,mute:$muteParam,controls:0,rel:0,playsinline:1,iv_load_policy:3,modestbranding:1},
    events:{
            onReady:function(e){e.target.playVideo();},
      onStateChange:function(e){
                if(e.data===1){if(window.AndroidBridge&&AndroidBridge.onVideoReady){AndroidBridge.onVideoReady();}}
        if(e.data===0){e.target.seekTo(0,true);e.target.playVideo();}
        if(e.data===-1){setTimeout(function(){e.target.playVideo();},300);}
      }
    }
  });
}
</script>
</body></html>""".trimIndent()
                wv.loadDataWithBaseURL("https://www.youtube-nocookie.com", ytHtml, "text/html", "utf-8", null)
                webViewLoaded = true
                                // Do not reveal WebView early; keep previous image visible until actual PLAYING state.
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = next.id)) } catch (_: Exception) {}
                }
                startItemOkPing(storeId, screenId, file, next.id)
                cancelScheduled()
                scheduledRotation = Runnable {
                    android.util.Log.d("TvDisplayActivity", "Rotate after YouTube duration ${durMs}ms -> next")
                    try {
                        wv.visibility = android.view.View.GONE
                        wv.loadUrl("about:blank")
                    } catch (_: Exception) {}
                    showAndSchedule()
                }
                binding.root.postDelayed(scheduledRotation!!, durMs)
            } catch (e: Exception) {
                // WebView constructor or setup threw — device doesn't support WebView or is OOM.
                // Report and show thumbnail so the playlist keeps running.
                android.util.Log.e("TvDisplayActivity", "YouTube WebView exception: ${e.message}", e)
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = next.id, error = "youtube_webview_exception: ${e.message}")) } catch (_: Exception) {}
                }
                showYouTubeThumbnailFallback("exception")
            }
            return
        }
        if (isVideo(file) || hasYoutubeProxyMp4) {
            if (hasYoutubeProxyMp4) {
                binding.message.text = "YT-MP4 ${file.removePrefix("youtube:").take(11)}"
            }
            youTubeWebView?.let {
                try {
                    it.visibility = android.view.View.GONE
                    it.loadUrl("about:blank")
                } catch (_: Exception) {}
            }
            imageView.visibility = ImageView.GONE
            secondaryImageView?.visibility = ImageView.GONE
            playerView.visibility = ImageView.VISIBLE
            // Ensure message is above player
            binding.message.bringToFront()
            try { debugOverlay?.bringToFront() } catch (_: Exception) {}
            try { transitionOverlay?.bringToFront() } catch (_: Exception) {}
            // Prefer /media (range streaming) for videos; fallback to static if needed
            val videoUrlPrimary = if (hasYoutubeProxyMp4) next.url!! else ApiClientImageHelper.buildVideoUrl(file)
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
                        // Reveal once legacy video is actually playing
                        revealWithQuickFade()
                        binding.message.text = "Legacy PLAY ${file.take(14)}"
                        // Report success for legacy playback
                        lifecycleScope.launch(Dispatchers.IO) {
                            try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = file, itemId = next.id)) } catch (_: Exception) {}
                        }
                        // Start periodic ok ping while this legacy video is playing
                        startItemOkPing(storeId, screenId, file, next.id)
                        // Schedule rotation according to playlist duration
                        val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                        cancelScheduled()
                        scheduledRotation = Runnable {
                            try { vv.stopPlayback() } catch (_: Exception) {}
                            vv.visibility = ImageView.GONE
                            showAndSchedule()
                        }
                        vv.postDelayed(scheduledRotation!!, durMs)
                    }
                    vv.setOnErrorListener { _, what, extra ->
                        binding.message.text = "LegacyErr w=$what e=$extra"
                        lifecycleScope.launch(Dispatchers.IO) {
                            try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, itemId = next.id, error = "legacy error w=$what e=$extra")) } catch (_: Exception) {}
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
                // Apply screen mute setting before playback starts
                player.volume = if (screenMuted) 0f else 1f
                // Attach listeners only once
                // Prepare new source
                currentVideoFile = file
                triedStaticFallbackForCurrent = false
                player.clearMediaItems()
                // Ensure legacy view is hidden when using ExoPlayer
                legacyVideoView?.visibility = ImageView.GONE
                // Determine if this video item belongs to an auto-sync group
                val isSyncVideo = (next.syncRef != null)
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
                                // Reveal the content when the player is actually ready
                                revealWithQuickFade()
                                lifecycleScope.launch(Dispatchers.IO) {
                                    try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_ok", file = f, itemId = next.id)) } catch (_: Exception) {}
                                }
                                // Start periodic ok ping while this video item is playing
                                startItemOkPing(storeId, screenId, f, next.id)
                                // Prefetch the upcoming item while this video is playing
                                val upcoming = if (state.items.isNotEmpty()) {
                                    val idx = if (state.index >= state.items.size) 0 else state.index
                                    state.items.getOrNull(idx)
                                } else null
                                prefetchNext(upcoming)
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
                                try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = f, itemId = next.id, error = error.message)) } catch (_: Exception) {}
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
                // If in sync mode, start at the server-relative position so all screens show the same frame
                if (isSyncVideo) {
                    player.prepare(); player.playWhenReady = false
                    lifecycleScope.launch(Dispatchers.IO) {
                        try {
                            // Multi-sample sync for accurate server offset
                            com.everydayadvertise.tv.sync.ServerTimeSync.initialSync(5)
                            val durationMs = ((next.duration ?: 10).coerceAtLeast(1)) * 1000L
                            val startEpochSec = next.syncRef?.startEpoch
                            val serverNow = com.everydayadvertise.tv.sync.ServerTimeSync.getServerSyncedTime()
                            var seekMs = 0L
                            if (durationMs > 0) {
                                if (startEpochSec != null) {
                                    val startMs = startEpochSec * 1000L
                                    val phase = (serverNow - startMs) % durationMs
                                    seekMs = if (phase >= 0) phase else (durationMs + phase)
                                } else {
                                    // Fallback: align to continuous server clock cycle
                                    val phase = serverNow % durationMs
                                    seekMs = if (phase >= 0) phase else (durationMs + phase)
                                }
                            }
                            android.util.Log.d("TvDisplayActivity", "Sync video: serverNow=${serverNow}, seekMs=${seekMs}, dur=${durationMs}")
                            withContext(Dispatchers.Main) {
                                try {
                                    if (currentVideoFile == file) {
                                        // Seek to the server-aligned position, then start immediately
                                        try { player.seekTo(seekMs) } catch (_: Exception) {}
                                        try { player.playWhenReady = true } catch (_: Exception) {}
                                    }
                                } catch (_: Exception) {}
                            }
                        } catch (e: Exception) {
                            android.util.Log.w("TvDisplayActivity", "sync start-position failed, playing immediately: ${e.message}")
                            withContext(Dispatchers.Main) { try { player.playWhenReady = true } catch (_: Exception) {} }
                        }
                    }
                } else {
                    // Normal immediate start
                    player.prepare(); player.playWhenReady = true
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
                // Schedule rotation based on playlist duration
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                currentItemDurationMs = durMs
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
                // For sync videos, rotate at the end of the current cycle so all screens advance together
                if ((next.syncRef != null)) {
                    lifecycleScope.launch(Dispatchers.IO) {
                        try {
                            com.everydayadvertise.tv.sync.ServerTimeSync.refreshIfStale()
                            val startEpochSec = next.syncRef?.startEpoch
                            val serverNow = com.everydayadvertise.tv.sync.ServerTimeSync.getServerSyncedTime()
                            var waitMs = durMs
                            if (startEpochSec != null) {
                                val startMs = startEpochSec * 1000L
                                val phase = (serverNow - startMs) % durMs
                                val phasePos = if (phase >= 0) phase else (durMs + phase)
                                waitMs = (durMs - phasePos).coerceAtLeast(50L)
                            } else {
                                // Fallback boundary: align to server clock cycle end
                                val phasePos = serverNow % durMs
                                waitMs = (durMs - (if (phasePos >= 0) phasePos else (durMs + phasePos))).coerceAtLeast(50L)
                            }
                            withContext(Dispatchers.Main) {
                                try { playerView.postDelayed(scheduledRotation!!, waitMs) } catch (_: Exception) {}
                            }
                        } catch (_: Exception) {
                            withContext(Dispatchers.Main) { try { playerView.postDelayed(scheduledRotation!!, durMs) } catch (_: Exception) {} }
                        }
                    }
                } else {
                    playerView.postDelayed(scheduledRotation!!, durMs)
                }
            } catch (e: Exception) {
                binding.message.text = ("ExoFail ${e.message}").take(60)
                useLegacy()
            }
        } else {
            // Skip formats we know we can't render without extra libs (e.g. svg / tiff) to avoid long black frames
            if (isAdvancedStill(file) && !(file.endsWith(".heic", true) || file.endsWith(".heif", true) || file.endsWith(".avif", true))) {
                binding.message.text = "Unsupported: ${file.take(40)}"
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "load_fail", file = file, error = "unsupported still format")) } catch (_: Exception) {}
                }
                imageView.postDelayed({ showAndSchedule() }, 3000)
                return
            }
            // Image / animated
            try { exoPlayer?.stop(); exoPlayer?.clearMediaItems() } catch (_: Exception) {}
        legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
        youTubeWebView?.let {
            try {
                it.visibility = android.view.View.GONE
                it.loadUrl("about:blank")
            } catch (_: Exception) {}
        }
            playerView.visibility = ImageView.GONE
            // Do NOT pre-show imageView here — crossfadeToImage manages visibility.
            // Pre-showing caused stale drawables to flash or slide out when coming from video.
            binding.message.bringToFront()
            try { debugOverlay?.bringToFront() } catch (_: Exception) {}
            try { transitionOverlay?.bringToFront() } catch (_: Exception) {}
            loadAnimatedOrStatic(file, next.id, next.url, next.effect) { success ->
                android.util.Log.d("TvDisplayActivity", "Displayed image/anim ${file} success=${success}")
                // Prefetch upcoming
                val upcoming = if (state.items.isNotEmpty()) {
                    val idx = if (state.index >= state.items.size) 0 else state.index
                    state.items.getOrNull(idx)
                } else null
                prefetchNext(upcoming)
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                currentItemDurationMs = durMs
                cancelScheduled()
                // If load succeeded, the ping was already started inside loadAnimatedOrStatic
                scheduledRotation = Runnable {
                    android.util.Log.d("TvDisplayActivity", "Rotate after image duration ${durMs}ms -> next")
                    showAndSchedule()
                }
                imageView.postDelayed(scheduledRotation!!, durMs)
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

    fun applyNewList(all: List<com.everydayadvertise.tv.api.PlaylistItem>?) {
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
        android.util.Log.d("TvDisplayActivity", "fetchPlaylist: storeId=$storeId, screenId=$screenId")
        lifecycleScope.launch {
            try {
                val jsonString = ApiClient.service.getPlaylist(storeId, screenId, 1)
                android.util.Log.d("TvDisplayActivity", "Received raw JSON: ${jsonString.take(200)}")
                
                // Parse JSON manually using Android's built-in JSONObject
                val jsonObj = org.json.JSONObject(jsonString)
                val success = jsonObj.optBoolean("success", false)
                val newOrientation = jsonObj.optString("orientation", "default")
                val newRotation = jsonObj.optInt("rotation", 0)
                val newMuted = jsonObj.optBoolean("muted", false)
                
                // Parse playlist array
                val original = mutableListOf<com.everydayadvertise.tv.api.PlaylistItem>()
                val playlistArray = jsonObj.optJSONArray("playlist")
                if (playlistArray != null) {
                    for (i in 0 until playlistArray.length()) {
                        try {
                            val item = playlistArray.getJSONObject(i)
                            val id = item.optString("id")
                            val file = item.optString("file")
                            val url = item.optString("url")
                            val enabled = item.optBoolean("enabled", true)
                            val duration = item.optInt("duration", 10)
                            val repeat = item.optBoolean("repeat", true)
                            val linkNext = item.optBoolean("link_next", false)
                            val start = if (item.has("start") && !item.isNull("start")) item.optString("start") else null
                            val end = if (item.has("end") && !item.isNull("end")) item.optString("end") else null
                            val mediaType = if (item.has("media_type") && !item.isNull("media_type")) item.optString("media_type") else null
                            val effect = if (item.has("effect") && !item.isNull("effect")) item.optString("effect") else null
                            
                            // Parse schedule array
                            val schedule = if (item.has("schedule")) {
                                val schedArray = item.optJSONArray("schedule")
                                if (schedArray != null && schedArray.length() > 0) {
                                    val schedList = ArrayList<com.everydayadvertise.tv.api.ScheduleWindow>()
                                    for (j in 0 until schedArray.length()) {
                                        try {
                                            val sched = schedArray.getJSONObject(j)
                                            schedList.add(com.everydayadvertise.tv.api.ScheduleWindow(
                                                start = if (sched.has("start")) sched.optString("start") else null,
                                                end = if (sched.has("end")) sched.optString("end") else null,
                                                days = if (sched.has("days")) {
                                                    val daysArray = sched.optJSONArray("days")
                                                    if (daysArray != null) {
                                                        val daysList = ArrayList<String>()
                                                        for (k in 0 until daysArray.length()) {
                                                            daysList.add(daysArray.getString(k))
                                                        }
                                                        daysList
                                                    } else null
                                                } else null
                                            ))
                                        } catch (e: Exception) {
                                            android.util.Log.e("TvDisplayActivity", "Failed to parse schedule item", e)
                                        }
                                    }
                                    schedList
                                } else null
                            } else null
                            
                            // Parse days array
                            val days = if (item.has("days")) {
                                val daysArray = item.optJSONArray("days")
                                if (daysArray != null && daysArray.length() > 0) {
                                    val daysList = ArrayList<String>()
                                    for (j in 0 until daysArray.length()) {
                                        daysList.add(daysArray.getString(j))
                                    }
                                    daysList
                                } else null
                            } else null
                            
                            // Parse sync_ref
                            val syncRef = if (item.has("sync_ref") && !item.isNull("sync_ref")) {
                                try {
                                    val syncObj = item.getJSONObject("sync_ref")
                                    com.everydayadvertise.tv.api.SyncRef(
                                        group = if (syncObj.has("group")) syncObj.optString("group") else null,
                                        role = if (syncObj.has("role")) syncObj.optString("role") else null,
                                        order = if (syncObj.has("order")) syncObj.optInt("order") else null,
                                        startEpoch = if (syncObj.has("start_epoch")) syncObj.optLong("start_epoch") else if (syncObj.has("startEpoch")) syncObj.optLong("startEpoch") else null,
                                        count = if (syncObj.has("count")) syncObj.optInt("count") else null,
                                        mode = if (syncObj.has("mode")) syncObj.optString("mode") else null,
                                        precisionMode = if (syncObj.has("precision_mode")) syncObj.optString("precision_mode") else null,
                                        preloadBuffer = if (syncObj.has("preload_buffer")) syncObj.optInt("preload_buffer") else null,
                                        syncTolerance = if (syncObj.has("sync_tolerance")) syncObj.optInt("sync_tolerance") else null
                                    )
                                } catch (e: Exception) {
                                    android.util.Log.e("TvDisplayActivity", "Failed to parse sync_ref", e)
                                    null
                                }
                            } else null
                            
                            original.add(com.everydayadvertise.tv.api.PlaylistItem(
                                id = id,
                                file = file,
                                url = url,
                                enabled = enabled,
                                duration = duration,
                                repeat = repeat,
                                linkNext = linkNext,
                                start = start,
                                end = end,
                                schedule = schedule,
                                days = days,
                                mediaType = mediaType,
                                effect = effect,
                                syncRef = syncRef
                            ))
                        } catch (e: Exception) {
                            android.util.Log.e("TvDisplayActivity", "Failed to parse playlist item", e)
                        }
                    }
                }
                
                android.util.Log.d("TvDisplayActivity", "Manually parsed: success=$success, playlist size=${original.size}")
                
                // Get orientation and rotation from server (like Pi client)
                
                // Calculate total rotation like Pi client:
                // base = 90° if vertical, 0° if horizontal
                // total = (base + rotation) % 360
                val baseRotation = if (newOrientation == "vertical") 90 else 0
                val totalRotation = ((baseRotation + newRotation) % 360 + 360) % 360
                
                // Check if rotation or orientation changed
                val orientationChanged = newOrientation != currentOrientation
                val rotationChanged = newRotation != currentRotation
                
                if (orientationChanged || rotationChanged) {
                    android.util.Log.d("TvDisplayActivity", 
                        "Config changed: orientation=$currentOrientation->$newOrientation, " +
                        "rotation=$currentRotation°->$newRotation°, total=$totalRotation°")
                    currentOrientation = newOrientation
                    currentRotation = newRotation
                    applyRotation(totalRotation)
                }

                // Apply mute setting — reload YouTube embed if it changed
                if (newMuted != screenMuted) {
                    android.util.Log.d("TvDisplayActivity", "Mute changed: $screenMuted -> $newMuted")
                    screenMuted = newMuted
                    // Update ExoPlayer volume immediately
                    try { exoPlayer?.volume = if (screenMuted) 0f else 1f } catch (_: Exception) {}
                    // Reload YouTube WebView with updated mute flag if it's currently playing
                    try {
                        val wv = youTubeWebView
                        if (wv != null && wv.visibility == android.view.View.VISIBLE && currentItemFile?.startsWith("youtube:") == true) {
                            val vid = currentItemFile!!.removePrefix("youtube:").trim()
                            val muteParam = if (screenMuted) "1" else "0"
                            val ytHtml = """<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{margin:0;padding:0;background:#000}html,body{width:100%;height:100%;overflow:hidden}#p{position:absolute;top:0;left:0;width:100%;height:100%}</style>
</head><body>
<div id="p"></div>
<script>
var s=document.createElement('script');
s.src='https://www.youtube.com/iframe_api';
document.head.appendChild(s);
var player;
function onYouTubeIframeAPIReady(){
  player=new YT.Player('p',{
    width:'100%',height:'100%',
    videoId:'$vid',
    playerVars:{autoplay:1,mute:$muteParam,controls:0,rel:0,playsinline:1,iv_load_policy:3,modestbranding:1},
    events:{
      onReady:function(e){e.target.playVideo();},
      onStateChange:function(e){
        if(e.data===0){e.target.seekTo(0,true);e.target.playVideo();}
        if(e.data===-1){setTimeout(function(){e.target.playVideo();},300);}
      }
    }
  });
}
</script>
</body></html>""".trimIndent()
                            wv.loadDataWithBaseURL("https://www.youtube-nocookie.com", ytHtml, "text/html", "utf-8", null)
                        }
                    } catch (_: Exception) {}
                }
                
                originalItems = original
                // Apply without resetting index if files are the same
                applyNewList(original)
                lifecycleScope.launch(Dispatchers.IO) {
                    try { ApiClient.service.postClientEvent(com.everydayadvertise.tv.api.ClientEventReq(storeId, screenId, "playlist_reload")) } catch (_: Exception) {}
                }
                val cnt = state.items.size
                if (cnt > 0) {
                    binding.message.text = "" // Hide items loaded message
                    // If rotation hasn’t started or was cancelled, kick it off
                    if (scheduledRotation == null && (currentItemFile == null || imageView.drawable == null)) {
                        showAndSchedule()
                    }
                } else {
                    binding.message.text = if (original.isNotEmpty()) "No items currently scheduled" else "No items in playlist"
                }
            } catch (e: Exception) {
                android.util.Log.e("TvDisplayActivity", "fetchPlaylist error", e)
                val errorMsg = when {
                    e.message != null -> "Network error: ${e.message}"
                    else -> "Network error: ${e.javaClass.simpleName}"
                }
                binding.message.text = errorMsg.take(60)
            } finally {
                imageView.postDelayed({ fetchPlaylist() }, refreshIntervalMs)
            }
        }
    }

    fetchPlaylist()

    // (Release now handled in onDestroy)
}
