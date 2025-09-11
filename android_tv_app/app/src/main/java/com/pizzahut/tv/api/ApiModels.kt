package com.pizzahut.tv.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName

data class PlaylistResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("playlist") val playlist: List<PlaylistItem>?,
	// Optional screen metadata used by web player; allow TV to mirror orientation behavior
	@SerializedName("orientation") val orientation: String? = null,
	@SerializedName("rotation") val rotation: Int? = null
)

data class PlaylistItem(
	@SerializedName("id") val id: String?,
	@SerializedName("file") val file: String?,
	// Absolute, server-built URL to the file (preferred for images when available)
	@SerializedName("url") val url: String? = null,
	@SerializedName("enabled") val enabled: Boolean? = true,
	@SerializedName("duration") val duration: Int? = 10,
	@SerializedName("repeat") val repeat: Boolean? = true,
	@SerializedName("link_next") val linkNext: Boolean? = false,
	@SerializedName("start") val start: String? = null,
	@SerializedName("end") val end: String? = null,
	@SerializedName("schedule") val schedule: List<ScheduleWindow>? = emptyList(),
	@SerializedName("days") val days: List<String>? = emptyList(),
	@SerializedName("media_type") val mediaType: String? = null,
	// Optional synchronized group metadata for split/sliced video
	@SerializedName("sync_ref") val syncRef: SyncRef? = null
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

// Client events
data class ClientEventReq(
	@SerializedName("store_id") val storeId: String,
	@SerializedName("screen_id") val screenId: String,
	@SerializedName("event") val event: String, // e.g., "load_ok", "load_fail", "playlist_reload"
	@SerializedName("file") val file: String? = null,
	@SerializedName("item_id") val itemId: String? = null,
	@SerializedName("error") val error: String? = null
)

data class BasicResp(
	@SerializedName("success") val success: Boolean,
	@SerializedName("error") val error: String? = null
)

// Sync/slice info to render a segment of a larger video/image
data class SyncRef(
	@SerializedName("group") val group: String? = null,
	@SerializedName("role") val role: String? = null,
	@SerializedName("order") val order: Int? = null,
	@SerializedName("count") val count: Int? = null,
	@SerializedName("mode") val mode: String? = null,
	@SerializedName("start_epoch") val startEpoch: Long? = null,
	@SerializedName("virtual") val virtual: Boolean? = null
)

// Pairing (stores by code)
data class CodeStoresResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("user") val user: CodeUser? = null,
	@SerializedName("stores") val stores: List<StoreInfo> = emptyList(),
	// Server returns an object map of storeId -> { screenId: { ... } }
	// Use JsonObject to avoid strict shape expectations.
	@SerializedName("screens") val screens: JsonObject? = null,
	@SerializedName("error") val error: String? = null
)

data class CodeUser(
	@SerializedName("username") val username: String?
)

