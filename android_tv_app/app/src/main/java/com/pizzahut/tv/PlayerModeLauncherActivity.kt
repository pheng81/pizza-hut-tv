package com.pizzahut.tv

import android.content.Context
import android.content.Intent
import android.util.Log
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

/**
 * Launcher that allows selecting among different playback implementations:
 * - ExoPlayer (stable)
 * - WebView (HTML panorama renderer)
 * - Custom Codec (experimental low-level decoder)
 * Remembers last chosen mode and auto-launches it after a short delay unless user cancels.
 */

data class PlayerMode(val title: String, val subtitle: String, val launcher: () -> Unit)

class PlayerModeLauncherActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private var autoLaunchCancelled = false
    private val autoLaunchDelayMs = 5000L
    private lateinit var autoHint: TextView

    private val prefs by lazy { getSharedPreferences("phtv_prefs", Context.MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
    Log.d("LauncherModes", "onCreate start")
    setContentView(R.layout.activity_player_mode_launcher)
        val recycler = findViewById<RecyclerView>(R.id.modeRecycler)
        autoHint = findViewById(R.id.autoLaunchHint)
    autoHint.text = "Loading modes..."
    Log.d("LauncherModes", "Views bound recycler=${recycler != null}")

        val storeId = intent.getStringExtra("storeId") ?: "0000"
        val screenId = intent.getStringExtra("screenId") ?: "screen1"

        val modes = listOf(
            PlayerMode("Native ExoPlayer", "Stable playback via ExoPlayer") {
                startActivity(Intent(this, TvDisplayActivity::class.java).apply { putExtra("storeId", storeId); putExtra("screenId", screenId) })
                rememberAndFinish("exo")
            },
            PlayerMode("WebView Player", "Embedded web panorama renderer") {
                startActivity(Intent(this, WebPlayerActivity::class.java).apply { putExtra("storeId", storeId); putExtra("screenId", screenId) })
                rememberAndFinish("web")
            },
            PlayerMode("Custom Codec", "Experimental low-level decoder & sync") {
                startActivity(Intent(this, CustomCodecPlayerActivity::class.java).apply { putExtra("storeId", storeId); putExtra("screenId", screenId) })
                rememberAndFinish("custom")
            }
        )
        Log.d("LauncherModes", "Modes size=${modes.size}")

        recycler.layoutManager = LinearLayoutManager(this, RecyclerView.HORIZONTAL, false)
        recycler.adapter = ModeAdapter(modes)
        recycler.setHasFixedSize(true)

        // Focus first item for dpad navigation
        recycler.post {
            Log.d("LauncherModes", "Recycler child count=${recycler.childCount}")
            recycler.getChildAt(0)?.let { Log.d("LauncherModes", "Requesting focus on first child") }
            recycler.getChildAt(0)?.requestFocus()
        }

        scheduleAutoLaunch(modes)
        Log.d("LauncherModes", "onCreate end")
    }

    private fun scheduleAutoLaunch(modes: List<PlayerMode>) {
        val last = prefs.getString("last_mode", null)
        if (last == null) return
        autoHint.visibility = View.VISIBLE
        Log.d("LauncherModes", "Scheduling auto launch last=$last in ${autoLaunchDelayMs}ms")
        autoHint.text = "Auto starting last mode ($last) in ${autoLaunchDelayMs/1000}s... Press any key to cancel"
        handler.postDelayed({
            if (autoLaunchCancelled) return@postDelayed
            when (last) {
                "exo" -> modes[0].launcher.invoke()
                "web" -> modes[1].launcher.invoke()
                "custom" -> modes[2].launcher.invoke()
            }
        }, autoLaunchDelayMs)
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (!autoLaunchCancelled) {
            autoLaunchCancelled = true
            autoHint.text = "Auto start cancelled"
            Log.d("LauncherModes", "Auto start cancelled by key=$keyCode")
        }
        return super.onKeyDown(keyCode, event)
    }

    private fun rememberAndFinish(mode: String) {
        prefs.edit().putString("last_mode", mode).apply()
        finish()
    }
}

class ModeAdapter(private val items: List<PlayerMode>) : RecyclerView.Adapter<ModeVH>() {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ModeVH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_player_mode, parent, false)
        return ModeVH(v)
    }
    override fun getItemCount(): Int = items.size
    override fun onBindViewHolder(holder: ModeVH, position: Int) = holder.bind(items[position])
}

class ModeVH(itemView: View) : RecyclerView.ViewHolder(itemView) {
    private val title = itemView.findViewById<TextView>(R.id.title)
    private val subtitle = itemView.findViewById<TextView>(R.id.subtitle)
    fun bind(mode: PlayerMode) {
        title.text = mode.title
        subtitle.text = mode.subtitle
        itemView.isFocusable = true
        itemView.isFocusableInTouchMode = true
        itemView.setOnClickListener { mode.launcher.invoke() }
        itemView.setOnFocusChangeListener { v, hasFocus ->
            v.scaleX = if (hasFocus) 1.07f else 1.0f
            v.scaleY = if (hasFocus) 1.07f else 1.0f
            v.elevation = if (hasFocus) 12f else 0f
        }
    }
}
