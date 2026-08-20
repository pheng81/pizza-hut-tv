package com.everydayadvertise.tv.net

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.util.Log
import com.everydayadvertise.tv.api.DeviceIdHelper
import com.everydayadvertise.tv.api.PairCodeHolder

/**
 * Announces this TV on the local network over mDNS/Bonjour.
 *
 * Without this the phone's "Scan Wi-Fi" finds nothing. It looks for vendor
 * services - AirPlay, Chromecast, Samsung, LG, Roku - and this app provides
 * none of them, so an EverydayAdvertise TV was invisible on its own network no
 * matter what the phone did.
 *
 * Registration only. The TV does not discover anything, so no NEARBY_WIFI_DEVICES
 * permission is needed on Android 13+.
 *
 * The port is informational: remote commands travel phone -> server -> TV over
 * the existing socket, not directly to this port. NSD requires a non-zero port,
 * and the TXT records are the part that matters - they let the phone match a
 * discovered TV to a screen already registered to the account.
 */
object TvNsdAdvertiser {

    const val SERVICE_TYPE = "_everydayadvertise._tcp"

    private const val TAG = "TvNsdAdvertiser"

    /** Nominal. See the class comment - nothing listens here. */
    private const val ADVERTISED_PORT = 8009

    private var nsdManager: NsdManager? = null
    private var listener: NsdManager.RegistrationListener? = null

    @Volatile
    private var registeredAs: String? = null

    /**
     * Publish this TV, replacing any previous registration.
     *
     * Safe to call repeatedly - re-registering with the same details is a no-op,
     * which matters because the display activity can be recreated on rotation or
     * when the screen assignment changes.
     */
    @Synchronized
    fun start(ctx: Context, storeId: String, screenId: String) {
        val context = ctx.applicationContext
        val deviceId = try {
            DeviceIdHelper.get(context)
        } catch (_: Exception) {
            ""
        }
        val desired = "$storeId/$screenId/$deviceId"
        if (registeredAs == desired) {
            return
        }
        stop()

        val manager = try {
            context.getSystemService(Context.NSD_SERVICE) as? NsdManager
        } catch (e: Exception) {
            Log.w(TAG, "No NSD service available: ${e.message}")
            null
        } ?: return

        // Shown verbatim in the phone's TV list, so name it for a human picking
        // between several screens in the same shop, not for a developer.
        val displayName = buildString {
            append("EverydayAdvertise")
            if (storeId.isNotBlank()) append(" $storeId")
            if (screenId.isNotBlank()) append(" - $screenId")
        }

        val info = NsdServiceInfo().apply {
            serviceName = displayName
            serviceType = SERVICE_TYPE
            port = ADVERTISED_PORT
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                putAttribute(this, "device_id", deviceId)
                putAttribute(this, "store_id", storeId)
                putAttribute(this, "screen_id", screenId)
                putAttribute(this, "app", "everydayadvertise-tv")
                putAttribute(
                    this,
                    "pair_code",
                    try {
                        PairCodeHolder.getOrCreateTvPairCode(context)
                    } catch (_: Exception) {
                        ""
                    },
                )
            }
        }

        val registration = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(info: NsdServiceInfo) {
                // Android may rename on collision (two screens in one shop), so
                // log what it actually published rather than what we asked for.
                Log.i(TAG, "Advertising as '${info.serviceName}' ($SERVICE_TYPE)")
            }

            override fun onRegistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                Log.w(TAG, "Registration failed: $errorCode")
                registeredAs = null
            }

            override fun onServiceUnregistered(info: NsdServiceInfo) {
                Log.i(TAG, "Stopped advertising")
            }

            override fun onUnregistrationFailed(info: NsdServiceInfo, errorCode: Int) {
                Log.w(TAG, "Unregistration failed: $errorCode")
            }
        }

        try {
            manager.registerService(info, NsdManager.PROTOCOL_DNS_SD, registration)
            nsdManager = manager
            listener = registration
            registeredAs = desired
        } catch (e: Exception) {
            // Discovery is a convenience; the TV must keep playing regardless.
            Log.w(TAG, "Could not register service: ${e.message}")
            registeredAs = null
        }
    }

    @Synchronized
    fun stop() {
        val manager = nsdManager
        val current = listener
        if (manager != null && current != null) {
            try {
                manager.unregisterService(current)
            } catch (e: Exception) {
                Log.w(TAG, "Could not unregister: ${e.message}")
            }
        }
        nsdManager = null
        listener = null
        registeredAs = null
    }

    private fun putAttribute(info: NsdServiceInfo, key: String, value: String?) {
        if (value.isNullOrBlank()) {
            return
        }
        try {
            info.setAttribute(key, value)
        } catch (e: Exception) {
            Log.w(TAG, "Could not set TXT $key: ${e.message}")
        }
    }
}
