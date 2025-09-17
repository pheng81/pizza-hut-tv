package com.pizzahut.tv

import android.content.Context

/** Stores persistent environment selection + last used environment. */
object EnvPreferences {
    private const val PREFS = "phtv_env"
    private const val KEY_MODE = "env_mode" // AUTO | LOCAL | PROD
    private const val KEY_LAST = "last_env" // local | prod

    enum class EnvMode { AUTO, LOCAL, PROD }

    private fun prefs(ctx: Context) = ctx.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun getMode(ctx: Context): EnvMode {
        val raw = prefs(ctx).getString(KEY_MODE, EnvMode.AUTO.name) ?: EnvMode.AUTO.name
        return try { EnvMode.valueOf(raw) } catch (_: Exception) { EnvMode.AUTO }
    }

    fun setMode(ctx: Context, mode: EnvMode) {
        prefs(ctx).edit().putString(KEY_MODE, mode.name).apply()
    }

    fun getLastWasLocal(ctx: Context): Boolean {
        return prefs(ctx).getString(KEY_LAST, null) == "local"
    }

    fun setLast(ctx: Context, local: Boolean) {
        prefs(ctx).edit().putString(KEY_LAST, if (local) "local" else "prod").apply()
    }
}
