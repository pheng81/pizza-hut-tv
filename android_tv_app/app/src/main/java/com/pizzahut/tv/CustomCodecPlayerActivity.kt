package com.pizzahut.tv

import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.media.AudioManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.widget.ImageView
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Gravity
import android.view.Surface
import android.view.TextureView
import android.widget.FrameLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.gson.Gson
import com.pizzahut.tv.api.ApiClient
import com.pizzahut.tv.api.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Request
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.SystemClock
import java.util.concurrent.atomic.AtomicLong
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okhttp3.Response
import okio.ByteString
import kotlin.math.min
import kotlin.math.max
import android.view.Choreographer
import android.view.View

/** Experimental low-level MediaCodec player with sync & metrics overlays. */
class CustomCodecPlayerActivity : AppCompatActivity(), TextureView.SurfaceTextureListener {
    private lateinit var textureView: TextureView
    private lateinit var root: FrameLayout
    private var decodeThread: Thread? = null
    @Volatile private var stopFlag = false

    private var playlist: List<PlaylistItem> = emptyList()
    private var currentIndex = -1
    private var currentItem: PlaylistItem? = null
    // Playlist state diagnostics
    private enum class PlaylistState { LOADING, READY, EMPTY, ERROR }
    @Volatile private var playlistState: PlaylistState = PlaylistState.LOADING
    @Volatile private var lastPlaylistFetchTs: Long = 0L
    @Volatile private var lastPlaylistError: String? = null
    private var storeId: String = "0000"
    private var screenId: String = "screen1"
    private var playlistRefreshMs = 60_000L
    private val handler = Handler(Looper.getMainLooper())
    private var backoffMs = 2_000L
    private val maxBackoffMs = 60_000L
    private var muted = true
    private var pendingSyncEpoch: Long? = null
    private var firstGroupStartEpoch: Long? = null
    private var metricsOverlay: TextView? = null
    private val frameCounter = java.util.concurrent.atomic.AtomicLong(0)
    private var lastFpsSampleMs = 0L
    private var lastFrameCountSample = 0L
    private var lastPtsUs = 0L
    private var droppedEstimate = 0L
    private var firstFrameRendered = false
    private var decodeStartMono = 0L
    private var sumFrameDeltaMs = 0L
    private var frameDeltaSamples = 0
    private var lastRenderMonoGlobal = 0L
    private var consecutiveStalls = 0
    private var useChoreographerPacing = true
    private val choreographer by lazy { Choreographer.getInstance() }
    private var consecutiveFirstFrameTimeouts = 0

    // Image support
    private var imageView: ImageView? = null
    private var currentBitmap: Bitmap? = null

    // UI controls overlay
    private var controlsOverlay: TextView? = null
    private var controlsVisible = true
    private var volumeOverlay: TextView? = null
    private var lastVolumeOverlayTs = 0L

