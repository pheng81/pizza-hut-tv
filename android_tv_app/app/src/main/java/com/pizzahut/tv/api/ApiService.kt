package com.pizzahut.tv.api

import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {
	@GET("playlist/{storeId}/{screenId}")
	suspend fun getPlaylist(
		@Path("storeId") storeId: String,
		@Path("screenId") screenId: String
	): PlaylistResponse

	@GET("stores")
	suspend fun getStores(): StoresResponse

	@GET("screens/{storeId}")
	suspend fun getScreens(
		@Path("storeId") storeId: String
	): ScreensResponse

	// Pairing: fetch stores for a user by 4-digit code
	@GET("api/stores_by_code/{code}")
	suspend fun getStoresByCode(
		@Path("code") code: String
	): CodeStoresResponse

	// Raw variant to detect HTML/login when server returns non-JSON
	@GET("api/stores_by_code/{code}")
	suspend fun getStoresByCodeRaw(
		@Path("code") code: String,
		@Header("Accept") accept: String = "text/plain, application/json"
	): String

	@POST("api/screen_heartbeat")
	suspend fun sendHeartbeat(@Body body: HeartbeatReq): HeartbeatResp

	// Client events: TV reports per-item load success/failure so dashboard can show status
	@POST("api/client_event")
	suspend fun postClientEvent(@Body body: ClientEventReq): BasicResp
}

