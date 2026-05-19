package com.everydayadvertise.tv

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.content.res.AppCompatResources
import androidx.lifecycle.lifecycleScope
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import com.everydayadvertise.tv.api.ApiClient
import com.everydayadvertise.tv.api.PairCodeHolder
import com.everydayadvertise.tv.ui.onboarding.OnboardingFragment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import java.net.SocketTimeoutException
import java.net.ConnectException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SetupActivity : AppCompatActivity() {
	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		setContentView(R.layout.activity_setup)
		// Make pairing code accessible to network layer
			PairCodeHolder.init(applicationContext)
			// Ensure device id exists and show small overlay for support
			try {
				com.everydayadvertise.tv.api.DeviceIdHelper.init(applicationContext)
				val id = com.everydayadvertise.tv.api.DeviceIdHelper.get(applicationContext)
				val tv = TextView(this).apply {
					text = "TV ID: ${id.take(8)}"
					setTextColor(0xFFE6EDF3.toInt())
					textSize = 12f
					setBackgroundColor(0x33000000)
					setPadding(12,6,12,6)
				}
				(this.findViewById(android.R.id.content) as? android.view.ViewGroup)?.addView(tv)
				tv.postDelayed({ tv.animate().alpha(0f).setDuration(800).withEndAction { (tv.parent as? android.view.ViewGroup)?.removeView(tv) } }, 7000)
			} catch (_: Exception) {}

		val codeInput = findViewById<EditText>(R.id.editTextPairCode)
		val codeBtn = findViewById<Button>(R.id.buttonVerifyCode)
		val codeStatus = findViewById<TextView>(R.id.codeStatusText)
		val qrCodeImageView = findViewById<ImageView>(R.id.qrCodeImageView)
		// Store selection moved to StoreSelectActivity

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
		maybeShowIntroOverlay()

		var verifiedCode: String? = null

		// Generate a session ID matching webplayer format (e.g., tv_ab12cd34ef)
		val sessionId: String = run {
			val r = java.util.UUID.randomUUID().toString().replace("-", "")
			"tv_" + r.take(12)
		}

		// Connect to Socket.IO to receive code from mobile (same as webplayer)
		// IMPROVED: Better error handling, status updates, automatic retries
		var socket: Socket? = null
		var socketConnected = false
		var retryCount = 0
		val maxRetries = 3
		
		fun connectSocketTo(host: String) {
			try {
				val opts = IO.Options()
				opts.forceNew = true
				opts.reconnection = true
				opts.reconnectionAttempts = 3
				opts.reconnectionDelay = 2000
				opts.timeout = 10000 // 10 second connection timeout
				// Start with polling for better reliability, then upgrade to websocket if available
				opts.transports = arrayOf("polling", "websocket")
				
				// WORKAROUND: Apply SSL bypass for old Android TV (same as ApiClient)
				try {
					val okHttpClient = okhttp3.OkHttpClient.Builder()
						.sslSocketFactory(
							com.everydayadvertise.tv.api.TrustAllCerts.getUnsafeSSLSocketFactory(),
							com.everydayadvertise.tv.api.TrustAllCerts.getTrustManager()
						)
						.hostnameVerifier(com.everydayadvertise.tv.api.TrustAllCerts.getAllTrustingHostnameVerifier())
						.connectTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
						.readTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
						.build()
					opts.callFactory = okHttpClient
					opts.webSocketFactory = okHttpClient
					android.util.Log.d("SetupActivity", "✅ Applied SSL workaround to Socket.IO")
				} catch (e: Exception) {
					android.util.Log.w("SetupActivity", "⚠️ Failed to apply SSL workaround to Socket.IO", e)
				}
				
				android.util.Log.d("SetupActivity", "🔌 Connecting Socket.IO to $host (attempt ${retryCount + 1}/$maxRetries)...")
				try { socket?.off(); socket?.disconnect() } catch (_: Exception) {}
				
				val s = IO.socket(host, opts)
				
				s.on(Socket.EVENT_CONNECT) {
					socketConnected = true
					retryCount = 0
					android.util.Log.d("SetupActivity", "✅ Socket connected to $host; joining session $sessionId")
					runOnUiThread { codeStatus.text = "Connected! Scan QR with phone." }
					val payload = JSONObject().put("session_id", sessionId)
					s.emit("join_session", payload)
					android.util.Log.d("SetupActivity", "📤 Emitted join_session: $sessionId")
				}
				
				s.on(Socket.EVENT_DISCONNECT) { args ->
					socketConnected = false
					val reason = args.firstOrNull()?.toString() ?: "unknown"
					android.util.Log.w("SetupActivity", "⚠️ Socket disconnected: $reason")
					runOnUiThread { codeStatus.text = "Disconnected. HTTP polling active..." }
				}
				
				s.on(Socket.EVENT_CONNECT_ERROR) { args ->
					val error = args.firstOrNull()?.toString() ?: "unknown error"
					android.util.Log.w("SetupActivity", "❌ Socket connect error on $host: $error")
					
					runOnUiThread { 
						codeStatus.text = "Connection failed. Using backup method..."
					}
					
					// Retry with exponential backoff
					if (retryCount < maxRetries) {
						retryCount++
						val delayMs = 2000L * retryCount // 2s, 4s, 6s
						android.util.Log.d("SetupActivity", "🔄 Retrying socket connection in ${delayMs}ms...")
						android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
							connectSocketTo(host)
						}, delayMs)
					} else {
						android.util.Log.w("SetupActivity", "❌ Socket connection failed after $maxRetries attempts. Using HTTP polling only.")
						runOnUiThread { codeStatus.text = "Using backup method. Scan QR or enter code." }
					}
				}
				
				// Connection timeout is handled by EVENT_CONNECT_ERROR
				
				s.on("code_entered") { args ->
					if (args.isNotEmpty()) {
						val obj = args[0] as? JSONObject ?: return@on
						val sid = obj.optString("session_id")
						val code = obj.optString("code")
						android.util.Log.d("SetupActivity", "📥 Received code_entered event: session=$sid, code=$code")
						
						if (sid == sessionId && code.length == 4) {
							android.util.Log.d("SetupActivity", "✅ Code matched session! Received via socket: $code")
							runOnUiThread {
								codeStatus.text = "Code received from phone!"
								codeInput.setText(code)
								codeInput.clearFocus()
								codeBtn.performClick()
							}
						} else {
							android.util.Log.w("SetupActivity", "⚠️ Code session mismatch: expected=$sessionId, got=$sid")
						}
					}
				}
				
				s.connect()
				socket = s
				android.util.Log.d("SetupActivity", "🔌 Socket.connect() called")
				
			} catch (e: Exception) {
				android.util.Log.e("SetupActivity", "❌ Socket connect exception for $host", e)
				runOnUiThread { codeStatus.text = "Connection error. HTTP polling active..." }
			}
		}

		fun connectSocket() { 
			socketConnected = false
			retryCount = 0
			connectSocketTo("https://everydayadvertise.com") 
		}

		// HTTP poll fallback: query server for a code if socket delivery fails
		// IMPROVED: Longer timeout (2 minutes), better error handling, status updates
		fun startPollingFallback() {
			lifecycleScope.launch(Dispatchers.IO) {
				try {
					val mainBase = ApiClient.baseUrl.replace("api.", "")
					val urls = listOf(
						(mainBase + "api/session_poll/" + sessionId).replace("//webplayer", "/webplayer"),
						ApiClient.baseUrl + "session_poll/" + sessionId // try api host too
					)
					var tries = 0
					val maxTries = 120 // 2 minutes instead of 30 seconds
					android.util.Log.d("SetupActivity", "Starting HTTP poll fallback (max ${maxTries}s)")
					
					while (tries < maxTries) {
						var received: String? = null
						try {
							for (u in urls) {
								try {
									( java.net.URL(u).openConnection() as java.net.HttpURLConnection ).apply {
										connectTimeout = 3000; readTimeout = 3000; requestMethod = "GET"
										inputStream.use { stream ->
											val txt = stream.bufferedReader().readText()
											val codeMatch = Regex("\"code\"\\s*:\\s*\"(\\d{4})\"").find(txt)
											received = codeMatch?.groupValues?.getOrNull(1)
										}
									}
									if (!received.isNullOrEmpty()) {
										android.util.Log.d("SetupActivity", "HTTP poll success from: $u")
										break
									}
								} catch (e: Exception) { 
									android.util.Log.w("SetupActivity", "HTTP poll attempt failed for $u: ${e.message}")
								}
							}
						} catch (e: Exception) { 
							android.util.Log.w("SetupActivity", "HTTP poll error: ${e.message}")
						}
						
						if (!received.isNullOrEmpty()) {
							val c = received!!
							android.util.Log.d("SetupActivity", "✅ Received code via HTTP poll: $c")
							withContext(Dispatchers.Main) {
								codeStatus.text = "Code received from phone!"
								codeInput.setText(c)
								codeInput.clearFocus()
								codeBtn.performClick()
							}
							return@launch
						}
						tries++
						
						// Update status every 10 seconds to show polling is active
						if (tries % 10 == 0 && tries < maxTries) {
							withContext(Dispatchers.Main) {
								codeStatus.text = "Waiting for code... (${tries}s)"
							}
						}
						
						coroutineContext.ensureActive()
						Thread.sleep(1000)
					}
					
					// Timeout reached
					android.util.Log.w("SetupActivity", "HTTP poll timeout after ${maxTries}s")
					withContext(Dispatchers.Main) {
						codeStatus.text = "No code received. Scan QR or enter manually."
					}
				} catch (e: Exception) {
					android.util.Log.e("SetupActivity", "HTTP poll fallback failed", e)
					withContext(Dispatchers.Main) {
						codeStatus.text = "Polling error. Please enter code manually."
					}
				}
			}
		}

		// Helper to render a drawable (including VectorDrawable) to a bitmap
		fun drawableToBitmap(drawableId: Int, width: Int, height: Int): Bitmap {
			val d = AppCompatResources.getDrawable(this@SetupActivity, drawableId)
			val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
			val c = android.graphics.Canvas(bmp)
			d?.setBounds(0, 0, width, height)
			d?.draw(c)
			return bmp
		}

		// Generate QR Code that opens the Webplayer handoff page (session-based)
		fun generateQRCode(@Suppress("UNUSED_PARAMETER") pairCode: String) {
			lifecycleScope.launch(Dispatchers.IO) {
				try {
					// URL format aligned with webplayer: https://everydayadvertise.com/webplayer?session=<id>
					val handoffUrl = "https://everydayadvertise.com/webplayer?session=$sessionId"
					android.util.Log.d("SetupActivity", "Generating QR for Webplayer URL: $handoffUrl")
					
					val qrCodeWriter = QRCodeWriter()
					// Use high error correction to allow for logo overlay
					val hints = mapOf(
						com.google.zxing.EncodeHintType.ERROR_CORRECTION to com.google.zxing.qrcode.decoder.ErrorCorrectionLevel.H,
						com.google.zxing.EncodeHintType.MARGIN to 1 // reduce quiet zone to make QR fill more of the square
					)
					val bitMatrix = qrCodeWriter.encode(handoffUrl, BarcodeFormat.QR_CODE, 512, 512, hints)
					val width = bitMatrix.width
					val height = bitMatrix.height
					android.util.Log.d("SetupActivity", "QR code size: ${width}x${height}")
					
					// Create bitmap from QR code
					val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.RGB_565)
					for (x in 0 until width) {
						for (y in 0 until height) {
							bmp.setPixel(x, y, if (bitMatrix[x, y]) Color.BLACK else Color.WHITE)
						}
					}

					// Overlay "proper" brand logo to match webplayer: white rounded square with gradient EP inside
					val overlaySize = (width * 0.24).toInt()
					val centerX = width / 2f
					val centerY = height / 2f
					val canvas = android.graphics.Canvas(bmp)
					
					// White rounded background (acts like the web's white container + 2px ring)
					val bgPaint = android.graphics.Paint().apply {
						color = Color.WHITE
						isAntiAlias = true
						style = android.graphics.Paint.Style.FILL
					}
					val half = overlaySize / 2f
					val rect = android.graphics.RectF(centerX - half, centerY - half, centerX + half, centerY + half)
					canvas.drawRoundRect(rect, overlaySize * 0.18f, overlaySize * 0.18f, bgPaint)

					// Draw the gradient EA logo vector slightly inset to leave a white border
					val inset = (overlaySize * 0.09f).toInt()
					val logoBmp = drawableToBitmap(R.drawable.ea_logo_qr, overlaySize - inset * 2, overlaySize - inset * 2)
					canvas.drawBitmap(logoBmp, centerX - (overlaySize - inset * 2) / 2f, centerY - (overlaySize - inset * 2) / 2f, null)
					
					withContext(Dispatchers.Main) {
						qrCodeImageView.setImageBitmap(bmp)
						android.util.Log.d("SetupActivity", "QR code bitmap set successfully with logo")
					}
				} catch (e: Exception) {
					android.util.Log.e("SetupActivity", "QR code generation failed", e)
					e.printStackTrace()
					withContext(Dispatchers.Main) {
						codeStatus.text = "QR code error: ${e.message}"
					}
				}
			}
		}

		// Generate QR code with saved pair code if exists, otherwise use placeholder
		val savedCode = prefs.getString(PairCodeHolder.KEY_PAIR_CODE, null)
		if (savedCode != null && savedCode.length == 4) {
			codeInput.setText(savedCode)
			generateQRCode(savedCode)
		} else {
			// Generate placeholder QR code with pairing page URL
			generateQRCode("0000")
		}

		// Start socket and HTTP poll fallback with delay to ensure QR is ready
		codeStatus.text = "Loading..."
		android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
			codeStatus.text = "Connecting..."
			android.util.Log.d("SetupActivity", "🚀 Starting connection methods: Socket.IO + HTTP polling")
			connectSocket()
			startPollingFallback()
			
			// Show helpful status after 3 seconds if still waiting
			android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
				if (!socketConnected && codeInput.text.toString().length != 4) {
					codeStatus.text = "Scan QR with phone or enter code manually"
				}
			}, 3000)
		}, 500) // Small delay to let QR finish rendering

		fun verifyCode() {
			val code = codeInput.text?.toString()?.trim().orEmpty()
			if (code.length != 4 || code.any { !it.isDigit() }) {
				codeStatus.text = "Enter 4-digit code"
				codeInput.requestFocus(); return
			}
			codeStatus.text = "Verifying…"
			// Update QR code with entered code
			generateQRCode(code)
			
			lifecycleScope.launch {
				try {
					// Optional: quick health check to avoid long timeouts when server is down
					withContext(Dispatchers.IO) {
						try {
							val url = java.net.URL(ApiClient.baseUrl + "healthz")
							(url.openConnection() as java.net.HttpURLConnection).apply {
								connectTimeout = 3000; readTimeout = 3000; requestMethod = "GET"
								inputStream.use { /* ok */ }
							}
						} catch (_: Exception) { /* ignore, proceed to API call */ }
					}
					val raw = withContext(Dispatchers.IO) { ApiClient.service.getStoresByCodeRaw(code) }
					val parsed = runCatching { JSONObject(raw) }.getOrNull()
					val ok = parsed?.optBoolean("success", false) ?: false
					if (!ok) {
						val err = parsed?.optString("error")?.takeIf { !it.isNullOrBlank() } ?: "Invalid code"
						codeStatus.text = err
						return@launch
					}
					verifiedCode = code
					prefs.edit().putString(PairCodeHolder.KEY_PAIR_CODE, code).putString("sessionId", sessionId).apply()
					codeStatus.text = "Code linked"
					// Navigate to StoreSelectActivity (step 2)
					val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
					i.putExtra("pairCode", code)
					i.putExtra("sessionId", sessionId)
					i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
					startActivity(i)
					finish()
				} catch (e: SocketTimeoutException) {
					codeStatus.text = "Network timeout connecting to server. Ensure the app is running on 10.0.2.2:5002"
				} catch (e: ConnectException) {
					codeStatus.text = "Cannot connect to server. Start Flask on 10.0.2.2:5002 or use production URL."
				} catch (e: Exception) {
					codeStatus.text = ("Network error: ${e.javaClass.simpleName}: ${e.message}").take(160)
				}
			}
		}


		// Add focus color change to Link Code button
		codeBtn.backgroundTintList = null
		codeBtn.setOnFocusChangeListener { view, hasFocus ->
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
				(view as Button).setTextColor(0xFFFFFFFF.toInt())
			}
		}
		
		// Set initial background
		codeBtn.post {
			codeBtn.backgroundTintList = null
			val initialBg = android.graphics.drawable.GradientDrawable()
			initialBg.setColor(0xFF37474F.toInt())
			initialBg.cornerRadius = 14f * resources.displayMetrics.density
			codeBtn.background = initialBg
		}

		codeBtn.setOnClickListener { verifyCode() }
		codeInput.setOnEditorActionListener { _, actionId, _ ->
			if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) {
				verifyCode(); true
			} else false
		}

		// If a code was previously linked, jump directly to store selection
		prefs.getString(PairCodeHolder.KEY_PAIR_CODE, null)?.let { saved ->
			if (saved.length == 4 && saved.all { it.isDigit() }) {
				// Ensure we have a fresh sessionId so mobile can join this session now
				val existingSession = prefs.getString("sessionId", null)
				val sid = existingSession ?: ("tv_" + java.util.UUID.randomUUID().toString().replace("-", "").take(12)).also {
					prefs.edit().putString("sessionId", it).apply()
				}

				fun navigate() {
					val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
					i.putExtra("pairCode", saved)
					i.putExtra("sessionId", sid)
					i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
					startActivity(i)
					finish()
				}

				// Always allow the intro overlay to be seen briefly before navigating away (match webplayer ~2.5s)
				android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ navigate() }, 2500L)
			}
		}
	}

	private fun maybeShowIntroOverlay() {
		// Present the onboarding flow only once, then remember completion in shared preferences.
		val prefs = getSharedPreferences(PairCodeHolder.PREFS_NAME, MODE_PRIVATE)
		if (prefs.getBoolean(OnboardingFragment.KEY_ONBOARDING_COMPLETE, false)) return
		if (supportFragmentManager.findFragmentByTag(OnboardingFragment.TAG) != null) return
		OnboardingFragment.newInstance().show(supportFragmentManager, OnboardingFragment.TAG)
	}

	override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
		// Don’t auto-start; require explicit selection
		return super.onKeyDown(keyCode, event)
	}

	override fun onDestroy() {
		super.onDestroy()
		try { val f = this::class.java.getDeclaredField("socket"); f.isAccessible = true; (f.get(this) as? Socket)?.disconnect() } catch (_: Exception) {}
	}
}

