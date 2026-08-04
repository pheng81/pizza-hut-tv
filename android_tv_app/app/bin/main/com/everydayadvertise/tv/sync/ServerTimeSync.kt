package com.everydayadvertise.tv.sync

import android.util.Log
import com.everydayadvertise.tv.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Lightweight server time synchronizer for precise multi-screen alignment.
 * - Computes server->client time offset using multiple samples
 * - Provides server-synced time for scheduling
 */
object ServerTimeSync {
    private const val TAG = "ServerTimeSync"
    @Volatile private var serverOffsetMs: Double = 0.0
    @Volatile private var lastSyncMs: Long = 0L
    private val samples = CopyOnWriteArrayList<Double>()

    private fun now(): Long = System.currentTimeMillis()

    fun getServerSyncedTime(): Long {
        val clientNow = now()
        // Background refresh every 5 seconds
        if (clientNow - lastSyncMs > 5_000L) {
            // Fire-and-forget refresh (caller should manage scope)
            // We avoid starting coroutines here to keep it simple; caller can invoke refreshIfStale()
        }
        return (clientNow + serverOffsetMs).toLong()
    }

    fun computeDelayToNextBoundary(syncIntervalMs: Int, warmupMs: Long = 150L, minWindowMs: Long = 10L): Long {
        val nowServer = getServerSyncedTime()
        val interval = syncIntervalMs.coerceAtLeast(100)
        val next = ((nowServer + interval - 1) / interval) * interval
        var delay = (next - nowServer - warmupMs)
        if (delay < minWindowMs) {
            delay += interval.toLong()
        }
        return delay.coerceAtLeast(0L)
    }

    suspend fun initialSync(sampleCount: Int = 5) {
        samples.clear()
        repeat(sampleCount.coerceAtLeast(3)) { idx ->
            try {
                val before = now()
                val st = withContext(Dispatchers.IO) { ApiClient.service.getSyncTime() }
                val after = now()
                val recv = after // approximate receive time
                val serverCurrent = st.currentTime ?: (st.timestamp - st.delayMs)
                val offset = serverCurrent - recv
                samples.add(offset.toDouble())
                Log.d(TAG, "sample ${idx+1}: offset=${"%.3f".format(offset)}ms rtt=${after - before}ms")
            } catch (e: Exception) {
                Log.w(TAG, "sync sample failed: ${e.message}")
            }
        }
        if (samples.isNotEmpty()) {
            val sorted = samples.sorted()
            val median = sorted[sorted.size / 2]
            serverOffsetMs = median
            lastSyncMs = now()
            Log.i(TAG, "server offset set to ${"%.3f".format(serverOffsetMs)}ms from ${samples.size} samples")
        }
    }

    suspend fun refreshIfStale(maxAgeMs: Long = 5_000L) {
        if (now() - lastSyncMs > maxAgeMs) {
            try { initialSync(3) } catch (_: Exception) {}
        }
    }
}
