// Remote Pi Manager - External JS File v3.0.0
// This file ensures proper screen filtering by store

console.log('🔧 Remote Pi Manager External JS loaded - v3.0.0');
console.log('✅ EXTERNAL JS - Cache should be cleared!');
console.log('🔍 Loading timestamp:', Date.now()); // Debug: track each load

// Global variable to store user's filtered data from API
// Changed to window property to avoid redeclaration errors
window.userStoresData = window.userStoresData || null;

function openRemotePiManager() {
    console.log('🚀 openRemotePiManager v3.0.0 called');
    document.getElementById('remotePiManagerModal').style.display = 'flex';
    document.getElementById('piId').focus();
    // Close drawer if open
    if (typeof toggleDrawer === 'function') {
        toggleDrawer(false);
    }
}

function closeRemotePiManager() {
    document.getElementById('remotePiManagerModal').style.display = 'none';
    document.getElementById('remotePiManagerForm').reset();
    document.getElementById('piConfigStatus').style.display = 'none';
    document.getElementById('piConnectionStatus').style.display = 'none';
    document.getElementById('stepPairCode').style.display = 'none';
    document.getElementById('stepStoreId').style.display = 'none';
    document.getElementById('stepScreenId').style.display = 'none';
    document.getElementById('piNotConnectedButtons').style.display = 'none';
    window.userStoresData = null;
}

// Step navigation functions for Remote Pi Manager
async function showStoreStep() {
    const pairCode = document.getElementById('piPairCode').value.trim();
    console.log('showStoreStep called, pair code:', pairCode, 'length:', pairCode.length);
    
    if (pairCode.length === 4) {
        try {
            // Fetch stores and screens from API using the pairing code
            const response = await fetch(`/api/stores_by_code/${pairCode}`);
            const data = await response.json();
            
            console.log('API Response:', data);
            
            if (data.success && data.stores && data.stores.length > 0) {
                // Store the complete user data (stores + screens) globally
                window.userStoresData = data;
                
                // Populate store dropdown with user's stores
                const storeSelect = document.getElementById('piStoreId');
                storeSelect.innerHTML = '';
                
                data.stores.forEach(store => {
                    const opt = document.createElement('option');
                    opt.value = store.id;
                    opt.textContent = `${store.id} - ${store.name}`;
                    storeSelect.appendChild(opt);
                });
                
                console.log('✅ Populated', data.stores.length, 'stores');
                document.getElementById('stepStoreId').style.display = 'block';
                
                // If only one store, auto-select it and show screen step
                if (data.stores.length === 1) {
                    storeSelect.value = data.stores[0].id;
                    showScreenStep();
                }
            } else {
                alert('Invalid pairing code or no stores found.');
            }
        } catch (error) {
            console.error('❌ Error fetching stores:', error);
            alert('Failed to verify pairing code. Please check your connection.');
        }
    }
}

function showScreenStep() {
    const storeId = document.getElementById('piStoreId').value;
    console.log('showScreenStep called, store ID:', storeId);
    
    if (storeId && window.userStoresData) {
        // Populate screen dropdown based on user's actual screens for this store
        const screenSelect = document.getElementById('piScreenId');
        screenSelect.innerHTML = '<option value="">Select Screen...</option>';
        
        // Get screens for this specific store from the API data
        const storeScreens = window.userStoresData.screens[storeId] || {};
        const screenIds = Object.keys(storeScreens);
        
        console.log('Available screens for store', storeId, ':', screenIds);
        console.log('Screens data structure:', storeScreens);
        
        if (screenIds.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No screens configured for this store';
            opt.disabled = true;
            screenSelect.appendChild(opt);
        } else {
            screenIds.forEach(fullScreenId => {
                const screenData = storeScreens[fullScreenId];
                const opt = document.createElement('option');
                
                // Full screen ID includes store prefix (e.g., "1000_screen1")
                // We need to send this full ID to the Pi
                opt.value = fullScreenId;
                
                // For display, create a friendly name
                // Strip store prefix for cleaner display: "1000_screen1" -> "Screen 1"
                let displayName;
                if (screenData.name) {
                    displayName = screenData.name;
                } else if (screenData.screen_name) {
                    displayName = screenData.screen_name;
                } else {
                    // Extract just the screen part: "1000_screen1" -> "screen1"
                    const screenPart = fullScreenId.includes('_') ? fullScreenId.split('_')[1] : fullScreenId;
                    // Format nicely: "screen1" -> "Screen 1", "promo1" -> "Promo 1"
                    displayName = screenPart.replace(/([a-z]+)(\d+)/i, (match, p1, p2) => {
                        return p1.charAt(0).toUpperCase() + p1.slice(1) + ' ' + p2;
                    });
                }
                
                opt.textContent = displayName;
                screenSelect.appendChild(opt);
                
                console.log(`✅ Added screen option: ${displayName} (value: ${fullScreenId})`);
            });
        }
        
        console.log('✅ Showing screen step with', screenIds.length, 'screens');
        document.getElementById('stepScreenId').style.display = 'block';
    }
}

console.log('✅ Remote Pi Manager external JS fully loaded');
