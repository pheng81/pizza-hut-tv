package com.pizzahut.tv

import android.content.Intent
import android.os.Bundle
import android.view.KeyEvent
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.pizzahut.tv.api.ApiClient
import androidx.appcompat.app.AlertDialog
import kotlinx.coroutines.Dispatchers
import java.net.SocketTimeoutException
import java.net.ConnectException
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException

class SetupActivity : AppCompatActivity() {
	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		setContentView(R.layout.activity_setup)
	// Make pairing code accessible to network layer
	com.pizzahut.tv.api.PairCodeHolder.init(applicationContext)
	// Load any saved server override (prod/local)
	ApiClient.initFromPrefs(applicationContext)

		val codeInput = findViewById<EditText>(R.id.editTextPairCode)
		val codeBtn = findViewById<Button>(R.id.buttonVerifyCode)
		val codeStatus = findViewById<TextView>(R.id.codeStatusText)
		val title = findViewById<TextView>(R.id.appTitle)
	// Store selection moved to StoreSelectActivity
		// Long-press the title to choose environment (Production vs Local)
		title?.setOnLongClickListener {
			val options = arrayOf(
				"Production (api.everydayadvertise.com)",
				"Local Emulator (10.0.2.2:5002)",
				"Local Network (192.168.1.115:5002)"
			)
			AlertDialog.Builder(this)
				.setTitle("Select server")
				.setItems(options) { _, which ->
					when (which) {
						0 -> ApiClient.setBaseUrlOverride(applicationContext, "https://api.everydayadvertise.com/")
						1 -> ApiClient.setBaseUrlOverride(applicationContext, "http://10.0.2.2:5002/")
						2 -> ApiClient.setBaseUrlOverride(applicationContext, "http://192.168.1.115:5002/")
					}
					Toast.makeText(this, "Server set to: " + ApiClient.baseUrl, Toast.LENGTH_SHORT).show()
					codeStatus.text = ("Server: " + ApiClient.baseUrl).take(80)
				}
				.setNegativeButton("Cancel", null)
				.show()
			true
		}
		// Show current server briefly
		codeStatus.text = ("Server: " + ApiClient.baseUrl).take(80)

	val prefs = getSharedPreferences("phtv", MODE_PRIVATE)

	var verifiedCode: String? = null

		fun maybeFastStart(): Boolean {
			val c = prefs.getString("pairCode", null)
			val st = intent?.getStringExtra("storeId")?.trim().orEmpty()
			val sc = intent?.getStringExtra("screenId")?.trim().orEmpty()
			if (!c.isNullOrBlank() && st.isNotBlank() && sc.isNotBlank()) {
				val i = Intent(this@SetupActivity, TvDisplayActivity::class.java)
				i.putExtra("storeId", st)
				i.putExtra("screenId", sc)
				i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
				startActivity(i)
				finish()
				return true
			}
			return false
		}

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
				} catch (e: HttpException) {
					val sc = e.code()
					codeStatus.text = when (sc) {
						400, 404 -> "Invalid or expired code. Regenerate from Profile, then try again."
						401, 403 -> "Code not authorized. Regenerate or sign in and retry."
						in 500..599 -> "Server error (${sc}). Try again later."
						else -> "HTTP ${sc}: ${e.message()}"
					}
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


		// Allow automation/test runner to inject a code via Intent extra
		intent?.getStringExtra("pairCode")?.let { injected ->
			val c = injected.trim()
			if (c.length == 4 && c.all { it.isDigit() }) {
				prefs.edit().putString("pairCode", c).apply()
				// If store/screen provided, jump straight to display; else go to StoreSelect
				if (!maybeFastStart()) {
					val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
					i.putExtra("pairCode", c)
					i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
					startActivity(i)
					finish()
				}
				return
			}
		}

		// If a code was previously linked, jump directly to store selection
		prefs.getString("pairCode", null)?.let { saved ->
			if (saved.length == 4 && saved.all { it.isDigit() }) {
				if (!maybeFastStart()) {
					val i = Intent(this@SetupActivity, StoreSelectActivity::class.java)
					i.putExtra("pairCode", saved)
					i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
					startActivity(i)
					finish()
				}
			}
		}
	}

	override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
		// Don’t auto-start; require explicit selection
		return super.onKeyDown(keyCode, event)
	}
}

