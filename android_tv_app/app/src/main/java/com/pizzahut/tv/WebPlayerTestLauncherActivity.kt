package com.pizzahut.tv

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log

/**
 * Small exported test harness (debug builds) to allow adb launching without exporting WebPlayerActivity.
 * Usage:
 * adb shell am start -n com.pizzahut.tv/.WebPlayerTestLauncherActivity --esa storeId 0000 --esa screenId screen1 --ez debug true
 */
class WebPlayerTestLauncherActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val storeId = intent.getStringExtra("storeId") ?: "0000"
        val screenId = intent.getStringExtra("screenId") ?: "screen1"
        val debug = intent.getBooleanExtra("debug", false)
        Log.d("WebPlayerHarness", "Forwarding to WebPlayerActivity store=$storeId screen=$screenId debug=$debug")
        startActivity(Intent(this, WebPlayerActivity::class.java).apply {
            putExtra("storeId", storeId)
            putExtra("screenId", screenId)
            putExtra("debug", debug)
        })
        finish()
    }
}
