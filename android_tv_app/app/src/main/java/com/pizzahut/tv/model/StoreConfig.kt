package com.pizzahut.tv.model

import com.google.gson.annotations.SerializedName

data class StoreConfig(
    @SerializedName("stores") val stores: List<Store>?,
    @SerializedName("screens") val screens: Map<String, Map<String, ScreenConfig>>?
)

data class Store(
    @SerializedName("id") val id: String?,
    @SerializedName("name") val name: String?
)

data class ScreenConfig(
    @SerializedName("file") val file: String?,
    @SerializedName("vertical") val vertical: Boolean = false,
    @SerializedName("horizontal") val horizontal: Boolean = false
)
