package com.pizzahut.tv

import android.content.Context
import android.graphics.*
import android.media.*
import android.os.Looper
import android.util.Log
import android.view.Surface
import android.view.SurfaceHolder
import android.view.SurfaceView
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.io.IOException
import java.nio.ByteBuffer
import java.net.HttpURLConnection
import java.net.URL

/**
 * Custom software video decoder using MediaExtractor + MediaCodec
 * Designed to handle problematic MP4 files that ExoPlayer can't decode
 */
class CustomVideoDecoder(
    private val context: Context,
    private val surfaceView: SurfaceView
) {
    // Reverted: removed global init mutex
    private val TAG = "CustomVideoDecoder"
    private val mainScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val ioDispatcher = Dispatchers.IO
    private val initMutex = Mutex()
    @Volatile private var initToken: Long = 0
    
    private var mediaExtractor: MediaExtractor? = null
    private var videoDecoder: MediaCodec? = null
    private var audioDecoder: MediaCodec? = null
    private var audioTrack: AudioTrack? = null
    
    @Volatile private var isPlaying = false
    @Volatile private var isPrepared = false
    @Volatile private var pendingStart = false
    private var decoderJob: Job? = null
    
    private var videoTrackIndex = -1
    private var audioTrackIndex = -1
    
    // Playback callback
    var onPreparedListener: (() -> Unit)? = null
    var onErrorListener: ((error: String) -> Unit)? = null
    var onCompletionListener: (() -> Unit)? = null
    // Reverted: removed first-frame callback API

    // Public state accessors
    fun isPlaying(): Boolean = isPlaying
    fun isPrepared(): Boolean = isPrepared
    
    fun setVideoPath(path: String) {
        Log.d(TAG, "Setting video path: $path")
        val myToken = System.nanoTime()
        initToken = myToken
        // Run preparation off the main thread to avoid StrictMode violations and serialize work
        mainScope.launch(ioDispatcher) {
            try {
                initMutex.withLock {
                    // If a newer init started, abort this one early
                    if (initToken != myToken) return@withLock

                    // Release any existing resources safely before re-initialization
                    stop()
                    try { videoDecoder?.release() } catch (_: Exception) {}
                    videoDecoder = null
                    try { audioDecoder?.release() } catch (_: Exception) {}
                    audioDecoder = null
                    try { audioTrack?.release() } catch (_: Exception) {}
                    audioTrack = null
                    try { mediaExtractor?.release() } catch (_: Exception) {}
                    mediaExtractor = null
                    isPrepared = false
                }

                // Create new media extractor with URL handling
                val extractor = MediaExtractor()

                if (path.startsWith("http://") || path.startsWith("https://")) {
                    // Prefer direct URL with headers first
                    val headers = mutableMapOf<String, String>()
                    headers["User-Agent"] = "CustomVideoDecoder Android"
                    try {
                        val pairCode = com.pizzahut.tv.api.PairCodeHolder.get()
                        if (!pairCode.isNullOrBlank()) headers["X-User-Code"] = pairCode
                    } catch (_: Exception) {}

                    try {
                        extractor.setDataSource(context, android.net.Uri.parse(path), headers)
                    } catch (directErr: Exception) {
                        Log.w(TAG, "Direct setDataSource with headers failed, trying temp file", directErr)
                        // Fallback: download to local temp file (still off main thread)
                        val localFile = downloadToTempFile(path)
                        extractor.setDataSource(localFile)
                    }
                } else {
                    // For local files
                    extractor.setDataSource(path)
                }

                // Assign after data source set to avoid races
                mediaExtractor = extractor

                // Find tracks and prepare decoders
                findTracks()
                prepareDecoders()

                isPrepared = true
                withContext(Dispatchers.Main) {
                    onPreparedListener?.invoke()
                    if (pendingStart) {
                        pendingStart = false
                        start()
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error setting video path", e)
                withContext(Dispatchers.Main) {
                    onErrorListener?.invoke("Failed to set video path: ${e.message}")
                }
            }
        }
    }
    
    private fun downloadToTempFile(url: String): String {
        Log.d(TAG, "Downloading video from URL: $url")
        // Ensure this runs off the main thread
        if (Looper.myLooper() == Looper.getMainLooper()) {
            throw IOException("downloadToTempFile called on main thread")
        }

        val connection = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10000
            readTimeout = 30000
            setRequestProperty("User-Agent", "CustomVideoDecoder Android")
            // Add authorization header if needed
            try {
                val pairCode = com.pizzahut.tv.api.PairCodeHolder.get()
                if (!pairCode.isNullOrBlank()) setRequestProperty("X-User-Code", pairCode)
            } catch (_: Exception) {}
        }

        connection.connect()

        if (connection.responseCode != 200) {
            throw IOException("HTTP ${connection.responseCode}: ${connection.responseMessage}")
        }

        val tempFile = java.io.File.createTempFile("slice_video_", ".mp4", context.cacheDir)
        tempFile.deleteOnExit()

        var bytesDownloaded = 0L
        connection.inputStream.use { input ->
            tempFile.outputStream().use { output ->
                val buffer = ByteArray(8192)
                var bytesRead: Int
                while (input.read(buffer).also { bytesRead = it } != -1) {
                    output.write(buffer, 0, bytesRead)
                    bytesDownloaded += bytesRead
                }
            }
        }

        Log.d(TAG, "Downloaded $bytesDownloaded bytes to ${tempFile.absolutePath}")
        return tempFile.absolutePath
    }
    
    private fun findTracks() {
        val extractor = mediaExtractor ?: return
        
        for (i in 0 until extractor.trackCount) {
            val format = extractor.getTrackFormat(i)
            val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
            
            when {
                mime.startsWith("video/") && videoTrackIndex == -1 -> {
                    videoTrackIndex = i
                    Log.d(TAG, "Found video track $i: $mime")
                }
                mime.startsWith("audio/") && audioTrackIndex == -1 -> {
                    audioTrackIndex = i
                    Log.d(TAG, "Found audio track $i: $mime")
                }
            }
        }
        
        if (videoTrackIndex == -1) {
            throw IOException("No video track found")
        }
    }
    
    private fun prepareDecoders() {
        val extractor = mediaExtractor ?: return
        
        // Prepare video decoder
        if (videoTrackIndex >= 0) {
            val videoFormat = extractor.getTrackFormat(videoTrackIndex)
            val videoMime = videoFormat.getString(MediaFormat.KEY_MIME)!!
            
            Log.d(TAG, "Creating video decoder for: $videoMime")
            
            try {
                // First try hardware decoder
                videoDecoder = MediaCodec.createDecoderByType(videoMime)
                Log.d(TAG, "Created hardware decoder: ${videoDecoder?.name}")
            } catch (e: Exception) {
                Log.w(TAG, "Hardware decoder failed, trying software", e)
                try {
                    // Force software decoder by finding software codec
                    val codecList = MediaCodecList(MediaCodecList.REGULAR_CODECS)
                    for (codecInfo in codecList.codecInfos) {
                        if (!codecInfo.isEncoder && !codecInfo.isHardwareAccelerated) {
                            for (supportedType in codecInfo.supportedTypes) {
                                if (supportedType.equals(videoMime, ignoreCase = true)) {
                                    Log.d(TAG, "Found software codec: ${codecInfo.name}")
                                    videoDecoder = MediaCodec.createByCodecName(codecInfo.name)
                                    break
                                }
                            }
                            if (videoDecoder != null) break
                        }
                    }
                } catch (e2: Exception) {
                    Log.e(TAG, "Failed to create software decoder", e2)
                    throw e2
                }
            }
            
            videoDecoder?.configure(videoFormat, surfaceView.holder.surface, null, 0)
        }
        
        // Prepare audio decoder if audio track exists
        if (audioTrackIndex >= 0) {
            val audioFormat = extractor.getTrackFormat(audioTrackIndex)
            val audioMime = audioFormat.getString(MediaFormat.KEY_MIME)!!
            
            try {
                audioDecoder = MediaCodec.createDecoderByType(audioMime)
                audioDecoder?.configure(audioFormat, null, null, 0)
                
                // Create AudioTrack
                val sampleRate = audioFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                val channelCount = audioFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                val channelConfig = if (channelCount == 1) AudioFormat.CHANNEL_OUT_MONO else AudioFormat.CHANNEL_OUT_STEREO
                
                val bufferSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, AudioFormat.ENCODING_PCM_16BIT)
                
                audioTrack = AudioTrack.Builder()
                    .setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .setContentType(AudioAttributes.CONTENT_TYPE_MOVIE)
                            .build()
                    )
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(sampleRate)
                            .setChannelMask(channelConfig)
                            .build()
                    )
                    .setBufferSizeInBytes(bufferSize)
                    .build()
                
                Log.d(TAG, "Audio track prepared: ${sampleRate}Hz, ${channelCount}ch")
                
            } catch (e: Exception) {
                Log.w(TAG, "Audio decoder setup failed", e)
                audioDecoder = null
                audioTrack = null
            }
        }
    }
    
    fun start() {
        if (!isPrepared) { pendingStart = true; return }
        
        if (isPlaying) {
            Log.w(TAG, "Already playing")
            return
        }
        
        isPlaying = true
        
        try {
            videoDecoder?.start()
            audioDecoder?.start()
            audioTrack?.play()
            
            // Start decoding in background
            decoderJob = CoroutineScope(Dispatchers.Default).launch {
                decode()
            }
            
            Log.d(TAG, "Playback started")
            
        } catch (e: Exception) {
            Log.e(TAG, "Error starting playback", e)
            onErrorListener?.invoke("Playback error: ${e.message}")
        }
    }
    
    private suspend fun decode() {
        val extractor = mediaExtractor ?: return
        val vDecoder = videoDecoder
        val aDecoder = audioDecoder
        val aTrack = audioTrack
        
        // Select tracks once at the beginning
        extractor.selectTrack(videoTrackIndex)
        if (audioTrackIndex >= 0 && aDecoder != null) {
            // Don't select audio track if we're already on video - will cause issues
            // We'll switch tracks only when needed
        }
        
    val videoInputBuffers = vDecoder?.inputBuffers
    val videoOutputBuffers = vDecoder?.outputBuffers
        val audioInputBuffers = aDecoder?.inputBuffers
        val audioOutputBuffers = aDecoder?.outputBuffers
        
        val videoBufferInfo = MediaCodec.BufferInfo()
        val audioBufferInfo = MediaCodec.BufferInfo()
        
    var videoInputDone = false
        var audioInputDone = false
        var videoOutputDone = false
        var audioOutputDone = false
    // Revert: no first-frame signaling
        
        val timeoutUs = 10000L
        var lastTrackSelected = videoTrackIndex
        
        try {
            while (isPlaying && (!videoOutputDone || (aDecoder != null && !audioOutputDone))) {
                
                // Feed video input
                if (!videoInputDone && vDecoder != null) {
                    val inputIndex = vDecoder.dequeueInputBuffer(timeoutUs)
                    if (inputIndex >= 0) {
                        val inputBuffer = if (videoInputBuffers != null) {
                            videoInputBuffers[inputIndex]
                        } else {
                            vDecoder.getInputBuffer(inputIndex)
                        }
                        
                        // Only switch track if necessary
                        if (lastTrackSelected != videoTrackIndex) {
                            extractor.selectTrack(videoTrackIndex)
                            lastTrackSelected = videoTrackIndex
                        }
                        
                        val sampleSize = try {
                            extractor.readSampleData(inputBuffer!!, 0)
                        } catch (e: IllegalArgumentException) {
                            Log.w(TAG, "Video read sample failed, trying to recover", e)
                            -1
                        }
                        
                        if (sampleSize >= 0) {
                            vDecoder.queueInputBuffer(
                                inputIndex, 0, sampleSize,
                                extractor.sampleTime, 0
                            )
                            extractor.advance()
                        } else {
                            vDecoder.queueInputBuffer(
                                inputIndex, 0, 0, 0,
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM
                            )
                            videoInputDone = true
                        }
                    }
                }
                
                // Feed audio input (simplified approach - video only for now)
                if (!audioInputDone && aDecoder != null && audioTrackIndex >= 0) {
                    // Skip audio processing for now to avoid track switching issues
                    audioInputDone = true
                }
                
                // Handle video output
                if (!videoOutputDone && vDecoder != null) {
                    val outputIndex = vDecoder.dequeueOutputBuffer(videoBufferInfo, timeoutUs)
                    
                    when {
                        outputIndex >= 0 -> {
                            // Render frame to surface only if it's still valid
                            val renderToSurface = try {
                                surfaceView.holder.surface.isValid
                            } catch (_: Exception) { false }
                            try {
                                if (!renderToSurface) {
                                    vDecoder.releaseOutputBuffer(outputIndex, false)
                                } else {
                                    vDecoder.releaseOutputBuffer(outputIndex, true)
                                }
                            } catch (e: Exception) {
                                Log.e(TAG, "Release output buffer failed (render=$renderToSurface)", e)
                            }
                            
                            if ((videoBufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                                videoOutputDone = true
                            }
                        }
                        outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                            Log.d(TAG, "Video output format changed: ${vDecoder.outputFormat}")
                        }
                    }
                }
                
                // Handle audio output
                if (!audioOutputDone && aDecoder != null && aTrack != null) {
                    val outputIndex = aDecoder.dequeueOutputBuffer(audioBufferInfo, timeoutUs)
                    
                    when {
                        outputIndex >= 0 -> {
                            val outputBuffer = if (audioOutputBuffers != null) {
                                audioOutputBuffers[outputIndex]
                            } else {
                                aDecoder.getOutputBuffer(outputIndex)
                            }
                            
                            if (audioBufferInfo.size > 0) {
                                val audioData = ByteArray(audioBufferInfo.size)
                                outputBuffer?.get(audioData)
                                outputBuffer?.rewind()
                                
                                aTrack.write(audioData, 0, audioData.size)
                            }
                            
                            aDecoder.releaseOutputBuffer(outputIndex, false)
                            
                            if ((audioBufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                                audioOutputDone = true
                            }
                        }
                        outputIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                            Log.d(TAG, "Audio output format changed: ${aDecoder.outputFormat}")
                        }
                    }
                }
                
                // Small delay to prevent tight loop
                delay(16) // ~60fps
            }
            
            withContext(Dispatchers.Main) {
                onCompletionListener?.invoke()
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "Decode error", e)
            withContext(Dispatchers.Main) {
                onErrorListener?.invoke("Decode error: ${e.message}")
            }
        }
    }
    
    fun pause() {
        isPlaying = false
        decoderJob?.cancel()
        audioTrack?.pause()
    }
    
    fun stop() {
        isPlaying = false
        decoderJob?.cancel()
        audioTrack?.stop()
    }
    
    fun release() {
        stop()
        
        try {
            videoDecoder?.stop()
            videoDecoder?.release()
            videoDecoder = null
            
            audioDecoder?.stop()
            audioDecoder?.release()
            audioDecoder = null
            
            audioTrack?.release()
            audioTrack = null
            
            mediaExtractor?.release()
            mediaExtractor = null
            
            isPrepared = false
            pendingStart = false
            
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing resources", e)
        }
    }
}