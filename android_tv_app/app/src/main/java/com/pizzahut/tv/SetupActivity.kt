package com.pizzahut.tv

import android.content.Intent
import android.os.Bundle
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.pizzahut.tv.api.ApiClient
import kotlinx.coroutines.Dispatchers
import java.net.SocketTimeoutException
import java.net.ConnectException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SetupActivity : AppCompatActivity() {
	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		setContentView(R.layout.activity_setup)
	// Make pairing code accessible to network layer
	com.pizzahut.tv.api.PairCodeHolder.init(applicationContext)

		val codeInput = findViewById<EditText>(R.id.editTextPairCode)
		val codeBtn = findViewById<Button>(R.id.buttonVerifyCode)
		val codeStatus = findViewById<TextView>(R.id.codeStatusText)
	// Store selection moved to StoreSelectActivity

	val prefs = getSharedPreferences("phtv", MODE_PRIVATE)

	var verifiedCode: String? = null

		fun verifyCode() {
			val code = codeInput.text?.toString()?.trim().orEmpty()
			if (code.length != 4 || code.any { !it.isDigit() }) {
				codeStatus.text = "Enter 4-digit code"
				codeInput.requestFocus(); return
			}
			codeStatus.text = "Verifying…"
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
					val resp = withContext(Dispatchers.IO) { ApiClient.service.getStoresByCode(code) }
					if (!resp.success) { codeStatus.text = resp.error ?: "Invalid code"; return@launch }
					verifiedCode = code
					prefs.edit().putString("pairCode", code).apply()
					codeStatus.text = "Code linked"
					// Navigate to StoreSelectActivity (step 2)
					val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
					i.putExtra("pairCode", code)
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


		codeBtn.setOnClickListener { verifyCode() }
		codeInput.setOnEditorActionListener { _, actionId, _ ->
			if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) {
				verifyCode(); true
			} else false
		}

		// If a code was previously linked, jump directly to store selection
		prefs.getString("pairCode", null)?.let { saved ->
			if (saved.length == 4 && saved.all { it.isDigit() }) {
				val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
				i.putExtra("pairCode", saved)
				i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
				startActivity(i)
				finish()
			}
		}
	}

	override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
		// Don’t auto-start; require explicit selection
		return super.onKeyDown(keyCode, event)
	}
}

