package com.pizzahut.tv.api

import com.google.gson.annotations.SerializedName

data class PlaylistResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("playlist") val playlist: List<PlaylistItem>?
)

data class PlaylistItem(
	@SerializedName("id") val id: String?,
	@SerializedName("file") val file: String?,
	@SerializedName("enabled") val enabled: Boolean? = true,
	@SerializedName("duration") val duration: Int? = 10,
	@SerializedName("repeat") val repeat: Boolean? = true,
	@SerializedName("link_next") val linkNext: Boolean? = false,
	@SerializedName("start") val start: String? = null,
	@SerializedName("end") val end: String? = null,
	@SerializedName("schedule") val schedule: List<ScheduleWindow>? = emptyList(),
	@SerializedName("days") val days: List<String>? = emptyList(),
	@SerializedName("media_type") val mediaType: String? = null
)

data class ScheduleWindow(
	@SerializedName("start") val start: String?,
	@SerializedName("end") val end: String?,
	@SerializedName("days") val days: List<String>? = null
)

// Device setup discovery
data class StoresResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("stores") val stores: List<StoreInfo> = emptyList()
)

data class StoreInfo(
	@SerializedName("id") val id: String,
	@SerializedName("name") val name: String? = null,
	@SerializedName("is_master") val isMaster: Boolean? = null
)

data class ScreensResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("screens") val screens: List<ScreenInfo> = emptyList()
)

data class ScreenInfo(
	@SerializedName("id") val id: String
)

// Heartbeat
data class HeartbeatReq(
	@SerializedName("store_id") val storeId: String,
	@SerializedName("screen_id") val screenId: String
)

data class HeartbeatResp(
	@SerializedName("success") val success: Boolean,
	@SerializedName("error") val error: String? = null
)

