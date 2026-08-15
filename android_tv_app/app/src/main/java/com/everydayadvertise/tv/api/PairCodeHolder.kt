package com.everydayadvertise.tv.api

import android.content.Context

/**
 * Minimal holder for the TV pairing code so the API client can attach it as an HTTP header.
 * Initialize once early (Setup/StoreSelect/TvDisplay) with appContext.
 */
object PairCodeHolder {
    const val PREFS_NAME = "com.everydayadvertise.tv.PREFERENCES"
    const val KEY_PAIR_CODE = "pairCode"
    const val KEY_TV_PAIR_CODE = "tvPairCode"

    @Volatile private var appContext: Context? = null

    fun init(ctx: Context) { appContext = ctx.applicationContext }

    /**
     * Six-digit code the dashboard uses to push link/store codes to this TV.
     * The server keys `webplayer_tv_pair_codes` on it, so it has to travel with
     * every join_session. Persisted so the number on screen stays the same
     * across restarts instead of changing under the user mid-pairing.
     */
    fun getOrCreateTvPairCode(ctx: Context? = null): String {
        val c = ctx?.applicationContext ?: appContext ?: return ""
        return try {
            val prefs = c.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val existing = prefs.getString(KEY_TV_PAIR_CODE, null)
            if (existing != null && existing.length == 6 && existing.all { it.isDigit() }) {
                existing
            } else {
                val generated = (100000..999999).random().toString()
                prefs.edit().putString(KEY_TV_PAIR_CODE, generated).apply()
                generated
            }
        } catch (_: Exception) {
            ""
        }
    }

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
