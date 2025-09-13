package com.pizzahut.tv.api

import android.content.Context
import com.google.gson.GsonBuilder
import com.pizzahut.tv.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.converter.scalars.ScalarsConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
	private fun normalized(base: String): String = if (base.endsWith("/")) base else "$base/"

	// Persisted override (in SharedPreferences "phtv", key "baseUrlOverride").
	@Volatile private var currentBaseUrl: String = normalized(BuildConfig.PHTV_BASE_URL)
	private const val PREFS = "phtv"
	private const val KEY_BASE = "baseUrlOverride"

	// Property-style access for callers (matches existing uses ApiClient.baseUrl)
	val baseUrl: String get() = currentBaseUrl

	fun initFromPrefs(ctx: Context?) {
		if (ctx == null) return
		try {
			val p = ctx.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
			val o = p.getString(KEY_BASE, null)
			if (!o.isNullOrBlank()) setBaseUrlInternal(o)
		} catch (_: Exception) {}
	}

	private fun setBaseUrlInternal(url: String?) {
		val u = normalized((url ?: BuildConfig.PHTV_BASE_URL))
		synchronized(this) {
			if (u == currentBaseUrl) return
			currentBaseUrl = u
			// Rebuild Retrofit/service with new base
			retrofit = null
			serviceInst = null
		}
	}

	fun setBaseUrlOverride(ctx: Context?, url: String?) {
		setBaseUrlInternal(url)
		try { ctx?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)?.edit()?.putString(KEY_BASE, url)?.apply() } catch (_: Exception) {}
	}

	fun clearOverride(ctx: Context?) {
		try { ctx?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)?.edit()?.remove(KEY_BASE)?.apply() } catch (_: Exception) {}
		setBaseUrlInternal(BuildConfig.PHTV_BASE_URL)
	}

	private val okHttp: OkHttpClient by lazy {
		val log = HttpLoggingInterceptor().apply {
			level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY else HttpLoggingInterceptor.Level.BASIC
		}
		OkHttpClient.Builder()
			.connectTimeout(10, TimeUnit.SECONDS)
			.readTimeout(15, TimeUnit.SECONDS)
			.writeTimeout(15, TimeUnit.SECONDS)
			// Attach pairing code when available so server can scope to user config
			.addInterceptor { chain ->
				val orig = chain.request()
				val b = orig.newBuilder()
				try {
					val code = PairCodeHolder.get()
					if (!code.isNullOrBlank()) {
						b.addHeader("X-User-Code", code)
					}
				} catch (_: Exception) {}
				// Identify client as Android TV so backend can tailor playlist (e.g., slice URLs)
				if (orig.header("User-Agent").isNullOrBlank()) {
					b.header("User-Agent", "PHTV-Android/1.0 (Android TV)")
				}
				// Prefer JSON responses unless caller explicitly set Accept
				if (orig.header("Accept") == null) {
					b.header("Accept", "application/json")
				}
				chain.proceed(b.build())
			}
			.addInterceptor(log)
			.build()
	}

	@Volatile private var retrofit: Retrofit? = null
	@Volatile private var serviceInst: ApiService? = null

	private fun getOrBuildService(): ApiService {
		synchronized(this) {
			serviceInst?.let { return it }
			val gson = GsonBuilder().setLenient().create()
			val rt = Retrofit.Builder()
				.baseUrl(currentBaseUrl)
				.client(okHttp)
				.addConverterFactory(ScalarsConverterFactory.create())
				.addConverterFactory(GsonConverterFactory.create(gson))
				.build()
			retrofit = rt
			val svc = rt.create(ApiService::class.java)
			serviceInst = svc
			return svc
		}
	}

	val service: ApiService
		get() = getOrBuildService()
}

