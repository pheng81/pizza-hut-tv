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

class TvDisplayActivity : AppCompatActivity() {
    // Made public so extension functions can access
    lateinit var binding: ActivityTvDisplayBinding
    // ExoPlayer instance (initialized lazily within playlist loop). Not private so extension function can access.
    var exoPlayer: com.google.android.exoplayer2.ExoPlayer? = null
    // Keep a reference to legacy VideoView so we can hide/stop it properly
    var legacyVideoView: VideoView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTvDisplayBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.message.text = "Loading playlist..."

        // Create / attach image & video containers
        val imageView = ImageView(this).apply {
            setBackgroundColor(Color.BLACK)
            adjustViewBounds = true
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            scaleType = ImageView.ScaleType.FIT_CENTER
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
        try {
            exoPlayer?.stop()
            exoPlayer?.clearMediaItems()
            exoPlayer?.release()
        } catch (_: Exception) {}
        exoPlayer = null
        legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
        super.onDestroy()
    }
}

object ApiClientImageHelper {
    fun buildImageUrl(filename: String): String = ApiClient.baseUrl + "static/uploads/" + filename
    fun buildVideoUrl(filename: String): String = ApiClient.baseUrl + "media/" + filename // new ranged streaming endpoint
    // Unified builder used by loadAnimatedOrStatic (images & animated assets live in static/uploads)
    fun buildFileUrl(filename: String): String = buildImageUrl(filename)
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
    val refreshIntervalMs = 60_000L // refresh playlist every 60s
    fun pickNext(): com.pizzahut.tv.api.PlaylistItem? {
        if (state.items.isEmpty()) return null
        if (state.index >= state.items.size) state.index = 0
        return state.items[state.index++]
    }

    fun prefetchNext(nextItem: com.pizzahut.tv.api.PlaylistItem?) {
        val nf = nextItem?.file ?: return
    val nurl = ApiClientImageHelper.buildImageUrl(nf)
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

    fun loadAnimatedOrStatic(file: String, onDone: () -> Unit) {
        val url = ApiClientImageHelper.buildFileUrl(file)
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
                } else {
                    // fallback to bitmap path
                    val bmp = withContext(Dispatchers.IO) { fetchBitmap(url) }
                    if (bmp != null) {
                        imageView.setImageBitmap(bmp)
                        binding.message.text = file.take(50)
                    } else binding.message.text = "Load failed: $file".take(60)
                }
            } else {
                val bmp = withContext(Dispatchers.IO) { fetchBitmap(url) }
                if (bmp != null) {
                    imageView.setImageBitmap(bmp)
                    binding.message.text = file.take(50)
                } else binding.message.text = "Load failed: $file".take(60)
            }
            onDone()
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
    }
    fun showAndSchedule() {
        val next = pickNext()
        if (next?.file == null) {
            binding.message.text = "No items"
            // Try again after default 10s
            imageView.postDelayed({ showAndSchedule() }, 10_000L)
            return
        }
        val file = next.file
        if (isVideo(file)) {
            imageView.visibility = ImageView.GONE
            playerView.visibility = ImageView.VISIBLE
            // Ensure message is above player
            binding.message.bringToFront()
            // Prefer /media (range streaming) for videos; fallback to static if needed
            val videoUrlPrimary = ApiClientImageHelper.buildVideoUrl(file)
            val videoUrlFallback = ApiClientImageHelper.buildImageUrl(file)
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
                        mp.isLooping = true
                        vv.visibility = ImageView.VISIBLE
                        vv.start()
                        binding.message.text = "Legacy PLAY ${file.take(14)}"
                    }
                    vv.setOnErrorListener { _, what, extra ->
                        binding.message.text = "LegacyErr w=$what e=$extra"
                        try { vv.stopPlayback() } catch (_: Exception) {}
                        vv.visibility = ImageView.GONE
                        showAndSchedule()
                        true
                    }
                    // If legacy never prepares within 6s, skip to next
                    vv.postDelayed({
                        if (vv.visibility != ImageView.VISIBLE) {
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
                            }
                            if (stateCode == com.google.android.exoplayer2.Player.STATE_ENDED) {
                                // Advance if natural end happens early
                                cancelScheduled()
                                showAndSchedule()
                            }
                        }
                        override fun onPlayerError(error: com.google.android.exoplayer2.PlaybackException) {
                            val f = currentVideoFile ?: "vid"
                            binding.message.text = ("Err ${error.errorCodeName}" + (error.message?.let { ":"+it.take(20) } ?: "")).take(60)
                            val playerRef = exoPlayer ?: return
                            // First error: try static fallback path once
                            if (!triedStaticFallbackForCurrent) {
                                triedStaticFallbackForCurrent = true
                                try {
                                    playerRef.clearMediaItems()
                                    playerRef.setMediaSource(buildMediaSource(ApiClientImageHelper.buildImageUrl(f)))
                                    playerRef.prepare(); playerRef.playWhenReady = true
                                    binding.message.text = ("StaticFB ${f.take(10)}").take(60)
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
                                playerRef.setMediaSource(buildMediaSource(ApiClientImageHelper.buildImageUrl(file)))
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
                cancelScheduled()
                scheduledRotation = Runnable {
                    // Move to next item after configured duration
                    try { player.stop() } catch (_: Exception) {}
            legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
                    showAndSchedule()
                }
                playerView.postDelayed(scheduledRotation!!, durMs)
            } catch (e: Exception) {
                binding.message.text = ("ExoFail ${e.message}").take(60)
                useLegacy()
            }
        } else {
            // Skip formats we know we can't render without extra libs (e.g. svg / tiff) to avoid long black frames
            if (isAdvancedStill(file) && !(file.endsWith(".heic", true) || file.endsWith(".heif", true) || file.endsWith(".avif", true))) {
                binding.message.text = "Unsupported: ${file.take(40)}"
                imageView.postDelayed({ showAndSchedule() }, 3000)
                return
            }
            // Image / animated
            try { exoPlayer?.stop(); exoPlayer?.clearMediaItems() } catch (_: Exception) {}
        legacyVideoView?.let { try { it.stopPlayback() } catch (_: Exception) {}; it.visibility = ImageView.GONE }
            playerView.visibility = ImageView.GONE
            imageView.visibility = ImageView.VISIBLE
            binding.message.bringToFront()
            loadAnimatedOrStatic(file) {
                // Prefetch upcoming
                val upcoming = if (state.items.isNotEmpty()) {
                    val idx = if (state.index >= state.items.size) 0 else state.index
                    state.items.getOrNull(idx)
                } else null
                prefetchNext(upcoming)
                val durMs = (next.duration ?: 10).coerceAtLeast(1) * 1000L
                cancelScheduled()
                scheduledRotation = Runnable { showAndSchedule() }
                imageView.postDelayed(scheduledRotation!!, durMs)
            }
        }
    }

    fun applyNewList(all: List<com.pizzahut.tv.api.PlaylistItem>?) {
        val filtered = all?.filter { it.enabled != false } ?: emptyList()
        state.items = if (filtered.isEmpty()) emptyList() else filtered
        state.index = 0
    }

    fun fetchPlaylist() {
    binding.message.text = "Fetching playlist..."
    lifecycleScope.launch {
            try {
                val resp = ApiClient.service.getPlaylist(storeId, screenId)
                applyNewList(resp.playlist)
                val cnt = state.items.size
                if (cnt > 0) {
                    binding.message.text = "${cnt} items loaded"
                    if (imageView.drawable == null) {
                        showAndSchedule()
                    }
                } else {
                    binding.message.text = "No items in playlist"
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
