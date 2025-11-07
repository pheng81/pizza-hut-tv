/**
 * 🚀 ULTRA-PRECISE SERVER TIME SYNCHRONIZATION
 * Eliminates clock drift between screens for perfect video sync
 */

// Global sync state
let serverTimeOffset = 0; // Milliseconds to add to client time
let networkLatency = 0; // Average network round-trip time
let lastServerSync = 0; // Last time we synced with server
let syncSamples = []; // Historical sync data for drift compensation

/**
 * Get server timestamp with multiple samples for accuracy
 * Uses NTP-style algorithm to account for network latency
 */
async function getServerTime() {
	const maxRetries = 5; // Take 5 samples for accuracy
	const samples = [];
	
	for(let attempt = 0; attempt < maxRetries; attempt++) {
		try {
			const t0 = performance.now(); // High-precision local time
			const clientSend = Date.now();
			
			const response = await fetch('/api/sync-time', { 
				cache: 'no-store',
				headers: { 'X-Client-Time': clientSend.toString() }
			});
			
			const t1 = performance.now();
			const roundTrip = t1 - t0;
			
			const data = await response.json();
			const serverTime = data.timestamp;
			const clientReceive = Date.now();
			
			// Calculate offset accounting for network latency
			// Assume symmetrical network delay (server time was at midpoint)
			const latency = roundTrip / 2;
			const offset = serverTime - clientReceive + latency;
			
			samples.push({
				offset: offset,
				latency: latency,
				roundTrip: roundTrip
			});
			
		} catch(err) {
			console.warn(`Server time sync attempt ${attempt + 1} failed:`, err);
			if(attempt === maxRetries - 1) {
				console.warn('All server time sync attempts failed, using client time');
				return Date.now();
			}
			// Wait before retry
			await new Promise(resolve => setTimeout(resolve, 100));
		}
	}
	
	if(samples.length > 0) {
		// Calculate median offset for better accuracy (removes outliers)
		const offsets = samples.map(s => s.offset).sort((a, b) => a - b);
		const medianOffset = offsets[Math.floor(offsets.length / 2)];
		
		// Calculate average latency
		const avgLatency = samples.reduce((sum, s) => sum + s.latency, 0) / samples.length;
		
		serverTimeOffset = medianOffset;
		networkLatency = avgLatency;
		lastServerSync = Date.now();
		
		// Store samples for drift analysis
		syncSamples.push({
			offset: medianOffset,
			latency: avgLatency,
			timestamp: lastServerSync
		});
		
		// Keep only last 10 samples
		if(syncSamples.length > 10) {
			syncSamples = syncSamples.slice(-10);
		}
		
		console.log('🌐 SERVER TIME SYNCED:', {
			medianOffset: medianOffset.toFixed(3) + 'ms',
			avgLatency: avgLatency.toFixed(1) + 'ms',
			samples: samples.length
		});
		
		return Date.now() + medianOffset;
	}
	
	return Date.now(); // Fallback
}

/**
 * Get current server-synchronized time with drift compensation
 */
function getServerSyncedTime() {
	const clientTime = Date.now();
	
	// Re-sync every 10 seconds to maintain accuracy
	if(clientTime - lastServerSync > 10000) {
		getServerTime(); // Async refresh in background
	}
	
	// Apply drift compensation if we have multiple samples
	let adjustedOffset = serverTimeOffset;
	if(syncSamples.length >= 3) {
		// Calculate drift trend from recent samples
		const recent = syncSamples.slice(-5);
		const oldestTime = recent[0].timestamp;
		const newestTime = recent[recent.length - 1].timestamp;
		const oldestOffset = recent[0].offset;
		const newestOffset = recent[recent.length - 1].offset;
		
		if(newestTime > oldestTime) {
			const driftRate = (newestOffset - oldestOffset) / (newestTime - oldestTime);
			const timeSinceLastSync = clientTime - lastServerSync;
			adjustedOffset = serverTimeOffset + (driftRate * timeSinceLastSync);
		}
	}
	
	return clientTime + adjustedOffset;
}

/**
 * 🎯 ULTRA-PRECISE SYNC WAIT - All screens start at exact same moment
 * Uses server time to eliminate any client clock drift
 */
async function stableSyncWait(syncGroup, screenId) {
	// Get server-synchronized time
	const serverTime = getServerSyncedTime();
	
	// 🚀 TIGHTER SYNC: Use 1-second intervals instead of 2 seconds
	// This reduces maximum wait time from 2s to 1s for faster startup
	const SYNC_INTERVAL = 1000; // 1 second boundaries
	
	// Calculate next sync boundary
	const nextSyncMoment = Math.ceil(serverTime / SYNC_INTERVAL) * SYNC_INTERVAL;
	const waitTime = Math.max(0, nextSyncMoment - serverTime);
	
	console.log(`🎯 PRECISE SYNC WAIT [${screenId}]:`, {
		group: syncGroup,
		wait: waitTime.toFixed(0) + 'ms',
		nextSync: new Date(nextSyncMoment).toISOString(),
		serverOffset: serverTimeOffset.toFixed(1) + 'ms'
	});
	
	// Wait until sync moment
	if(waitTime > 0) {
		await new Promise(resolve => setTimeout(resolve, waitTime));
	}
	
	console.log(`✅ SYNC READY [${screenId}] - Starting NOW!`);
}
