package com.everydayadvertise.tv.api

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import java.lang.reflect.Type

/**
 * Custom deserializer for CodeStoresResponse that only parses the fields we need
 * and ignores the massive nested "screens" object that causes parsing issues on old Android versions.
 */
class CodeStoresDeserializer : JsonDeserializer<CodeStoresResponse> {
	override fun deserialize(
		json: JsonElement,
		typeOfT: Type,
		context: JsonDeserializationContext
	): CodeStoresResponse {
		val obj = json.asJsonObject
		
		// Extract only the fields we need, ignore everything else
		val success = obj.get("success")?.asBoolean ?: false
		val error = obj.get("error")?.takeIf { !it.isJsonNull }?.asString
		
		// Parse user object if present
		val user = obj.get("user")?.takeIf { !it.isJsonNull }?.asJsonObject?.let {
			CodeUser(username = it.get("username")?.asString)
		}
		
		fun asSafeString(el: JsonElement?): String? {
			if (el == null || el.isJsonNull) return null
			return try { el.asString } catch (_: Exception) { el.toString().trim('"') }
		}

		fun asSafeBoolean(el: JsonElement?): Boolean? {
			if (el == null || el.isJsonNull) return null
			return try { el.asBoolean } catch (_: Exception) {
				asSafeString(el)?.lowercase()?.let {
					when (it) {
						"1", "true", "yes", "y" -> true
						"0", "false", "no", "n" -> false
						else -> null
					}
				}
			}
		}

		// Parse stores from either array or object map
		val stores = mutableListOf<StoreInfo>()
		val storesNode = obj.get("stores")
		when {
			storesNode == null || storesNode.isJsonNull -> Unit
			storesNode.isJsonArray -> {
				storesNode.asJsonArray.forEach { storeElement ->
					try {
						val store = storeElement.asJsonObject
						val id = asSafeString(store.get("id")) ?: return@forEach
						val name = asSafeString(store.get("name"))
						val isMaster = asSafeBoolean(store.get("is_master"))
						stores.add(StoreInfo(id = id, name = name, isMaster = isMaster))
					} catch (_: Exception) {
						// Skip malformed store entries
					}
				}
			}
			storesNode.isJsonObject -> {
				storesNode.asJsonObject.entrySet().forEach { (key, value) ->
					try {
						val store = value.asJsonObject
						val id = asSafeString(store.get("id")) ?: key
						val name = asSafeString(store.get("name"))
						val isMaster = asSafeBoolean(store.get("is_master"))
						stores.add(StoreInfo(id = id, name = name, isMaster = isMaster))
					} catch (_: Exception) {
						// Skip malformed object-map entries
					}
				}
			}
		}
		
		// Completely ignore the "screens" field - don't even try to parse it
		return CodeStoresResponse(
			success = success,
			user = user,
			stores = stores,
			error = error
		)
	}
}
