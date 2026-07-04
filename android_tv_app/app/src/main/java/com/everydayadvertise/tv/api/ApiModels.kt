package com.everydayadvertise.tv.api

import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName

data class PlaylistResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("playlist") val playlist: ArrayList<PlaylistItem>?,
	@SerializedName("rotation") val rotation: Int? = 0,
	@SerializedName("orientation") val orientation: String? = "default"
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
	@SerializedName("schedule") val schedule: ArrayList<ScheduleWindow>? = null,
	@SerializedName("days") val days: ArrayList<String>? = null,
	@SerializedName("media_type") val mediaType: String? = null,
	@SerializedName("live_pos_title") val livePosTitle: String? = null,
	@SerializedName("live_pos_body") val livePosBody: String? = null,
	@SerializedName("effect") val effect: String? = null,
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
	@SerializedName("stores") val stores: List<StoreInfo> = emptyList(),
	@SerializedName("error") val error: String? = null
	// Note: API also returns "devices" and "user" objects, but we ignore them
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
	@SerializedName("id") val id: String,
	@SerializedName("rotation") val rotation: Int? = 0,
	@SerializedName("orientation") val orientation: String? = "default"
)

// Heartbeat
data class HeartbeatReq(
	@SerializedName("store_id") val storeId: String,
	@SerializedName("screen_id") val screenId: String,
	@SerializedName("device_id") val deviceId: String? = null
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

// Sync metadata embedded per item when part of an auto-sync group
data class SyncRef(
	@SerializedName("group") val group: String? = null,
	@SerializedName("role") val role: String? = null, // "master" or "follower" (legacy)
	@SerializedName("order") val order: Int? = null,
	@SerializedName(value = "start_epoch", alternate = ["startEpoch"]) val startEpoch: Long? = null,
	@SerializedName("count") val count: Int? = null,
	@SerializedName("mode") val mode: String? = null,
	@SerializedName("precision_mode") val precisionMode: String? = null,
	@SerializedName("preload_buffer") val preloadBuffer: Int? = null,
	@SerializedName("sync_tolerance") val syncTolerance: Int? = null
)

// Server time sync endpoint response
data class SyncTimeResp(
	@SerializedName("timestamp") val timestamp: Long,
	@SerializedName("current_time") val currentTime: Long? = null,
	@SerializedName("sync_interval") val syncInterval: Int,
	@SerializedName("delay_ms") val delayMs: Long
)

// Pairing (stores by code)
data class CodeStoresResponse(
	@SerializedName("success") val success: Boolean,
	@SerializedName("user") val user: CodeUser? = null,
	@SerializedName("stores") val stores: List<StoreInfo> = emptyList(),
	@SerializedName("error") val error: String? = null
	// Note: API also returns "screens" object with nested screen data, but we ignore it for pairing
	// Gson will automatically ignore unknown fields, so no need to declare it
)

data class CodeUser(
	@SerializedName("username") val username: String?
)

