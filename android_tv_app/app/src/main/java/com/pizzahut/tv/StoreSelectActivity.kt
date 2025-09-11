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
    // Ensure ApiClient uses any saved server override
    ApiClient.initFromPrefs(applicationContext)

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
            val pairCodeSaved = prefs.getString("pairCode", null)
            if (pairCodeSaved.isNullOrBlank()) { status.text = "Link TV code first. Press Change Code."; return }
            status.text = "Loading screens..."
            container.removeAllViews()
            lifecycleScope.launch {
                try {
                    // Prefer code-scoped API: /api/stores_by_code/{code}
                    // First, fetch raw to check for HTML/login or errors without crashing JSON parsing
                    val raw = withContext(Dispatchers.IO) { ApiClient.service.getStoresByCodeRaw(pairCodeSaved) }
                    if (raw.trim().startsWith("<") && raw.contains("</html>", true)) {
                        status.text = "Login page received. Code invalid/expired. Tap Change Code to re-link."
                        return@launch
                    }
                    val resp = withContext(Dispatchers.IO) { ApiClient.service.getStoresByCode(pairCodeSaved) }
                    if (!resp.success) { status.text = resp.error ?: "Invalid TV code"; return@launch }
                    val screensJson = resp.screens
                    val storeScreens = try { screensJson?.get(storeId)?.asJsonObject } catch (_: Exception) { null }
                    val ids: List<String> = try { storeScreens?.entrySet()?.map { it.key } } catch (_: Exception) { null } ?: emptyList()
                    if (ids.isEmpty()) { status.text = "No screens found for store $storeId"; return@launch }
                    status.text = "Select a screen"
                    prefs.edit().putString("storeId", storeId).apply()
                    val targetPx = (600 * resources.displayMetrics.density).toInt()
                    ids.sorted().forEach { sid ->
                        val screenLabel = sid.removePrefix("${storeId}_")
                        val b = Button(this@StoreSelectActivity).apply {
                            text = screenLabel
                            textSize = 22f
                            isAllCaps = false
                            setPadding(24)
                            setOnClickListener {
                                val chosen = sid.trim()
                                if (chosen.isEmpty()) { Toast.makeText(this@StoreSelectActivity, "Invalid screen id", Toast.LENGTH_SHORT).show(); return@setOnClickListener }
                                prefs.edit().putString("screenId", chosen).apply()
                                val i = Intent(this@StoreSelectActivity, TvDisplayActivity::class.java)
                                i.putExtra("storeId", storeId)
                                i.putExtra("screenId", chosen)
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
                        msg.contains("403") || msg.contains("forbidden") -> "Code invalid or expired. Tap Change Code to re-link."
                        msg.contains("404") && msg.contains("store") -> "Store $storeId not found for this account."
                        msg.contains("malformedjson") || msg.contains("jsonreader") -> "Unexpected response. Try Change Code to re-link."
                        else -> ("Network error: ${e.javaClass.simpleName}: ${e.message}").take(160)
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
