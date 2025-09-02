package com.pizzahut.tv.api

import android.content.Context

/**
 * Minimal holder for the TV pairing code so the API client can attach it as an HTTP header.
 * Initialize once early (Setup/StoreSelect/TvDisplay) with appContext.
 */
object PairCodeHolder {
    @Volatile private var appContext: Context? = null
    fun init(ctx: Context) { appContext = ctx.applicationContext }
    fun get(): String? {
        val ctx = appContext ?: return null
        return try { ctx.getSharedPreferences("phtv", Context.MODE_PRIVATE).getString("pairCode", null) } catch (_: Exception) { null }
    }
}
