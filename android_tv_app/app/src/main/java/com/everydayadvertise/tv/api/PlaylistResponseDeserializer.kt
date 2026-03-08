package com.everydayadvertise.tv.api

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import java.lang.reflect.Type

/**
 * Custom deserializer for PlaylistResponse that handles complex nested data gracefully
 * and only parses the fields we need for Android TV playback.
 */
class PlaylistResponseDeserializer : JsonDeserializer<PlaylistResponse> {
	override fun deserialize(
		json: JsonElement,
		typeOfT: Type,
		context: JsonDeserializationContext
	): PlaylistResponse {
		val obj = json.asJsonObject
		
		// Extract success field
		val success = obj.get("success")?.asBoolean ?: false
		val rotation = obj.get("rotation")?.asInt ?: 0
		val orientation = obj.get("orientation")?.asString ?: "default"
		
		// Parse playlist array safely
		val playlist = mutableListOf<PlaylistItem>()
		val playlistArray = obj.get("playlist")
		android.util.Log.d("PlaylistDeserializer", "Parsing response: success=$success, has playlist=${playlistArray != null}, isArray=${playlistArray?.isJsonArray}")
		obj.get("playlist")?.takeIf { it.isJsonArray }?.asJsonArray?.forEach { itemElement ->
			try {
				val item = itemElement.asJsonObject
				
				// Extract required fields
				val id = item.get("id")?.asString
				val file = item.get("file")?.asString
				val url = item.get("url")?.asString
				val enabled = item.get("enabled")?.asBoolean ?: true
				val duration = item.get("duration")?.asInt ?: 10
				val repeat = item.get("repeat")?.asBoolean ?: true
				val linkNext = item.get("link_next")?.asBoolean ?: false
				val start = item.get("start")?.asString
				val end = item.get("end")?.asString
				val mediaType = item.get("media_type")?.asString
				
			// Parse schedule array if present (but don't fail if malformed)
			val schedule = try {
				item.get("schedule")?.takeIf { it.isJsonArray }?.asJsonArray?.mapNotNull { schedElement ->
					try {
						val sched = schedElement.asJsonObject
						ScheduleWindow(
							start = sched.get("start")?.asString,
							end = sched.get("end")?.asString,
							days = sched.get("days")?.asJsonArray?.mapNotNull { it.asString }
						)
					} catch (e: Exception) {
						null
					}
				}?.let { ArrayList(it) }
			} catch (e: Exception) {
				null
			}
			
			// Parse days array
			val days = try {
				item.get("days")?.asJsonArray?.mapNotNull { it.asString }?.let { ArrayList(it) }
			} catch (e: Exception) {
				null
			}				// Parse sync_ref if present (but ignore if malformed)
				val syncRef = try {
					item.get("sync_ref")?.takeIf { !it.isJsonNull }?.asJsonObject?.let { syncObj ->
						SyncRef(
							group = syncObj.get("group")?.asString,
							role = syncObj.get("role")?.asString,
							order = syncObj.get("order")?.asInt,
							startEpoch = syncObj.get("start_epoch")?.asLong ?: syncObj.get("startEpoch")?.asLong,
							count = syncObj.get("count")?.asInt,
							mode = syncObj.get("mode")?.asString,
							precisionMode = syncObj.get("precision_mode")?.asString,
							preloadBuffer = syncObj.get("preload_buffer")?.asInt,
							syncTolerance = syncObj.get("sync_tolerance")?.asInt
						)
					}
				} catch (e: Exception) {
					android.util.Log.e("PlaylistDeserializer", "Failed to parse sync_ref", e)
					null
				}
				
				playlist.add(
					PlaylistItem(
						id = id,
						file = file,
						url = url,
						enabled = enabled,
						duration = duration,
						repeat = repeat,
						linkNext = linkNext,
						start = start,
						end = end,
						schedule = schedule,
						days = days,
						mediaType = mediaType,
						syncRef = syncRef
					)
				)
			} catch (e: Exception) {
				android.util.Log.e("PlaylistDeserializer", "Failed to parse playlist item", e)
			}
		}
		
		return PlaylistResponse(
			success = success,
			playlist = if (playlist.isNotEmpty()) ArrayList(playlist) else null,
			rotation = rotation,
			orientation = orientation
		)
	}
}
