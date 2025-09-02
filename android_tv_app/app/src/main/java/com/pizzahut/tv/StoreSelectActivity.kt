package com.pizzahut.tv

import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.inputmethod.EditorInfo
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.setPadding
import androidx.lifecycle.lifecycleScope
import com.pizzahut.tv.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class StoreSelectActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_store_select)
    com.pizzahut.tv.api.PairCodeHolder.init(applicationContext)

        val storeInput = findViewById<EditText>(R.id.editTextStoreId)
        val fetchBtn = findViewById<Button>(R.id.buttonFetchScreens)
    val changeCodeBtn = findViewById<Button>(R.id.buttonChangeCode)
        val status = findViewById<TextView>(R.id.statusText)
        val container = findViewById<LinearLayout>(R.id.screensContainer)

        val pairCode = intent.getStringExtra("pairCode")
        val prefs = getSharedPreferences("phtv", MODE_PRIVATE)
        if (!pairCode.isNullOrBlank()) {
            prefs.edit().putString("pairCode", pairCode).apply()
        }

        changeCodeBtn.setOnClickListener {
            prefs.edit().remove("pairCode").apply()
            val i = Intent(this@StoreSelectActivity, SetupActivity::class.java)
            i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(i)
            finish()
        }

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
                    val targetPx = (600 * resources.displayMetrics.density).toInt()
                    screens.forEach { s ->
                        val screenLabel = s.id.removePrefix("${storeId}_")
                        val b = Button(this@StoreSelectActivity).apply {
                            text = screenLabel
                            textSize = 22f
                            isAllCaps = false
                            setPadding(24)
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

        fetchBtn.setOnClickListener { fetchScreens() }
        storeInput.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_DONE || actionId == EditorInfo.IME_ACTION_GO) { fetchScreens(); true } else false
        }
    }
}
