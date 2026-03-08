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
		
		// Parse stores array
		val stores = mutableListOf<StoreInfo>()
		obj.get("stores")?.asJsonArray?.forEach { storeElement ->
			try {
				val store = storeElement.asJsonObject
				val id = store.get("id")?.asString ?: return@forEach
				val name = store.get("name")?.asString
				val isMaster = store.get("is_master")?.asBoolean
				stores.add(StoreInfo(id = id, name = name, isMaster = isMaster))
			} catch (e: Exception) {
				// Skip malformed store entries
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