    // WebSocket
    private var syncSocket: WebSocket? = null
    private var wsReconnectMs = 5_000L
    private var authToken: String? = null
    private var lastWsMetricsSent = 0L
    private var wsMetricsIntervalMs = 10_000L
    private val wsMaxReconnectMs = 60_000L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        root = FrameLayout(this)
        textureView = TextureView(this)
        textureView.surfaceTextureListener = this
        root.addView(textureView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        imageView = ImageView(this).apply { scaleType = ImageView.ScaleType.MATRIX; visibility = ImageView.GONE }
        root.addView(imageView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
    metricsOverlay = TextView(this).apply { setTextColor(0xFFFFFFFF.toInt()); textSize = 12f; setBackgroundColor(0x66000000); setPadding(16, 8, 16, 8); text = "LOADING PLAYLIST..." }
        root.addView(metricsOverlay, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT).apply { gravity = Gravity.TOP or Gravity.START })
        controlsOverlay = TextView(this).apply { setTextColor(0xFFFFFFFF.toInt()); textSize = 14f; setBackgroundColor(0x66000000); setPadding(20, 14, 20, 14); text = controlHelpText() }
        root.addView(controlsOverlay, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT).apply { gravity = Gravity.BOTTOM or Gravity.START })
        volumeOverlay = TextView(this).apply { setTextColor(0xFFFFFFFF.toInt()); textSize = 18f; setBackgroundColor(0x99000000.toInt()); setPadding(26, 20, 26, 20); text = "VOL"; visibility = View.GONE }
        root.addView(volumeOverlay, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT).apply { gravity = Gravity.CENTER_HORIZONTAL or Gravity.TOP })
        setContentView(root)
        volumeControlStream = AudioManager.STREAM_MUSIC
        storeId = intent.getStringExtra("storeId")?.ifBlank { null } ?: "0000"
        screenId = intent.getStringExtra("screenId")?.ifBlank { null } ?: "screen1"
        fetchPlaylist(initial = true)
        scheduleInitialPlaylistWatchdog()
        schedulePlaylistRefresh(); scheduleHeartbeat(); scheduleMetricsUpdate(); scheduleStallWatchdog(); connectWebSocket()
    }

    override fun onDestroy() { stopFlag = true; try { syncSocket?.close(1000, "destroy") } catch (_: Exception) {}; decodeThread?.interrupt(); currentBitmap?.recycle(); currentBitmap = null; super.onDestroy() }

    private fun fetchPlaylist(initial: Boolean = false) {
        playlistState = PlaylistState.LOADING
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val resp = ApiClient.service.getPlaylist(storeId, screenId)
                val list = (resp.playlist ?: emptyList()).filter { it.enabled != false }
                lastPlaylistFetchTs = System.currentTimeMillis()
                if (list.isNotEmpty()) {
                    playlist = list
                    playlistState = PlaylistState.READY
                    lastPlaylistError = null
                    if (initial) { currentIndex = -1; advanceItem(reason = "initial") }
                    backoffMs = 2_000L
                } else {
                    playlist = emptyList()
                    playlistState = PlaylistState.EMPTY
                    lastPlaylistError = null
                    Log.w("CustomCodec", "Empty playlist (JSON resp)")
                }
            } catch (e: Exception) {
                lastPlaylistFetchTs = System.currentTimeMillis()
                lastPlaylistError = e.message
                playlistState = PlaylistState.ERROR
                Log.e("CustomCodec", "Playlist fetch failed base=${ApiClient.baseUrl} store=${storeId} screen=${screenId} msg=${e.message}")
                scheduleRetry()
            }
        }
    }

    private fun scheduleRetry() { backoffMs = min(maxBackoffMs, (backoffMs * 1.7).toLong()); handler.postDelayed({ fetchPlaylist(initial = false) }, backoffMs) }
    private fun schedulePlaylistRefresh() { handler.postDelayed({ if (!stopFlag) { fetchPlaylist(initial = false); schedulePlaylistRefresh() } }, playlistRefreshMs) }
    private fun scheduleInitialPlaylistWatchdog() { handler.postDelayed({
        if (stopFlag) return@postDelayed
        if (playlistState != PlaylistState.READY) {
            Log.w("CustomCodec", "Playlist still not READY after initial timeout; retrying fetch")
            fetchPlaylist(initial = false)
        }
    }, 15_000L) }
    private fun scheduleHeartbeat() { handler.postDelayed({ if (!stopFlag) { postHeartbeat(); scheduleHeartbeat() } }, 30_000L) }
    private fun postHeartbeat() { lifecycleScope.launch(Dispatchers.IO) { try { ApiClient.service.sendHeartbeat(HeartbeatReq(storeId, screenId)) } catch (_: Exception) {} } }
    private fun postEvent(event: String, item: PlaylistItem?, error: String? = null) { lifecycleScope.launch(Dispatchers.IO) { try { ApiClient.service.postClientEvent(ClientEventReq(storeId, screenId, event, file = item?.file, itemId = item?.id, error = error)) } catch (_: Exception) {} }; try { val json = Gson().toJson(mapOf("type" to "client_event","event" to event,"storeId" to storeId,"screenId" to screenId,"itemId" to (item?.id ?: ""),"file" to (item?.file ?: ""),"error" to (error ?: ""),"ts" to System.currentTimeMillis())); syncSocket?.send(json) } catch (_: Exception) {} }

    private fun advanceItem(reason: String) { if (playlist.isEmpty()) return; currentIndex = (currentIndex + 1) % playlist.size; currentItem = playlist[currentIndex]; frameCounter.set(0); lastPtsUs = 0L; droppedEstimate = 0L; sumFrameDeltaMs = 0L; frameDeltaSamples = 0; decodeStartMono = SystemClock.elapsedRealtime(); applyViewportCrop(); postEvent("item_start", currentItem, reason); if (isVideoItem(currentItem)) { imageView?.visibility = ImageView.GONE; textureView.visibility = TextureView.VISIBLE; if (textureView.isAvailable) startDecode(textureView.surfaceTexture!!) } else if (isImageItem(currentItem)) { stopDecodeThread(); loadAndDisplayImage(currentItem!!) } else { handler.post { advanceItem("skip_unknown") }; return }; establishSyncBarrierIfNeeded() }
    private fun isVideoItem(item: PlaylistItem?): Boolean = when { item == null -> false; (item.mediaType == "video") -> true; (item.url?.lowercase()?.endsWith(".mp4") == true) -> true; else -> false }
    private fun isImageItem(item: PlaylistItem?): Boolean = when { item == null -> false; item.mediaType == "image" -> true; else -> item.url?.lowercase()?.matches(Regex(".*\\.(png|jpg|jpeg|gif|webp)$")) == true }
    private fun loadAndDisplayImage(item: PlaylistItem) { val durMs = ((item.duration ?: 10) * 1000L).coerceAtLeast(1000L); lifecycleScope.launch(Dispatchers.IO) { try { val url = item.url ?: return@launch; val httpField = ApiClient::class.java.getDeclaredField("okHttp").apply { isAccessible = true }; val okClient = httpField.get(ApiClient) as okhttp3.OkHttpClient; val req = Request.Builder().url(url).get().build(); okClient.newCall(req).execute().use { resp -> if (!resp.isSuccessful) throw IllegalStateException("HTTP ${resp.code}"); val bytes = resp.body?.bytes() ?: throw IllegalStateException("empty image"); val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size); withContext(Dispatchers.Main) { currentBitmap?.recycle(); currentBitmap = bmp; imageView?.setImageBitmap(bmp); applyImageViewportCrop(bmp, item); imageView?.visibility = ImageView.VISIBLE; textureView.visibility = TextureView.GONE } } } catch (e: Exception) { Log.e("CustomCodec", "Image load failed", e) } finally { handler.postDelayed({ advanceItem("image_timeout") }, durMs) } } }
    private fun applyImageViewportCrop(bmp: Bitmap?, item: PlaylistItem) { if (bmp == null) return; val sref = item.syncRef ?: return; val order = (sref.order ?: 0).coerceAtLeast(0); val count = (sref.count ?: 1).coerceAtLeast(1); if (count <= 1) return; val mode = (sref.mode ?: "split-h").lowercase(); val viewW = imageView?.width ?: return; val viewH = imageView?.height ?: return; if (viewW == 0 || viewH == 0) { imageView?.post { applyImageViewportCrop(bmp, item) }; return }; val m = Matrix(); val bmpW = bmp.width.toFloat(); val bmpH = bmp.height.toFloat(); if (mode == "split-h") { val scale = viewH / bmpH; val displayedFullWidth = bmpW * scale; val perSlice = displayedFullWidth / count; val xOffset = -order * perSlice; m.setScale(scale, scale); m.postTranslate(xOffset, 0f) } else { val scale = viewW / bmpW; val displayedFullHeight = bmpH * scale; val perSlice = displayedFullHeight / count; val yOffset = -order * perSlice; m.setScale(scale, scale); m.postTranslate(0f, yOffset) }; imageView?.imageMatrix = m }
    private fun stopDecodeThread() { try { stopFlag = true; decodeThread?.interrupt() } catch (_: Exception) {} }
    private fun establishSyncBarrierIfNeeded() { val sref = currentItem?.syncRef ?: return; if (firstGroupStartEpoch == null && sref.startEpoch != null && sref.startEpoch > 0) { firstGroupStartEpoch = sref.startEpoch }; pendingSyncEpoch = firstGroupStartEpoch }
    private fun startDecode(st: SurfaceTexture) {
        if (currentItem?.url.isNullOrBlank()) return
        if (decodeThread?.isAlive == true) return
        stopFlag = false
        firstFrameRendered = false
        val itemRef = currentItem
        val url = itemRef!!.url!!
        Log.d("CustomCodec", "startDecode url=${url}")
        // Watchdog for first frame
        handler.postDelayed({
            if (!stopFlag && !firstFrameRendered && isVideoItem(itemRef)) {
                consecutiveFirstFrameTimeouts++
                Log.w("CustomCodec", "First frame timeout #$consecutiveFirstFrameTimeouts; restarting decode for url=${url}")
                postEvent("first_frame_timeout", itemRef, "count=$consecutiveFirstFrameTimeouts")
                if (consecutiveFirstFrameTimeouts >= 2) {
                    Log.e("CustomCodec", "Escalating to WebPlayer after first-frame timeouts")
                    fallbackToWebPlayer("first_frame_timeout_${consecutiveFirstFrameTimeouts}")
                } else {
                    textureView.surfaceTexture?.let { startDecode(it) }
                }
            } else if (firstFrameRendered) {
                consecutiveFirstFrameTimeouts = 0
            }
        }, 3_000L)
        decodeThread = Thread {
            runDecodeOnce(url, itemRef)
            if (!stopFlag) handler.post { advanceItem("eos") }
        }.apply { name = "CustomCodecDecode"; start() }
    }

    private fun runDecodeOnce(url: String, item: PlaylistItem) {
        var extractor: MediaExtractor? = null
        var codec: MediaCodec? = null
        try {
            // Preflight HEAD to ensure media reachable quickly (avoid long hangs inside extractor)
            try {
                val okClient = ApiClient.rawOkHttp
                val headReq = okhttp3.Request.Builder().url(url).head().build()
                okClient.newCall(headReq).execute().use { hr ->
                    if (!hr.isSuccessful) throw IllegalStateException("HEAD ${hr.code}")
                    val cl = hr.header("Content-Length")
                    Log.d("CustomCodec", "Preflight HEAD ok len=${cl}")
                }
            } catch (e: Exception) {
                Log.e("CustomCodec", "Preflight failed url=${url} msg=${e.message}")
                postEvent("preflight_fail", item, e.message)
                return
            }
            Log.d("CustomCodec", "Decode thread begin url=${url}")
            extractor = MediaExtractor()
            extractor.setDataSource(url)
            Log.d("CustomCodec", "DataSource set, trackCount=${extractor.trackCount}")
            var videoTrack = -1
            for (i in 0 until extractor.trackCount) {
                val fmt = extractor.getTrackFormat(i)
                val mime = fmt.getString(MediaFormat.KEY_MIME) ?: continue
                if (mime.startsWith("video/")) { videoTrack = i; break }
            }
            if (videoTrack < 0) throw IllegalStateException("No video track")
            extractor.selectTrack(videoTrack)
            val format = extractor.getTrackFormat(videoTrack)
            Log.d("CustomCodec", "Selected videoTrack=${videoTrack} format=${format}")
            val surface = Surface(textureView.surfaceTexture)
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            codec.configure(format, surface, null, 0)
            codec.start()
            Log.d("CustomCodec", "Codec started mime=${format.getString(MediaFormat.KEY_MIME)}")
            pendingSyncEpoch?.let { epoch ->
                val waitMs = epoch - System.currentTimeMillis()
                if (waitMs > 30) {
                    Log.d("CustomCodec", "Sync wait ${waitMs}ms for group epoch")
                    Thread.sleep(min(waitMs, 10_000L))
                }
                pendingSyncEpoch = null
            }
            val baseMono = SystemClock.elapsedRealtime()
            val bufferInfo = MediaCodec.BufferInfo()
            var eos = false
            var lastRenderMono = SystemClock.elapsedRealtime()
            while (!stopFlag && !eos) {
                val inIndex = codec.dequeueInputBuffer(10_000)
                if (inIndex >= 0) {
                    val buf = codec.getInputBuffer(inIndex)!!
                    val sz = extractor.readSampleData(buf, 0)
                    if (sz < 0) {
                        codec.queueInputBuffer(inIndex, 0,0,0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                    } else {
                        val pts = extractor.sampleTime
                        codec.queueInputBuffer(inIndex, 0, sz, pts, 0)
                        extractor.advance()
                    }
                }
                val outIndex = codec.dequeueOutputBuffer(bufferInfo, 5_000)
                if (outIndex >= 0) {
                    if (!firstFrameRendered) firstFrameRendered = true
                    if (frameCounter.get() == 0L) Log.d("CustomCodec", "First frame rendered url=${url}")
                    val ptsMs = bufferInfo.presentationTimeUs / 1000L
                    val playElapsed = SystemClock.elapsedRealtime() - baseMono
                    val delta = ptsMs - playElapsed
                    if (delta > 2) {
                        if (useChoreographerPacing) {
                            val target = SystemClock.elapsedRealtime() + delta
                            var yielded = false
                            while (!stopFlag && SystemClock.elapsedRealtime() < target - 2) {
                                val latch = Object()
                                choreographer.postFrameCallback { synchronized(latch) { latch.notify() } }
                                synchronized(latch) { try { latch.wait(5) } catch (_: InterruptedException) {} }
                                yielded = true
                            }
                            if (!yielded) {
                                val remain = target - SystemClock.elapsedRealtime()
                                if (remain > 1) Thread.sleep(min(5, remain.toInt()).toLong())
                            }
                        } else {
                            Thread.sleep(min(15, delta.toInt()).toLong())
                        }
                    }
                    if (lastPtsUs != 0L) {
                        val frameDelta = (bufferInfo.presentationTimeUs - lastPtsUs) / 1000L
                        if (frameDelta in 5..80) { sumFrameDeltaMs += frameDelta; frameDeltaSamples++ }
                        if (frameDelta > 50) droppedEstimate++
                    }
                    lastPtsUs = bufferInfo.presentationTimeUs
                    val c = frameCounter.incrementAndGet()
                    if (c % 30L == 0L) Log.d("CustomCodec", "Frame milestone count=${c} url=${url}")
                    lastRenderMono = SystemClock.elapsedRealtime()
                    lastRenderMonoGlobal = lastRenderMono
                    codec.releaseOutputBuffer(outIndex, true)
                    if ((bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) { eos = true }
                }
                applyViewportCrop()
            }
            postEvent("item_end", item, null)
        } catch (e: Exception) {
            Log.e("CustomCodec", "Decode loop error url=${url} msg=${e.message}", e)
            postEvent("load_fail", item, e.message)
        } finally {
            Log.d("CustomCodec", "Tearing down codec for url=${url}")
            try { codec?.stop(); codec?.release() } catch (_: Exception) {}
            try { extractor?.release() } catch (_: Exception) {}
        }
    }
    private fun applyViewportCrop() { val item = currentItem ?: return; val sref = item.syncRef ?: return; val order = (sref.order ?: 0).coerceAtLeast(0); val count = (sref.count ?: 1).coerceAtLeast(1); if (count <= 1) return; val mode = (sref.mode ?: "split-h").lowercase(); val w = textureView.width.takeIf { it > 0 } ?: return; val h = textureView.height.takeIf { it > 0 } ?: return; val m = Matrix(); if (mode == "split-h") { val sliceW = w.toFloat() / count; val tx = -order * sliceW; m.setScale(count.toFloat(), 1f); m.postTranslate(tx, 0f) } else { val sliceH = h.toFloat() / count; val ty = -order * sliceH; m.setScale(1f, count.toFloat()); m.postTranslate(0f, ty) }; textureView.post { textureView.setTransform(m) } }
    private fun scheduleMetricsUpdate() { handler.postDelayed({ if (!stopFlag) { updateMetricsOverlay(); scheduleMetricsUpdate() } }, 1000L) }
    private fun updateMetricsOverlay() {
        val frames = frameCounter.get()
        val now = SystemClock.elapsedRealtime()
        if (lastFpsSampleMs == 0L) { lastFpsSampleMs = now; lastFrameCountSample = frames }
        val elapsed = now - lastFpsSampleMs
        var fps = 0.0
        if (elapsed >= 1000) {
            val diff = frames - lastFrameCountSample
            fps = diff * 1000.0 / elapsed
            lastFpsSampleMs = now
            lastFrameCountSample = frames
        }
        val avgDelta = if (frameDeltaSamples > 0) sumFrameDeltaMs / frameDeltaSamples else 0
        val state = playlistState.name
        val ageSec = if (lastPlaylistFetchTs > 0) (System.currentTimeMillis() - lastPlaylistFetchTs) / 1000 else -1
        val err = lastPlaylistError?.let { " err=${it.take(30)}" } ?: ""
    val sinceLastMs = if (lastRenderMonoGlobal == 0L) -1 else (SystemClock.elapsedRealtime() - lastRenderMonoGlobal)
    val firstFlag = if (firstFrameRendered) "Y" else "N"
        val urlShort = currentItem?.url?.let { u ->
            val clean = u.substringAfterLast('/')
            if (clean.length > 14) clean.take(6) + ".." + clean.takeLast(6) else clean
        } ?: "-"
        metricsOverlay?.text = "IDX=$currentIndex F1=$firstFlag FPS=${"%.1f".format(fps)} dropEst=$droppedEstimate Δ=${avgDelta}ms stall=${sinceLastMs}ms stalls=$consecutiveStalls PL=${playlist.size} $state age=${ageSec}s file=${urlShort}$err"
        sendMetricsWs()
    }
    private fun scheduleStallWatchdog() { handler.postDelayed({ if (!stopFlag) { checkStall(); scheduleStallWatchdog() } }, 5_000L) }
    private fun checkStall() {
        val item = currentItem ?: return
        if (!isVideoItem(item)) return
        val since = SystemClock.elapsedRealtime() - lastRenderMonoGlobal
        if (since > 10_000L) {
            consecutiveStalls++
            Log.w("CustomCodec", "STALL detected (${since}ms) count=$consecutiveStalls restarting item")
            postEvent("stall_restart", item, null)
            sendSimpleWs("stall_restart")
            stopDecodeThread()
            if (consecutiveStalls >= 3) {
                fallbackToWebPlayer("stall_exceeded_${consecutiveStalls}")
            } else {
                textureView.surfaceTexture?.let { startDecode(it) }
            }
        } else if (since < 2000L) {
            // Reset stall counter on healthy rendering
            if (consecutiveStalls != 0) consecutiveStalls = 0
        }
    }

    private fun fallbackToWebPlayer(reason: String) {
        val item = currentItem
        Log.e("CustomCodec", "Fallback to WebPlayerActivity reason=${reason}")
        postEvent("codec_fallback", item, reason)
        try {
            val intent = android.content.Intent(this, WebPlayerActivity::class.java).apply {
                putExtra("storeId", storeId)
                putExtra("screenId", screenId)
            }
            startActivity(intent)
            finish()
        } catch (e: Exception) {
            Log.e("CustomCodec", "Fallback launch failed reason=${reason}", e)
        }
    }
    private fun connectWebSocket() { try { val base = ApiClient.baseUrl; val host = base.replaceFirst("http://", "ws://").replaceFirst("https://", "wss://"); val url = host.trimEnd('/') + "/ws/sync/$storeId/$screenId"; val httpField = ApiClient::class.java.getDeclaredField("okHttp").apply { isAccessible = true }; val okClient = httpField.get(ApiClient) as okhttp3.OkHttpClient; val req = okhttp3.Request.Builder().url(url).build(); syncSocket = okClient.newWebSocket(req, object: WebSocketListener() { override fun onOpen(webSocket: WebSocket, response: Response) { wsReconnectMs = 5_000L; Log.d("CustomCodecWS", "Connected"); val payload = mapOf("type" to "handshake","storeId" to storeId,"screenId" to screenId,"device" to android.os.Build.MODEL,"sdk" to android.os.Build.VERSION.SDK_INT,"ts" to System.currentTimeMillis(),"token" to (authToken ?: "")); webSocket.send(Gson().toJson(payload)) } override fun onMessage(webSocket: WebSocket, text: String) { handler.post { handleSyncMessage(text) } } override fun onMessage(webSocket: WebSocket, bytes: ByteString) {} override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) { Log.e("CustomCodecWS", "WS failure: ${t.message}"); scheduleWsReconnect() } override fun onClosed(webSocket: WebSocket, code: Int, reason: String) { scheduleWsReconnect() } }) } catch (e: Exception) { Log.e("CustomCodecWS", "Connect error", e); scheduleWsReconnect() } }
    private fun scheduleWsReconnect() { wsReconnectMs = min(wsMaxReconnectMs, (wsReconnectMs * 1.7).toLong()); handler.postDelayed({ if (!stopFlag) connectWebSocket() }, wsReconnectMs) }
    private fun handleSyncMessage(msg: String) { if (msg.startsWith("{")) { try { val obj = Gson().fromJson(msg, Map::class.java); when (obj["type"]) { "command" -> when (obj["cmd"]) { "reload" -> fetchPlaylist(false); "next" -> advanceItem("ws_next"); "prev" -> { if (playlist.isNotEmpty()) { currentIndex = (currentIndex - 2 + playlist.size) % playlist.size; advanceItem("ws_prev") } }; "set_epoch" -> (obj["epoch"] as? Double)?.toLong()?.let { pendingSyncEpoch = it }; "metrics_request" -> sendMetricsWs(force = true) }; "auth" -> { (obj["token"] as? String)?.let { authToken = it } } } } catch (e: Exception) { Log.w("CustomCodecWS", "Bad JSON msg: $msg") }; return }; when { msg.equals("reload", true) -> fetchPlaylist(false); msg.equals("next", true) -> advanceItem("ws_next"); msg.equals("prev", true) -> { if (playlist.isNotEmpty()) { currentIndex = (currentIndex - 2 + playlist.size) % playlist.size; advanceItem("ws_prev") } }; msg.startsWith("sync_epoch:", true) -> { val parts = msg.split(":", limit = 2); parts.getOrNull(1)?.toLongOrNull()?.let { epoch -> pendingSyncEpoch = epoch } } } }
    private fun sendSimpleWs(event: String) { try { syncSocket?.send(Gson().toJson(mapOf("type" to "simple", "event" to event, "ts" to System.currentTimeMillis()))) } catch (_: Exception) {} }
    private fun sendMetricsWs(force: Boolean = false) { val now = System.currentTimeMillis(); if (!force && now - lastWsMetricsSent < wsMetricsIntervalMs) return; lastWsMetricsSent = now; try { val avgDelta = if (frameDeltaSamples > 0) sumFrameDeltaMs / frameDeltaSamples else 0; val payload = mapOf("type" to "metrics","storeId" to storeId,"screenId" to screenId,"fpsFrames" to frameCounter.get(),"dropEst" to droppedEstimate,"avgDelta" to avgDelta,"currentIndex" to currentIndex,"ts" to now); syncSocket?.send(Gson().toJson(payload)) } catch (_: Exception) {} }
    private fun controlHelpText(): String = "NEXT: Right  PREV: Left  Mute: M / MediaPlayPause  Toggle HUD: Menu/Info"
    private fun showVolumeOverlay(vol: Int, muted: Boolean) { val txt = if (muted) "MUTED" else "VOL $vol"; volumeOverlay?.text = txt; volumeOverlay?.visibility = View.VISIBLE; lastVolumeOverlayTs = SystemClock.elapsedRealtime(); handler.postDelayed({ val diff = SystemClock.elapsedRealtime() - lastVolumeOverlayTs; if (diff >= 1400) volumeOverlay?.visibility = View.GONE }, 1500) }
    override fun onKeyDown(keyCode: Int, event: android.view.KeyEvent?): Boolean {
        when (keyCode) {
            android.view.KeyEvent.KEYCODE_DPAD_RIGHT -> { advanceItem("key_next"); return true }
            android.view.KeyEvent.KEYCODE_DPAD_LEFT -> { if (playlist.isNotEmpty()) { currentIndex = (currentIndex - 2 + playlist.size) % playlist.size; advanceItem("key_prev") }; return true }
            android.view.KeyEvent.KEYCODE_R -> { Log.d("CustomCodec", "Manual reload via R key"); fetchPlaylist(initial = false); scheduleInitialPlaylistWatchdog(); return true }
            android.view.KeyEvent.KEYCODE_M, android.view.KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, android.view.KeyEvent.KEYCODE_VOLUME_MUTE -> {
                muted = !muted; postEvent("mute_toggle", currentItem, muted.toString()); showControlsFlash(); val am = getSystemService(AUDIO_SERVICE) as AudioManager; am.setStreamMute(AudioManager.STREAM_MUSIC, muted); val vol = am.getStreamVolume(AudioManager.STREAM_MUSIC); showVolumeOverlay(vol, muted); return true }
            android.view.KeyEvent.KEYCODE_VOLUME_UP -> { val am = getSystemService(AUDIO_SERVICE) as AudioManager; am.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_RAISE, 0); val vol = am.getStreamVolume(AudioManager.STREAM_MUSIC); showVolumeOverlay(vol, muted); return true }
            android.view.KeyEvent.KEYCODE_VOLUME_DOWN -> { val am = getSystemService(AUDIO_SERVICE) as AudioManager; am.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_LOWER, 0); val vol = am.getStreamVolume(AudioManager.STREAM_MUSIC); showVolumeOverlay(vol, muted); return true }
            android.view.KeyEvent.KEYCODE_MENU, android.view.KeyEvent.KEYCODE_INFO -> { controlsVisible = !controlsVisible; controlsOverlay?.visibility = if (controlsVisible) TextView.VISIBLE else TextView.GONE; return true }
        }
        return super.onKeyDown(keyCode, event)
    }
    private fun showControlsFlash() { controlsOverlay?.text = controlHelpText() + "\nMuted=$muted"; controlsOverlay?.visibility = TextView.VISIBLE; handler.postDelayed({ if (!controlsVisible) controlsOverlay?.visibility = TextView.GONE }, 4000) }
    override fun onSurfaceTextureAvailable(surface: SurfaceTexture, width: Int, height: Int) { if (currentItem != null && currentItem?.mediaType == "video") startDecode(surface) }
    override fun onSurfaceTextureSizeChanged(surface: SurfaceTexture, width: Int, height: Int) {}
    override fun onSurfaceTextureDestroyed(surface: SurfaceTexture): Boolean { stopFlag = true; return true }
    override fun onSurfaceTextureUpdated(surface: SurfaceTexture) {}
}
