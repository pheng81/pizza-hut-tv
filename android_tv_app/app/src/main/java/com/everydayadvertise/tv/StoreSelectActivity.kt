package com.everydayadvertise.tv

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.setPadding
import androidx.lifecycle.lifecycleScope
import com.everydayadvertise.tv.api.ApiClient
import com.everydayadvertise.tv.api.PairCodeHolder
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject

class StoreSelectActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_store_select)
        PairCodeHolder.init(applicationContext)

        val storeInput = findViewById<EditText>(R.id.editTextStoreId)
        val fetchBtn = findViewById<Button>(R.id.buttonFetchScreens)
        val changeCodeBtn = findViewById<Button>(R.id.buttonChangeCode)
        val tvCodeView = findViewById<TextView>(R.id.tvCode)
        val status = findViewById<TextView>(R.id.statusText)
        val container = findViewById<LinearLayout>(R.id.screensContainer)
        val scrollView = findViewById<android.widget.ScrollView>(R.id.scrollView)
        val qrCodeImageView = findViewById<ImageView>(R.id.qrCodeStoreImageView)

        val pairCode = intent.getStringExtra("pairCode")
        val prefs = getSharedPreferences(PairCodeHolder.PREFS_NAME, MODE_PRIVATE)
        if (!prefs.contains(PairCodeHolder.KEY_PAIR_CODE)) {
            val legacyPrefs = getSharedPreferences("phtv", MODE_PRIVATE)
            val legacyCode = legacyPrefs.getString(PairCodeHolder.KEY_PAIR_CODE, null)
            val legacySession = legacyPrefs.getString("sessionId", null)
            if (!legacyCode.isNullOrEmpty()) {
                prefs.edit().apply {
                    putString(PairCodeHolder.KEY_PAIR_CODE, legacyCode)
                    if (!legacySession.isNullOrEmpty()) {
                        putString("sessionId", legacySession)
                    }
                }.apply()
            }
        }
        if (!pairCode.isNullOrBlank()) {
            prefs.edit().putString(PairCodeHolder.KEY_PAIR_CODE, pairCode).apply()
        }
        val effectiveCode = (pairCode ?: prefs.getString(PairCodeHolder.KEY_PAIR_CODE, null)).orEmpty()
        tvCodeView?.text = "TV code: ${effectiveCode.ifBlank { "—" }}"

        // Join the same WebSocket session used during pairing so mobile can send the store code
        val sessionId = intent.getStringExtra("sessionId") ?: prefs.getString("sessionId", null) ?: run {
            // Generate new session ID if none exists
            val r = java.util.UUID.randomUUID().toString().replace("-", "")
            val newId = "tv_" + r.take(12)
            prefs.edit().putString("sessionId", newId).apply()
            newId
        }

        // Generate QR code for mobile store entry
        fun generateStoreQRCode() {
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val handoffUrl = "https://everydayadvertise.com/webplayer?session=$sessionId"
                    val qrCodeWriter = QRCodeWriter()
                    val hints = mapOf(
                        com.google.zxing.EncodeHintType.ERROR_CORRECTION to com.google.zxing.qrcode.decoder.ErrorCorrectionLevel.H,
                        com.google.zxing.EncodeHintType.MARGIN to 1
                    )
                    val bitMatrix = qrCodeWriter.encode(handoffUrl, BarcodeFormat.QR_CODE, 512, 512, hints)
                    val width = bitMatrix.width
                    val height = bitMatrix.height
                    
                    val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.RGB_565)
                    for (x in 0 until width) {
                        for (y in 0 until height) {
                            bmp.setPixel(x, y, if (bitMatrix[x, y]) Color.BLACK else Color.WHITE)
                        }
                    }
                    
                    withContext(Dispatchers.Main) {
                        qrCodeImageView?.setImageBitmap(bmp)
                    }
                } catch (e: Exception) {
                    android.util.Log.e("StoreSelectActivity", "Failed to generate QR code", e)
                }
            }
        }
        
        // Generate QR code on startup
        generateStoreQRCode()

        fun fetchScreens() {
            val storeId = storeInput.text?.toString()?.trim().orEmpty()
            if (storeId.isEmpty()) { status.text = "Enter your store number"; storeInput.requestFocus(); return }
            status.text = "Loading screens..."
            container.removeAllViews()
            lifecycleScope.launch {
                try {
                    val resp = withContext(Dispatchers.IO) { ApiClient.service.getScreens(storeId) }
                    val screens = resp.screens
                    if (screens.isEmpty()) { status.text = "No screens found for store $storeId (0)"; return@launch }
                    status.text = "Select a screen"
                    prefs.edit().putString("storeId", storeId).apply()
                    val targetPx = (720 * resources.displayMetrics.density).toInt()
                    screens.forEach { s ->
                        val screenLabel = s.id.removePrefix("${storeId}_")
                        val b = Button(this@StoreSelectActivity).apply {
                            text = screenLabel
                            textSize = 20f
                            isAllCaps = false
                            setPadding(24)
                            setTextColor(0xFFE6EDF3.toInt())
                            
                            // Disable background tint to allow custom backgrounds
                            backgroundTintList = null
                            
                            // Set initial background (dark slate/unfocused state)
                            val initialBg = android.graphics.drawable.GradientDrawable()
                            initialBg.setColor(0xFF37474F.toInt())
                            initialBg.cornerRadius = 14f * resources.displayMetrics.density
                            background = initialBg
                            
                            // Focus color change
                            setOnFocusChangeListener { view, hasFocus ->
                                view.backgroundTintList = null
                                if (hasFocus) {
                                    // Red when focused
                                    val gd = android.graphics.drawable.GradientDrawable()
                                    gd.setColor(0xFFE31837.toInt())
                                    gd.cornerRadius = 14f * resources.displayMetrics.density
                                    view.background = gd
                                    (view as Button).setTextColor(0xFFFFFFFF.toInt())
                                } else {
                                    // Dark slate gray when not focused
                                    val gd = android.graphics.drawable.GradientDrawable()
                                    gd.setColor(0xFF37474F.toInt())
                                    gd.cornerRadius = 14f * resources.displayMetrics.density
                                    view.background = gd
                                    (view as Button).setTextColor(0xFFE6EDF3.toInt())
                                }
                            }
                            
                            setOnClickListener {
                                prefs.edit().putString("screenId", s.id).apply()
                                val i = Intent(this@StoreSelectActivity, TvDisplayActivity::class.java)
                                i.putExtra("storeId", storeId)
                                i.putExtra("screenId", s.id)
                                i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
                                startActivity(i)
                                finish()
                            }
                        }
                        val lp = LinearLayout.LayoutParams(targetPx, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = 16; gravity = Gravity.CENTER_HORIZONTAL }
                        container.addView(b, lp)
                    }
                    
                    // Scroll to show screen buttons and focus first one
                    container.post {
                        scrollView?.smoothScrollTo(0, container.top)
                        
                        // Focus the first screen button
                        if (container.childCount > 0) {
                            container.getChildAt(0).requestFocus()
                        }
                    }
                } catch (e: Exception) {
                    val msg = (e.message ?: "").lowercase()
                    status.text = when {
                        msg.contains("403") || msg.contains("forbidden") -> "Pairing code required or invalid. Please go back and link code first."
                        msg.contains("404") && msg.contains("store") -> "Store $storeId not found for this account."
                        else -> ("Network error: ${e.javaClass.simpleName}: ${e.message}").take(140)
                    }
                }
            }
        }

        var socket: Socket? = null
        fun joinSession(host: String) {
            try {
                val opts = IO.Options()
                opts.forceNew = true
                opts.reconnection = true
                opts.transports = arrayOf("websocket", "polling")
                
                // WORKAROUND: Apply SSL bypass for old Android TV (same as SetupActivity)
                try {
                    val okHttpClient = okhttp3.OkHttpClient.Builder()
                        .sslSocketFactory(
                            com.everydayadvertise.tv.api.TrustAllCerts.getUnsafeSSLSocketFactory(),
                            com.everydayadvertise.tv.api.TrustAllCerts.getTrustManager()
                        )
                        .hostnameVerifier(com.everydayadvertise.tv.api.TrustAllCerts.getAllTrustingHostnameVerifier())
                        .build()
                    opts.callFactory = okHttpClient
                    opts.webSocketFactory = okHttpClient
                } catch (e: Exception) {
                    android.util.Log.w("StoreSelectActivity", "Failed to apply SSL workaround", e)
                }
                
                socket?.let { try { it.off(); it.disconnect() } catch (_: Exception) {} }
                val s = IO.socket(host, opts)
                s.on(Socket.EVENT_CONNECT) {
                    if (!sessionId.isNullOrBlank()) {
                        s.emit("join_session", JSONObject().put("session_id", sessionId))
                        runOnUiThread { status.text = "Connected. Waiting for store code…" }
                    }
                }
                s.on("store_code_entered") { args ->
                    try {
                        if (args.isNotEmpty()) {
                            val obj = args[0] as? JSONObject ?: return@on
                            val sid = obj.optString("session_id")
                            val sc = obj.optString("store_code")
                            if (sid == sessionId && sc.isNotBlank()) {
                                runOnUiThread {
                                    storeInput.setText(sc)
                                    if (sc.length >= 4) {
                                        status.text = "Store code received"
                                        // Auto-fetch after a brief delay when full code present
                                        storeInput.postDelayed({ fetchScreens() }, 300)
                                    } else {
                                        status.text = "Store code received… waiting for full code"
                                    }
                                }
                            }
                        }
                    } catch (_: Exception) {}
                }
                // Mobile selects a screen on browse page -> TV should auto-navigate
                s.on("screen_selected") { args ->
                    try {
                        if (args.isNotEmpty()) {
                            val obj = args[0] as? JSONObject ?: return@on
                            val sid = obj.optString("session_id")
                            val screenId = obj.optString("screen_id")
                            val storeId = obj.optString("store_id")
                            if (sid == sessionId && screenId.isNotBlank()) {
                                runOnUiThread {
                                    val finalStore = if (storeId.isNullOrBlank()) storeInput.text?.toString()?.trim().orEmpty() else storeId
                                    // Persist for later
                                    prefs.edit().putString("storeId", finalStore).putString("screenId", screenId).apply()
                                    val i = Intent(this@StoreSelectActivity, TvDisplayActivity::class.java)
                                    i.putExtra("storeId", finalStore)
                                    i.putExtra("screenId", screenId)
                                    i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
                                    startActivity(i)
                                    finish()
                                }
                            }
                        }
                    } catch (_: Exception) {}
                }
                s.connect()
                socket = s
            } catch (_: Exception) {}
        }
        if (!sessionId.isNullOrBlank()) {
            // Try main host first, then API
            joinSession("https://everydayadvertise.com")
            storeInput.postDelayed({ if (socket?.connected() != true) joinSession("https://api.everydayadvertise.com") }, 2500)
        }

        // HTTP polling fallback for store code in case Socket.IO delivery is blocked
        fun startStorePollingFallback() {
            if (sessionId.isNullOrBlank()) return
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    // Build two URLs: main and api hosts
                    val mainBase = com.everydayadvertise.tv.api.ApiClient.baseUrl.replace("api.", "")
                    val urls = listOf(
                        (mainBase + "api/store_session_poll/" + sessionId!!).replace("//webplayer", "/webplayer"),
                        com.everydayadvertise.tv.api.ApiClient.baseUrl + "store_session_poll/" + sessionId!!
                    )
                    var tries = 0
                    var lastSeen: String? = null
                    while (tries < 90) { // up to ~90s
                        var received: String? = null
                        for (u in urls) {
                            try {
                                (java.net.URL(u).openConnection() as java.net.HttpURLConnection).apply {
                                    connectTimeout = 2000; readTimeout = 2000; requestMethod = "GET"
                                    inputStream.use { stream ->
                                        val txt = stream.bufferedReader().readText()
                                        val m = Regex("\"store_code\"\\s*:\\s*\"([0-9]{1,8})\"").find(txt)
                                        received = m?.groupValues?.getOrNull(1)
                                    }
                                }
                            } catch (_: Exception) { /* try next url */ }
                            if (!received.isNullOrEmpty()) break
                        }
                        if (!received.isNullOrEmpty()) {
                            val sc = received!!
                            if (sc != lastSeen) {
                                lastSeen = sc
                                withContext(Dispatchers.Main) {
                                    storeInput.setText(sc)
                                    if (sc.length >= 4) {
                                        status.text = "Store code received"
                                        storeInput.postDelayed({ fetchScreens() }, 200)
                                    } else {
                                        status.text = "Store code received… waiting for full code"
                                    }
                                }
                            }
                            if (sc.length >= 4) return@launch
                        }
                        tries++
                        kotlinx.coroutines.delay(1000)
                    }
                } catch (_: Exception) {}
            }
        }

        // Kick off fallback alongside socket attempts
        startStorePollingFallback()

        // Poll for screen selection as a fallback when sockets are blocked
        fun startSelectionPollingFallback() {
            if (sessionId.isNullOrBlank()) return
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val mainBase = com.everydayadvertise.tv.api.ApiClient.baseUrl.replace("api.", "")
                    val urls = listOf(
                        (mainBase + "api/selection_session_poll/" + sessionId!!).replace("//webplayer", "/webplayer"),
                        com.everydayadvertise.tv.api.ApiClient.baseUrl + "selection_session_poll/" + sessionId!!
                    )
                    var tries = 0
                    while (tries < 120) {
                        var storeId: String? = null
                        var screenId: String? = null
                        for (u in urls) {
                            try {
                                (java.net.URL(u).openConnection() as java.net.HttpURLConnection).apply {
                                    connectTimeout = 2000; readTimeout = 2000; requestMethod = "GET"
                                    inputStream.use { stream ->
                                        val txt = stream.bufferedReader().readText()
                                        val sm = Regex("\"screen_id\"\\s*:\\s*\"([^\"]+)\"").find(txt)
                                        val tm = Regex("\"store_id\"\\s*:\\s*\"([^\"]*)\"").find(txt)
                                        screenId = sm?.groupValues?.getOrNull(1)
                                        storeId = tm?.groupValues?.getOrNull(1)
                                    }
                                }
                            } catch (_: Exception) {}
                            if (!screenId.isNullOrBlank()) break
                        }
                        if (!screenId.isNullOrBlank()) {
                            val finalStore = (storeId ?: storeInput.text?.toString()?.trim().orEmpty())
                            withContext(Dispatchers.Main) {
                                prefs.edit().putString("storeId", finalStore).putString("screenId", screenId).apply()
                                val i = Intent(this@StoreSelectActivity, TvDisplayActivity::class.java)
                                i.putExtra("storeId", finalStore)
                                i.putExtra("screenId", screenId)
                                i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
                                startActivity(i)
                                finish()
                            }
                            return@launch
                        }
                        tries++
                        kotlinx.coroutines.delay(1000)
                    }
                } catch (_: Exception) {}
            }
        }

        startSelectionPollingFallback()

        changeCodeBtn.setOnClickListener {
            prefs.edit().remove(PairCodeHolder.KEY_PAIR_CODE).apply()
            val i = Intent(this@StoreSelectActivity, SetupActivity::class.java)
            i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(i)
            finish()
        }


        // Disable any background tint that might override our colors
        fetchBtn.backgroundTintList = null
        
        // Programmatic focus color change - use solid colors directly
        fetchBtn.setOnFocusChangeListener { view, hasFocus ->
            android.util.Log.d("StoreSelectActivity", "Button focus changed: $hasFocus")
            view.backgroundTintList = null  // Clear tint on every focus change
            if (hasFocus) {
                // Red when focused
                val gd = android.graphics.drawable.GradientDrawable()
                gd.setColor(0xFFE31837.toInt())
                gd.cornerRadius = 14f * resources.displayMetrics.density
                view.background = gd
                (view as Button).setTextColor(0xFFFFFFFF.toInt())
            } else {
                // Dark slate gray when not focused
                val gd = android.graphics.drawable.GradientDrawable()
                gd.setColor(0xFF37474F.toInt())
                gd.cornerRadius = 14f * resources.displayMetrics.density
                view.background = gd
                (view as Button).setTextColor(0xFFFFFFFF.toInt())
            }
        }
        
        // Set initial background AFTER layout inflation completes
        fetchBtn.post {
            fetchBtn.backgroundTintList = null  // Clear any tint
            val initialBg = android.graphics.drawable.GradientDrawable()
            initialBg.setColor(0xFF37474F.toInt())  // Dark slate initially
            initialBg.cornerRadius = 14f * resources.displayMetrics.density
            fetchBtn.background = initialBg
        }

        fetchBtn.setOnClickListener { fetchScreens() }
        storeInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) { fetchScreens(); true } else false
        }

    // Initial hint under the card
    status.text = "Tap a screen to switch"
    }
}
