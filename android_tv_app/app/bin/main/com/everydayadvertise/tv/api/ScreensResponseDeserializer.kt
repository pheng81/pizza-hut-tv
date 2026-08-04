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
		
		fun asSafeString(el: JsonElement?): String? {
			if (el == null || el.isJsonNull) return null
			return try { el.asString } catch (_: Exception) { el.toString().trim('"') }
		}

		fun asSafeInt(el: JsonElement?, fallback: Int = 0): Int {
			if (el == null || el.isJsonNull) return fallback
			return try { el.asInt } catch (_: Exception) {
				asSafeString(el)?.toIntOrNull() ?: fallback
			}
		}

		// Parse screens from either array or object map
		val screens = mutableListOf<ScreenInfo>()
		val screensNode = obj.get("screens")
		when {
			screensNode == null || screensNode.isJsonNull -> Unit
			screensNode.isJsonArray -> {
				screensNode.asJsonArray.forEach { screenElement ->
					try {
						val screen = screenElement.asJsonObject
						val id = asSafeString(screen.get("id")) ?: return@forEach
						val rotation = asSafeInt(screen.get("rotation"), 0)
						val orientation = asSafeString(screen.get("orientation")) ?: "default"
						screens.add(ScreenInfo(id = id, rotation = rotation, orientation = orientation))
					} catch (_: Exception) {
						// Skip malformed screen entries
					}
				}
			}
			screensNode.isJsonObject -> {
				screensNode.asJsonObject.entrySet().forEach { (key, value) ->
					try {
						val screen = value.asJsonObject
						val id = asSafeString(screen.get("id")) ?: key
						val rotation = asSafeInt(screen.get("rotation"), 0)
						val orientation = asSafeString(screen.get("orientation")) ?: "default"
						screens.add(ScreenInfo(id = id, rotation = rotation, orientation = orientation))
					} catch (_: Exception) {
						// Skip malformed object-map entries
					}
				}
			}
		}
		
		return ScreensResponse(success = success, screens = screens)
	}
}
