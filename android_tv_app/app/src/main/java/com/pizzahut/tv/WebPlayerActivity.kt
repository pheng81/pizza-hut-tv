package com.pizzahut.tv

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebResourceResponse
import android.widget.FrameLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/** WebView panorama player; performs viewport cropping in CSS instead of server slicing. */
class WebPlayerActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private var initialUrl: String? = null
    private lateinit var root: FrameLayout
    private var statusOverlay: TextView? = null
    private var triedAltHost: Boolean = false
    private var triedStaticPath: Boolean = false
    private var usingLocal: Boolean = false
    private var localBase: String = "http://10.0.2.2:5000"
    private var prodBase: String = "" // filled later
    private var currentMode: EnvPreferences.EnvMode = EnvPreferences.EnvMode.AUTO

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Enable remote debugging so we can inspect the WebView via chrome://inspect on a dev machine
        try { WebView.setWebContentsDebuggingEnabled(true) } catch (_: Throwable) {}
        root = FrameLayout(this)
        webView = WebView(this)
        root.addView(webView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        statusOverlay = TextView(this).apply {
            setBackgroundColor(0xAA000000.toInt())
            setTextColor(Color.WHITE)
            textSize = 14f
            setPadding(24,24,24,24)
            text = "Initializing Web Player..."
        }
        root.addView(statusOverlay, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT))
        setContentView(root)
        configureImmersive()

        val storeId = intent.getStringExtra("storeId")?.ifBlank { null } ?: "0000"
        val screenId = intent.getStringExtra("screenId")?.ifBlank { null } ?: "screen1"
        val debug = intent.getBooleanExtra("debug", false)

        // Determine production base from ApiClient (trim trailing slash)
        prodBase = com.pizzahut.tv.api.ApiClient.baseUrl.trimEnd('/')
        // Normalize localhost forms to 10.0.2.2 for emulator
        localBase = localBase // allow future replacement if passed via intent
        if (prodBase.contains("localhost")) prodBase = prodBase.replace("localhost", "10.0.2.2")

        // Load persisted mode
        currentMode = EnvPreferences.getMode(this)
        val lastWasLocal = EnvPreferences.getLastWasLocal(this)

        when (currentMode) {
            EnvPreferences.EnvMode.LOCAL -> {
                usingLocal = true
                val url = buildUrl(localBase, storeId, screenId, debug)
                initialUrl = url
                Log.d("WebPlayer", "Forced LOCAL mode -> $url")
                statusOverlay?.text = "LOCAL (forced)\n$url"
                webView.loadUrl(url)
                updateOverlayTint(); EnvPreferences.setLast(this, true)
            }
            EnvPreferences.EnvMode.PROD -> {
                usingLocal = false
                val url = buildUrl(prodBase, storeId, screenId, debug)
                initialUrl = url
                Log.d("WebPlayer", "Forced PROD mode -> $url")
                statusOverlay?.text = "PROD (forced)\n$url"
                webView.loadUrl(url)
                updateOverlayTint(); EnvPreferences.setLast(this, false)
            }
            EnvPreferences.EnvMode.AUTO -> {
                // Always probe in AUTO to avoid stale environment assumptions.
                val preferLocal = debug || BuildConfig.DEBUG
                probeAndLoad(localFirst = preferLocal, storeId = storeId, screenId = screenId, debug = debug)
            }
        }

        val settings: WebSettings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.allowFileAccess = false
        settings.cacheMode = WebSettings.LOAD_NO_CACHE
        settings.setSupportZoom(false)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) settings.safeBrowsingEnabled = true
        // Allow mixed content if your page is https but media is http (optional – restrict later)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        }

        webView.addJavascriptInterface(object {
            @JavascriptInterface fun heartbeat(ts: Long) { Log.d("WebPlayer", "Heartbeat from JS $ts") }
            @JavascriptInterface fun log(msg: String) { Log.d("WebPlayerJS", msg) }
        }, "NativeBridge")

        webView.setBackgroundColor(Color.BLACK)
        webView.isHorizontalScrollBarEnabled = false
        webView.isVerticalScrollBarEnabled = false

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(consoleMessage: ConsoleMessage): Boolean {
                Log.d("WebPlayerConsole", "${consoleMessage.messageLevel()}: ${consoleMessage.message()}")
                if (consoleMessage.message().contains("ERROR", true)) {
                    statusOverlay?.apply { text = "Console: ${consoleMessage.message()}"; postDelayed({ if (text?.startsWith("Console:") == true) text = "" }, 5000) }
                }
                return true
            }
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = false
            override fun onPageCommitVisible(view: WebView?, url: String?) {
                statusOverlay?.text = "Rendering..."
            }
            override fun onPageFinished(view: WebView?, url: String?) {
                Log.d("WebPlayer", "Finished $url")
                statusOverlay?.text = ""
                // Inject a tiny diagnostic script to report DOM state
                view?.evaluateJavascript("(function(){try{return JSON.stringify({title:document.title,ready:document.readyState,body:!!document.body,children:document.body?document.body.children.length:0,htmlLength:document.documentElement?document.documentElement.outerHTML.length:0});}catch(e){return JSON.stringify({error:e.message});}})();") { result ->
                    Log.d("WebPlayerDiag", "DOM: $result")
                }
            }
            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                val desc = error.description
                Log.e("WebPlayer", "Load error: $desc")
                statusOverlay?.text = "Error: $desc (retrying)"
                view.postDelayed({ view.reload() }, 4000)
            }
            override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
                // Only log main frame issues for clarity
                if (request.isForMainFrame) {
                    Log.e("WebPlayer", "HTTP error: ${errorResponse.statusCode} ${errorResponse.reasonPhrase} for ${request.url}")
                    statusOverlay?.text = "HTTP ${errorResponse.statusCode}"
                    // Retry strategy chain: api. -> root domain -> /static/ path -> asset fallback
                    val failing = request.url.toString()
                    if (errorResponse.statusCode == 404) {
                        // If in AUTO mode and we haven't tried switching environments yet, attempt the alternate base once before host/path fallbacks
                        if (currentMode == EnvPreferences.EnvMode.AUTO) {
                            val isCurrentLocal = usingLocal
                            val alternateBase = if (isCurrentLocal) prodBase else localBase
                            val currentBase = if (isCurrentLocal) localBase else prodBase
                            if (failing.startsWith(currentBase) && !failing.startsWith(alternateBase)) {
                                try {
                                    val uri = android.net.Uri.parse(failing)
                                    val storeQ = uri.getQueryParameter("store") ?: "0000"
                                    val screenQ = uri.getQueryParameter("screen") ?: "screen1"
                                    usingLocal = !isCurrentLocal
                                    EnvPreferences.setLast(this@WebPlayerActivity, usingLocal)
                                    val swapUrl = buildUrl(alternateBase, storeQ, screenQ, uri.getQueryParameter("debug") == "1")
                                    Log.w("WebPlayer", "AUTO: 404 -> switching environment to ${if (usingLocal) "LOCAL" else "PROD"} $swapUrl")
                                    statusOverlay?.text = "404 -> switch ${if (usingLocal) "LOCAL" else "PROD"}" 
                                    view.loadUrl(swapUrl)
                                    updateOverlayTint()
                                    return
                                } catch (_: Exception) {}
                            }
                        }
                        if (!triedAltHost && failing.contains("://api.")) {
                            triedAltHost = true
                            val alt = failing.replace("://api.", "://")
                            Log.w("WebPlayer", "Retry alt host $alt")
                            statusOverlay?.text = "404 -> alt host"
                            view.loadUrl(alt)
                            return
                        } else if (!triedStaticPath && !failing.contains("/static/")) {
                            triedStaticPath = true
                            val uri = android.net.Uri.parse(failing)
                            val rebuilt = uri.buildUpon().path("/static" + uri.path).build().toString()
                            Log.w("WebPlayer", "Retry static path $rebuilt")
                            statusOverlay?.text = "404 -> /static/"
                            view.loadUrl(rebuilt)
                            return
                        } else {
                            // Asset fallback if provided
                            try {
                                assets.open("webplayer_embed.html").close()
                                val assetUrl = "file:///android_asset/webplayer_embed.html?store=$storeId&screen=$screenId"
                                Log.w("WebPlayer", "Falling back to asset: $assetUrl")
                                statusOverlay?.text = "Local fallback"
                                view.loadUrl(assetUrl)
                                return
                            } catch (_: Exception) {}
                        }
                    }
                    // For non-404 reuse reload with delay to avoid tight loop
                    view.postDelayed({ view.reload() }, 4000)
                }
            }
            override fun onRenderProcessGone(view: WebView, detail: android.webkit.RenderProcessGoneDetail): Boolean {
                Log.e("WebPlayer", "Render process gone (didCrash=${detail.didCrash()})")
                statusOverlay?.text = "Web process crashed – reloading"
                // Recreate WebView gracefully
                root.removeView(webView)
                webView.destroy()
                webView = WebView(this@WebPlayerActivity)
                root.addView(webView, 0)
                // Best-effort minimal re-init (reuse initialUrl)
                webView.settings.javaScriptEnabled = true
                webView.webViewClient = this
                webView.webChromeClient = object : WebChromeClient() {}
                initialUrl?.let { webView.loadUrl(it) }
                return true
            }
        }

        // (Initial navigation done in probeAndLoad once probe resolves)
    }

    private fun buildUrl(base: String, storeId: String, screenId: String, debug: Boolean): String {
        return base.trimEnd('/') + "/webplayer_embed.html?store=" + storeId + "&screen=" + screenId + (if (debug) "&debug=1" else "")
    }

    private fun probeAndLoad(localFirst: Boolean, storeId: String, screenId: String, debug: Boolean) {
        val prod = prodBase
        val local = localBase
        val tryOrder = if (localFirst) listOf(local, prod) else listOf(prod, local)
        statusOverlay?.text = "Probing hosts..."
        Thread {
            var selected: String? = null
            for (candidate in tryOrder) {
                if (probe(candidate)) {
                    selected = candidate
                    break
                }
            }
            if (selected == null) selected = tryOrder.first() // fallback even if probe failed
            usingLocal = (selected == local)
            val url = buildUrl(selected, storeId, screenId, debug)
            initialUrl = url
            Log.d("WebPlayer", "Loading $url (usingLocal=$usingLocal)")
            runOnUiThread {
                statusOverlay?.text = "Loading: ${if (usingLocal) "LOCAL" else "PROD"}\n$url"
                webView.loadUrl(url)
                updateOverlayTint()
            }
        }.start()
    }

    private fun probe(base: String): Boolean {
        return try {
            val url = java.net.URL(base + "/health")
            val conn = (url.openConnection() as java.net.HttpURLConnection).apply { connectTimeout = 1500; readTimeout = 1500; requestMethod = "GET" }
            conn.connect()
            val code = conn.responseCode
            conn.disconnect()
            code in 200..399
        } catch (e: Exception) {
            false
        }
    }

    private fun toggleEnvironment() {
        usingLocal = !usingLocal
        EnvPreferences.setLast(this, usingLocal)
        val base = if (usingLocal) localBase else prodBase
        statusOverlay?.text = "Switching to ${if (usingLocal) "LOCAL" else "PROD"}... (mode=${currentMode.name})"
        initialUrl?.let {
            val uri = android.net.Uri.parse(it)
            val store = uri.getQueryParameter("store") ?: "0000"
            val screen = uri.getQueryParameter("screen") ?: "screen1"
            val debug = uri.getQueryParameter("debug") == "1"
            val newUrl = buildUrl(base, store, screen, debug)
            Log.d("WebPlayer", "Manual toggle -> $newUrl")
            webView.loadUrl(newUrl)
            initialUrl = newUrl
            updateOverlayTint()
        }
    }

    private fun updateOverlayTint() {
        statusOverlay?.setBackgroundColor(if (usingLocal) 0xAA004400.toInt() else 0xAA000044.toInt())
    }

    private fun configureImmersive() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val controller = WindowInsetsControllerCompat(window, window.decorView)
        controller.hide(WindowInsetsCompat.Type.systemBars())
        controller.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        window.addFlags(WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or WindowManager.LayoutParams.FLAG_FULLSCREEN or WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    override fun onResume() { super.onResume(); webView.onResume() }
    override fun onPause() { webView.onPause(); super.onPause() }
    override fun onDestroy() { webView.destroy(); super.onDestroy() }

    override fun onBackPressed() { if (webView.canGoBack()) webView.goBack() else super.onBackPressed() }

    // Debug helper: long-press DPAD_CENTER to reload
    override fun dispatchKeyEvent(event: android.view.KeyEvent): Boolean {
        if (event.action == android.view.KeyEvent.ACTION_DOWN && event.repeatCount > 20) {
            when (event.keyCode) {
                android.view.KeyEvent.KEYCODE_DPAD_CENTER -> {
                    statusOverlay?.text = "Manual reload (${if (usingLocal) "LOCAL" else "PROD"})..."
                    webView.reload()
                    return true
                }
                android.view.KeyEvent.KEYCODE_DPAD_RIGHT -> {
                    statusOverlay?.text = "Loading test page..."
                    webView.loadUrl("https://example.com")
                    return true
                }
                android.view.KeyEvent.KEYCODE_DPAD_LEFT -> {
                    statusOverlay?.text = "Toggle env..."
                    toggleEnvironment()
                    return true
                }
                android.view.KeyEvent.KEYCODE_DPAD_UP -> {
                    // Cycle mode: AUTO -> LOCAL -> PROD -> AUTO
                    currentMode = when (currentMode) {
                        EnvPreferences.EnvMode.AUTO -> EnvPreferences.EnvMode.LOCAL
                        EnvPreferences.EnvMode.LOCAL -> EnvPreferences.EnvMode.PROD
                        EnvPreferences.EnvMode.PROD -> EnvPreferences.EnvMode.AUTO
                    }
                    EnvPreferences.setMode(this, currentMode)
                    statusOverlay?.text = "Mode=${currentMode.name}"
                    // Re-run selection logic quickly using current URL params
                    val uri = initialUrl?.let { android.net.Uri.parse(it) }
                    val store = uri?.getQueryParameter("store") ?: "0000"
                    val screen = uri?.getQueryParameter("screen") ?: "screen1"
                    val debugParam = uri?.getQueryParameter("debug") == "1"
                    when (currentMode) {
                        EnvPreferences.EnvMode.LOCAL -> {
                            usingLocal = true
                            EnvPreferences.setLast(this, true)
                            val u = buildUrl(localBase, store, screen, debugParam)
                            initialUrl = u; webView.loadUrl(u)
                        }
                        EnvPreferences.EnvMode.PROD -> {
                            usingLocal = false
                            EnvPreferences.setLast(this, false)
                            val u = buildUrl(prodBase, store, screen, debugParam)
                            initialUrl = u; webView.loadUrl(u)
                        }
                        EnvPreferences.EnvMode.AUTO -> {
                            probeAndLoad(localFirst = (debugParam || BuildConfig.DEBUG), storeId = store, screenId = screen, debug = debugParam)
                        }
                    }
                    updateOverlayTint()
                    return true
                }
            }
        }
        return super.dispatchKeyEvent(event)
    }
}
