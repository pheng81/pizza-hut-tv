package com.pizzahut.tv

import android.content.Context
import android.graphics.Color
import android.util.AttributeSet
import android.util.Log
import android.view.SurfaceHolder
import android.view.SurfaceView

/**
 * Custom video surface that uses our CustomVideoDecoder
 * Provides similar interface to ExoPlayer's PlayerView
 */
class CustomVideoSurfaceView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : SurfaceView(context, attrs, defStyleAttr), SurfaceHolder.Callback {
    
    private val TAG = "CustomVideoSurface"
    
    private var customDecoder: CustomVideoDecoder? = null
    private var currentVideoPath: String? = null
    private var shouldAutoPlay = false
    private var targetAutoStart = false
    // Prevent concurrent/duplicate initialization (surfaceCreated + setVideoPath racing)
    @Volatile private var isInitializingDecoder: Boolean = false
    private var lastInitMs: Long = 0L
    private val INIT_DEBOUNCE_MS = 300L
    
    // Listeners
    var onPreparedListener: (() -> Unit)? = null
    var onErrorListener: ((error: String) -> Unit)? = null
    var onCompletionListener: (() -> Unit)? = null
    
    init {
        setBackgroundColor(Color.BLACK)
        try {
            // Ensure the video surface is drawn above other content when needed (helps on some TV builds/emulators)
            this.setZOrderMediaOverlay(true)
            // Revert: bring surface explicitly on top as before
            this.setZOrderOnTop(true)
        } catch (_: Exception) { }
        holder.addCallback(this)
    }
    
    fun setVideoPath(path: String) {
        Log.d(TAG, "Setting video path: $path")
        // If same path and already playing or initializing, avoid re-initialization
        if (currentVideoPath == path && (isPlaying() || isInitializingDecoder)) {
            Log.d(TAG, "Same video path and already active/initializing; ignoring setVideoPath")
            return
        }
        currentVideoPath = path
        
        if (holder.surface?.isValid == true) {
            // Debounce rapid re-inits (emulator can churn surface callbacks)
            val now = System.currentTimeMillis()
            if (isInitializingDecoder || (now - lastInitMs) < INIT_DEBOUNCE_MS) {
                Log.d(TAG, "Init suppressed (busy/debounce)")
                shouldAutoPlay = true
                targetAutoStart = true
                return
            }
            isInitializingDecoder = true
            lastInitMs = now
            initializeDecoder()
        } else {
            // Surface not ready, will initialize in surfaceCreated
            shouldAutoPlay = true
            targetAutoStart = true
        }
    }
    
    private fun initializeDecoder() {
        val path = currentVideoPath ?: return
        
        try {
            // Release existing decoder
            customDecoder?.release()
            
            // Create new decoder
            customDecoder = CustomVideoDecoder(context, this).apply {
                onPreparedListener = {
                    Log.d(TAG, "Decoder prepared")
                    isInitializingDecoder = false
                    this@CustomVideoSurfaceView.onPreparedListener?.invoke()
                    
                    if (shouldAutoPlay || targetAutoStart) {
                        start()
                        shouldAutoPlay = false
                        targetAutoStart = false
                    }
                }
                
                onErrorListener = { error ->
                    Log.e(TAG, "Decoder error: $error")
                    isInitializingDecoder = false
                    this@CustomVideoSurfaceView.onErrorListener?.invoke(error)
                }
                
                onCompletionListener = {
                    Log.d(TAG, "Playback completed")
                    isInitializingDecoder = false
                    this@CustomVideoSurfaceView.onCompletionListener?.invoke()
                }
                
                setVideoPath(path)
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize decoder", e)
            isInitializingDecoder = false
            onErrorListener?.invoke("Decoder initialization failed: ${e.message}")
        }
    }
    
    fun start() {
        // Avoid re-entrant starts
        val dec = customDecoder
        if (dec == null) {
            Log.w(TAG, "start() called but decoder is null")
            return
        }
        if (dec.isPlaying()) {
            Log.d(TAG, "start() ignored; already playing")
            return
        }
        // Ensure we are visible and on top when starting
        try {
            this.visibility = VISIBLE
            this.bringToFront()
        } catch (_: Exception) {}
        dec.start()
    }
    
    fun pause() {
        customDecoder?.pause()
    }
    
    fun stop() {
        customDecoder?.stop()
    }
    
    fun isPlaying(): Boolean = customDecoder?.isPlaying() == true
    
    fun release() {
        customDecoder?.release()
        customDecoder = null
    }

    // Provide access to decoder to allow external configuration if needed
    fun withDecoder(block: (CustomVideoDecoder) -> Unit) {
        customDecoder?.let(block) 
    }
    // first-frame listener removed in revert
    
    // SurfaceHolder.Callback implementation
    override fun surfaceCreated(holder: SurfaceHolder) {
        Log.d(TAG, "Surface created")
        // Only initialize if we actually have a target and we're not mid-init already
        if (currentVideoPath != null && customDecoder == null && !isInitializingDecoder) {
            val now = System.currentTimeMillis()
            if ((now - lastInitMs) >= INIT_DEBOUNCE_MS) {
                isInitializingDecoder = true
                lastInitMs = now
                initializeDecoder()
            } else {
                Log.d(TAG, "surfaceCreated init suppressed by debounce")
            }
        } else {
            if (isInitializingDecoder) Log.d(TAG, "surfaceCreated skipped: init in progress")
        }
    }
    
    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        Log.d(TAG, "Surface changed: ${width}x${height}")
        // Handle surface size changes if needed
    }
    
    override fun surfaceDestroyed(holder: SurfaceHolder) {
        Log.d(TAG, "Surface destroyed")
        // Fully release decoder to avoid obsolete surface rendering issues
        customDecoder?.release()
    }
}