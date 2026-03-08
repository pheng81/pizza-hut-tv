package com.everydayadvertise.tv

import android.content.Intent
import android.os.Bundle
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import android.view.Gravity
import androidx.core.view.setPadding
import androidx.lifecycle.lifecycleScope
import com.everydayadvertise.tv.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ChangeScreenActivity : AppCompatActivity() {
	override fun onCreate(savedInstanceState: Bundle?) {
		super.onCreate(savedInstanceState)
		setContentView(R.layout.activity_change_screen)

		val prefs = getSharedPreferences("phtv", MODE_PRIVATE)
		val storeInput = findViewById<EditText>(R.id.editTextStoreId)
		val fetchBtn = findViewById<Button>(R.id.buttonFetchScreens)
		val status = findViewById<TextView>(R.id.statusText)
		val container = findViewById<LinearLayout>(R.id.screensContainer)

		// Prefill last used store
		storeInput.setText(prefs.getString("storeId", ""))

		fun pick(storeId: String, screenId: String) {
			prefs.edit().putString("storeId", storeId).putString("screenId", screenId).apply()
			startActivity(Intent(this, TvDisplayActivity::class.java).apply {
				putExtra("storeId", storeId); putExtra("screenId", screenId)
				addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
			})
			finish()
		}

		fun fetchScreens() {
			val storeId = storeInput.text?.toString()?.trim().orEmpty()
			if (storeId.isEmpty()) { status.text = "Enter your store number"; return }
			status.text = "Loading screens..."; container.removeAllViews()
			lifecycleScope.launch {
				try {
					val resp = withContext(Dispatchers.IO) { ApiClient.service.getScreens(storeId) }
					if (resp.screens.isEmpty()) { status.text = "No screens for $storeId"; return@launch }
					status.text = "Tap a screen to switch"
					val targetPx = (600 * resources.displayMetrics.density).toInt()
					resp.screens.forEach { s ->
						val screenLabel = s.id.removePrefix("${storeId}_")
						val b = Button(this@ChangeScreenActivity).apply {
							text = screenLabel; textSize = 22f; isAllCaps = false; setPadding(24)
							setTextColor(0xFFE6EDF3.toInt())
							
							// Disable background tint
							backgroundTintList = null
							
							// Set initial background
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
							
							setOnClickListener { pick(storeId, s.id) }
						}
						val lp = LinearLayout.LayoutParams(targetPx, LinearLayout.LayoutParams.WRAP_CONTENT).apply { topMargin = 16; gravity = Gravity.CENTER_HORIZONTAL }
						container.addView(b, lp)
					}
				} catch (e: Exception) {
					status.text = ("Network error: ${e.message}").take(80)
				}
			}
		}

		// Add focus color change to fetch button
		fetchBtn.backgroundTintList = null
		fetchBtn.setOnFocusChangeListener { view, hasFocus ->
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
		fetchBtn.post {
			fetchBtn.backgroundTintList = null
			val initialBg = android.graphics.drawable.GradientDrawable()
			initialBg.setColor(0xFF37474F.toInt())
			initialBg.cornerRadius = 14f * resources.displayMetrics.density
			fetchBtn.background = initialBg
		}

		fetchBtn.setOnClickListener { fetchScreens() }
		storeInput.setOnEditorActionListener { _, actionId, _ ->
			if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) { fetchScreens(); true } else false
		}
	}
}

