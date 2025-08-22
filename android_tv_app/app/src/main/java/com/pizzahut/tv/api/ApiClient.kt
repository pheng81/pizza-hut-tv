package com.pizzahut.tv.api

import com.pizzahut.tv.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
	private fun normalized(base: String): String = if (base.endsWith("/")) base else "$base/"

	val baseUrl: String by lazy { normalized(BuildConfig.PHTV_BASE_URL) }

	private val okHttp: OkHttpClient by lazy {
		val log = HttpLoggingInterceptor().apply {
			level = HttpLoggingInterceptor.Level.BASIC
		}
		OkHttpClient.Builder()
			.connectTimeout(5, TimeUnit.SECONDS)
			.readTimeout(8, TimeUnit.SECONDS)
			.writeTimeout(8, TimeUnit.SECONDS)
			.addInterceptor(log)
			.build()
	}

	private val retrofit: Retrofit by lazy {
		Retrofit.Builder()
			.baseUrl(baseUrl)
			.client(okHttp)
			.addConverterFactory(GsonConverterFactory.create())
			.build()
	}

	val service: ApiService by lazy { retrofit.create(ApiService::class.java) }
}

