package com.everydayadvertise.tv.api

import android.content.Context

object DeviceIdHelper {
    private const val PREFS_NAME = "phtv"
    private const val KEY_DEVICE_ID = "device_id"
    @Volatile private var cached: String? = null

    fun init(ctx: Context) { get(ctx) }

    @Synchronized fun get(ctx: Context): String {
        cached?.let { return it }
        val prefs = ctx.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        var id = prefs.getString(KEY_DEVICE_ID, null)
        if (id.isNullOrBlank()) {
            // Generate user-friendly ID: androidtv-XXXX-XX (e.g., androidtv-a3f8-2c)
            val uuid = java.util.UUID.randomUUID().toString().replace("-", "")
            id = "androidtv-${uuid.substring(0, 4)}-${uuid.substring(4, 6)}"
            prefs.edit().putString(KEY_DEVICE_ID, id).apply()
        }
        cached = id!!
        return id
    }
}
