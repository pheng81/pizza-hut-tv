package com.everydayadvertise.tv.api

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {
	@GET("playlist/{storeId}/{screenId}")
	suspend fun getPlaylist(
		@Path("storeId") storeId: String,
		@Path("screenId") screenId: String,
		@Query("skip_schedule_filter") skipScheduleFilter: Int = 1
	): String

	@GET("api/stores")
	suspend fun getStores(): StoresResponse

	@GET("api/screens/{storeId}")
	suspend fun getScreens(
		@Path("storeId") storeId: String
	): ScreensResponse

	// Precise server time alignment for synchronized playback
	@GET("api/sync-time")
	suspend fun getSyncTime(): SyncTimeResp

	// Pairing: fetch stores for a user by 4-digit code
	@GET("api/stores_by_code/{code}")
	suspend fun getStoresByCode(
		@Path("code") code: String
	): CodeStoresResponse

	@POST("api/screen_heartbeat")
	suspend fun sendHeartbeat(@Body body: HeartbeatReq): HeartbeatResp

	// Client events: TV reports per-item load success/failure so dashboard can show status
	@POST("api/client_event")
	suspend fun postClientEvent(@Body body: ClientEventReq): BasicResp
}

