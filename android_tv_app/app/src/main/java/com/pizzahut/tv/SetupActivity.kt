package com.pizzahut.tv

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.view.KeyEvent
import android.view.Gravity
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.setPadding
import androidx.lifecycle.lifecycleScope
import com.pizzahut.tv.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SetupActivity : AppCompatActivity() {
	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		setContentView(R.layout.activity_setup)

		val storeInput = findViewById<EditText>(R.id.editTextStoreId)
		val fetchBtn = findViewById<Button>(R.id.buttonFetchScreens)
		val status = findViewById<TextView>(R.id.statusText)
		val container = findViewById<LinearLayout>(R.id.screensContainer)

	val prefs = getSharedPreferences("phtv", MODE_PRIVATE)

		fun fetchScreens() {
			val storeId = storeInput.text?.toString()?.trim().orEmpty()
			if (storeId.isEmpty()) {
				status.text = "Enter your store number"
				storeInput.requestFocus(); return
			}
			status.text = "Loading screens..."
			container.removeAllViews()
			lifecycleScope.launch {
				try {
					val resp = withContext(Dispatchers.IO) { ApiClient.service.getScreens(storeId) }
					val screens = resp.screens
					if (screens.isEmpty()) {
						status.text = "No screens found for store $storeId"
						return@launch
					}
					status.text = "Select a screen"
					prefs.edit().putString("storeId", storeId).apply()
					// Create easy large buttons
					val targetPx = (600 * resources.displayMetrics.density).toInt()
					screens.forEach { s ->
						val screenLabel = s.id.removePrefix("${storeId}_")
						val b = Button(this@SetupActivity).apply {
							text = screenLabel
							textSize = 22f
							isAllCaps = false
							setPadding(24)
							setOnClickListener {
								// Save chosen screenId as plain id (e.g., screen1)
								prefs.edit().putString("screenId", s.id).apply()
								val i = Intent(this@SetupActivity, TvDisplayActivity::class.java)
								i.putExtra("storeId", storeId)
								i.putExtra("screenId", s.id)
								i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
								startActivity(i)
								finish()
							}
						}
						val lp = LinearLayout.LayoutParams(
							targetPx,
							LinearLayout.LayoutParams.WRAP_CONTENT
						).apply { topMargin = 16; gravity = Gravity.CENTER_HORIZONTAL }
						container.addView(b, lp)
					}
				} catch (e: Exception) {
					status.text = ("Network error: ${e.message}").take(80)
				}
			}
		}

		fetchBtn.setOnClickListener { fetchScreens() }
		storeInput.setOnEditorActionListener { _, actionId, _ ->
			if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) {
				fetchScreens(); true
			} else false
		}
	}

	override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
		// Don’t auto-start; require explicit selection
		return super.onKeyDown(keyCode, event)
	}
}

