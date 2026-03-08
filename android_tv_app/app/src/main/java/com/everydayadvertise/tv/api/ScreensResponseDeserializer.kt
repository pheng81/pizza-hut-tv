package com.everydayadvertise.tv.api

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import java.lang.reflect.Type

/**
 * Custom deserializer for ScreensResponse that only parses the fields we need
 * and handles any unexpected data gracefully.
 */
class ScreensResponseDeserializer : JsonDeserializer<ScreensResponse> {
	override fun deserialize(
		json: JsonElement,
		typeOfT: Type,
		context: JsonDeserializationContext
	): ScreensResponse {
		val obj = json.asJsonObject
		
		// Extract only the fields we need
		val success = obj.get("success")?.asBoolean ?: false
		
		// Parse screens array
		val screens = mutableListOf<ScreenInfo>()
		obj.get("screens")?.asJsonArray?.forEach { screenElement ->
			try {
				val screen = screenElement.asJsonObject
				val id = screen.get("id")?.asString ?: return@forEach
				val rotation = screen.get("rotation")?.asInt ?: 0
				val orientation = screen.get("orientation")?.asString ?: "default"
				screens.add(ScreenInfo(id = id, rotation = rotation, orientation = orientation))
			} catch (e: Exception) {
				// Skip malformed screen entries
			}
		}
		
		return ScreensResponse(success = success, screens = screens)
	}
}
