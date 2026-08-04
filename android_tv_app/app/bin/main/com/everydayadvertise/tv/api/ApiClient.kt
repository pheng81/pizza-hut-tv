package com.everydayadvertise.tv.api

import com.everydayadvertise.tv.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.converter.scalars.ScalarsConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
	private fun normalized(base: String): String = if (base.endsWith("/")) base else "$base/"

	val baseUrl: String by lazy { normalized(BuildConfig.PHTV_BASE_URL) }

	private val okHttp: OkHttpClient by lazy {
		val log = HttpLoggingInterceptor().apply {
			level = HttpLoggingInterceptor.Level.BODY
		}
		val builder = OkHttpClient.Builder()
			.connectTimeout(10, TimeUnit.SECONDS)
			.readTimeout(15, TimeUnit.SECONDS)
			.writeTimeout(15, TimeUnit.SECONDS)
		
		// Only allow the insecure TLS workaround when explicitly enabled per build.
		if (BuildConfig.PHTV_ALLOW_INSECURE_SSL) {
			try {
				builder.sslSocketFactory(
					TrustAllCerts.getUnsafeSSLSocketFactory(),
					TrustAllCerts.getTrustManager()
				)
				builder.hostnameVerifier(TrustAllCerts.getAllTrustingHostnameVerifier())
			} catch (e: Exception) {
				// Fall back to default SSL if workaround fails
			}
		}
		
		builder
			// Attach pairing code when available so server can scope to user config
			.addInterceptor { chain ->
				val orig = chain.request()
				val b = orig.newBuilder()
				try {
					val code = PairCodeHolder.get()
					if (!code.isNullOrBlank()) {
						b.addHeader("X-User-Code", code)
					}
					// Attach stable device identifier for observability and sync grouping
					// Pull device id through PairCodeHolder accessor (which has appContext)
					try {
						PairCodeHolder.getDeviceId()?.let { b.addHeader("X-Device-Id", it) }
					} catch (_: Exception) {}
				} catch (_: Exception) {}
				chain.proceed(b.build())
			}
			.addInterceptor(log)
			.build()
	}

	private val retrofit: Retrofit by lazy {
		// Configure Gson with custom deserializers for API responses
		// This avoids parsing issues and ClassCastException on old Android versions
		val gson = com.google.gson.GsonBuilder()
			.setLenient()
			.registerTypeAdapter(CodeStoresResponse::class.java, CodeStoresDeserializer())
			.registerTypeAdapter(ScreensResponse::class.java, ScreensResponseDeserializer())
			// Playlist uses default Gson since we fixed the model (no emptyList defaults)
			.create()
		
		Retrofit.Builder()
			.baseUrl(baseUrl)
			.client(okHttp)
			.addConverterFactory(ScalarsConverterFactory.create())
			.addConverterFactory(GsonConverterFactory.create(gson))
			.build()
	}

	val service: ApiService by lazy { retrofit.create(ApiService::class.java) }
}

