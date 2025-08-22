package com.pizzahut.tv.api

import retrofit2.http.GET
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
}

