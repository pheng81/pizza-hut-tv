package com.everydayadvertise.tv.api

import android.content.Context

/**
 * Minimal holder for the TV pairing code so the API client can attach it as an HTTP header.
 * Initialize once early (Setup/StoreSelect/TvDisplay) with appContext.
 */
object PairCodeHolder {
    const val PREFS_NAME = "com.everydayadvertise.tv.PREFERENCES"
    const val KEY_PAIR_CODE = "pairCode"

    @Volatile private var appContext: Context? = null

    fun init(ctx: Context) { appContext = ctx.applicationContext }

    fun get(): String? {
        val ctx = appContext ?: return null
        return try {
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).getString(KEY_PAIR_CODE, null)
        } catch (_: Exception) {
            null
        }
    }

    fun getDeviceId(): String? {
        val ctx = appContext ?: return null
        return try { DeviceIdHelper.get(ctx) } catch (_: Exception) { null }
    }
}
