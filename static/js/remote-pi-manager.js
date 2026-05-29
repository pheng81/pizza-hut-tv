// Remote Pi Manager - External JS File v3.0.0
// This file ensures proper screen filtering by store

console.log('🔧 Remote Pi Manager External JS loaded - v3.0.0');
console.log('✅ EXTERNAL JS - Cache should be cleared!');
console.log('🔍 Loading timestamp:', Date.now()); // Debug: track each load

// Global variable to store user's filtered data from API
// Changed to window property to avoid redeclaration errors
window.userStoresData = window.userStoresData || null;

function resetRemotePiManagerUi(options = {}) {
    const { resetForm = false } = options;
    const form = document.getElementById('remotePiManagerForm');

    if (resetForm && form) {
        form.reset();
    }

    const statusDiv = document.getElementById('piConfigStatus');
    if (statusDiv) {
        statusDiv.style.display = 'none';
        statusDiv.innerHTML = '';
    }

    const connectionStatus = document.getElementById('piConnectionStatus');
    if (connectionStatus) {
        connectionStatus.style.display = 'none';
    }

    ['stepPairCode', 'stepStoreId', 'stepScreenId', 'piScreenPreview'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.style.display = 'none';
        }
    });

    ['closeScreenBtn', 'restartClientBtn', 'restartPiBtn'].forEach(id => {
        const button = document.getElementById(id);
        if (button) {
            button.style.display = 'none';
        }
    });

    const notConnectedButtons = document.getElementById('piNotConnectedButtons');
    if (notConnectedButtons) {
        notConnectedButtons.style.display = 'none';
    }

    const connectBtn = document.getElementById('connectPiBtn');
    if (connectBtn) {
        connectBtn.disabled = false;
        connectBtn.textContent = 'Connect';
        connectBtn.style.background = '#667eea';
        connectBtn.style.borderColor = '#667eea';
    }

    const storeSelect = document.getElementById('piStoreId');
    if (storeSelect) {
        storeSelect.innerHTML = '<option value="">Select Store...</option>';
    }

    const screenSelect = document.getElementById('piScreenId');
    if (screenSelect) {
        screenSelect.innerHTML = '<option value="">Select Screen...</option>';
    }

    window.userStoresData = null;

    if (typeof window.updateRemotePiConfigureButtonState === 'function') {
        window.updateRemotePiConfigureButtonState();
    }
    if (typeof window.syncNewPiInstallCommand === 'function') {
        window.syncNewPiInstallCommand();
    }
}

function openRemotePiManager() {
    console.log('🚀 openRemotePiManager v3.0.0 called');
    resetRemotePiManagerUi();
    document.getElementById('remotePiManagerModal').style.display = 'flex';
    document.getElementById('piId').focus();
    // Close drawer if open
    if (typeof toggleDrawer === 'function') {
        toggleDrawer(false);
    }

    setTimeout(() => {
        if (typeof window.ensureRemotePiConfigSelections === 'function') {
            window.ensureRemotePiConfigSelections();
        }

        const pairCodeInput = document.getElementById('piPairCode');
        if (pairCodeInput && pairCodeInput.value && pairCodeInput.value.length === 4) {
            console.log('🔄 Pairing code pre-filled, auto-fetching stores...');
            showStoreStep();
        }
    }, 100);

    if (typeof window.updateRemotePiConfigureButtonState === 'function') {
        window.updateRemotePiConfigureButtonState();
    }
    if (typeof window.syncNewPiInstallCommand === 'function') {
        window.syncNewPiInstallCommand();
    }
}

function closeRemotePiManager() {
    document.getElementById('remotePiManagerModal').style.display = 'none';
    resetRemotePiManagerUi({ resetForm: true });
}

// Step navigation functions for Remote Pi Manager
async function showStoreStep() {
    const pairCode = document.getElementById('piPairCode').value.trim();
    console.log('showStoreStep called, pair code:', pairCode, 'length:', pairCode.length);
    if (typeof window.syncNewPiInstallCommand === 'function') {
        window.syncNewPiInstallCommand();
    }
    
    if (pairCode.length === 4) {
        const myPairingCode = typeof MY_PAIRING_CODE !== 'undefined' ? MY_PAIRING_CODE : '';

        if (myPairingCode && pairCode !== myPairingCode) {
            console.warn('❌ Pairing code mismatch - entered:', pairCode, 'expected:', myPairingCode);
            alert('⚠️ Security: You can only configure devices using your own pairing code (' + myPairingCode + ').\n\nThe code you entered (' + pairCode + ') belongs to a different user.');
            document.getElementById('piPairCode').value = '';
            document.getElementById('stepStoreId').style.display = 'none';
            document.getElementById('stepScreenId').style.display = 'none';
            return;
        }

        try {
            // Fetch stores and screens from API using the pairing code
            const response = await fetch(`/api/stores_by_code/${pairCode}`, { cache: 'no-store' });
            const data = await response.json();
            
            console.log('API Response:', data);
            
            if (data.success && data.stores && data.stores.length > 0) {
                // Store the complete user data (stores + screens) globally
                if (typeof window.setRemotePiStoresData === 'function') {
                    window.setRemotePiStoresData(data);
                } else {
                    window.userStoresData = data;
                }
                
                // Populate store dropdown with user's stores
                const storeSelect = document.getElementById('piStoreId');
                if (typeof window.populateRemotePiStoreOptions === 'function') {
                    window.populateRemotePiStoreOptions(data);
                } else {
                    storeSelect.innerHTML = '<option value="">Select Store...</option>';
                    
                    data.stores.forEach(store => {
                        const opt = document.createElement('option');
                        opt.value = store.id;
                        opt.textContent = `${store.id} - ${store.name || 'Store ' + store.id}`;
                        storeSelect.appendChild(opt);
                    });
                }
                
                console.log('✅ Populated', data.stores.length, 'stores');
                document.getElementById('stepStoreId').style.display = 'block';
                document.getElementById('stepScreenId').style.display = 'none';
                
                // If only one store, auto-select it and show screen step
                if (data.stores.length === 1) {
                    storeSelect.value = data.stores[0].id;
                    showScreenStep();
                }

                if (typeof window.updateRemotePiConfigureButtonState === 'function') {
                    window.updateRemotePiConfigureButtonState();
                }
                if (typeof window.syncNewPiInstallCommand === 'function') {
                    window.syncNewPiInstallCommand();
                }
            } else {
                const fallbackData = typeof window.getRemotePiStoresData === 'function'
                    ? window.getRemotePiStoresData()
                    : null;

                if (fallbackData && fallbackData.stores && fallbackData.stores.length > 0) {
                    console.warn('⚠️ Falling back to embedded dashboard store data');
                    if (typeof window.setRemotePiStoresData === 'function') {
                        window.setRemotePiStoresData(fallbackData);
                    } else {
                        window.userStoresData = fallbackData;
                    }
                    if (typeof window.populateRemotePiStoreOptions === 'function') {
                        window.populateRemotePiStoreOptions(fallbackData);
                    }
                    document.getElementById('stepStoreId').style.display = 'block';
                    if (typeof window.updateRemotePiConfigureButtonState === 'function') {
                        window.updateRemotePiConfigureButtonState();
                    }
                    if (typeof window.syncNewPiInstallCommand === 'function') {
                        window.syncNewPiInstallCommand();
                    }
                    return;
                }

                alert('Invalid pairing code or no stores found.');
            }
        } catch (error) {
            console.error('❌ Error fetching stores:', error);
            const fallbackData = typeof window.getRemotePiStoresData === 'function'
                ? window.getRemotePiStoresData()
                : null;

            if (fallbackData && fallbackData.stores && fallbackData.stores.length > 0) {
                console.warn('⚠️ Falling back to embedded dashboard store data after fetch error');
                if (typeof window.setRemotePiStoresData === 'function') {
                    window.setRemotePiStoresData(fallbackData);
                } else {
                    window.userStoresData = fallbackData;
                }
                if (typeof window.populateRemotePiStoreOptions === 'function') {
                    window.populateRemotePiStoreOptions(fallbackData);
                }
                document.getElementById('stepStoreId').style.display = 'block';
                if (typeof window.updateRemotePiConfigureButtonState === 'function') {
                    window.updateRemotePiConfigureButtonState();
                }
                if (typeof window.syncNewPiInstallCommand === 'function') {
                    window.syncNewPiInstallCommand();
                }
                return;
            }

            alert('Failed to verify pairing code. Please check your connection.');
        }
    }
}

function showScreenStep() {
    const storeId = document.getElementById('piStoreId').value;
    console.log('showScreenStep called, store ID:', storeId);
    const remotePiStoresData = typeof window.getRemotePiStoresData === 'function'
        ? window.getRemotePiStoresData()
        : window.userStoresData;
    
    if (storeId && remotePiStoresData) {
        // Populate screen dropdown based on user's actual screens for this store
        const screenSelect = document.getElementById('piScreenId');
        const selectedScreenId = screenSelect.value;
        screenSelect.innerHTML = '<option value="">Select Screen...</option>';
        
        // Get screens for this specific store from the API data
        const storeScreens = remotePiStoresData.screens[storeId] || {};
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

            if (selectedScreenId && screenIds.includes(selectedScreenId)) {
                screenSelect.value = selectedScreenId;
            }
        }
        
        console.log('✅ Showing screen step with', screenIds.length, 'screens');
        document.getElementById('stepScreenId').style.display = 'block';
    } else {
        document.getElementById('stepScreenId').style.display = 'none';
    }

    if (typeof window.updateRemotePiConfigureButtonState === 'function') {
        window.updateRemotePiConfigureButtonState();
    }

    if (typeof window.syncNewPiInstallCommand === 'function') {
        window.syncNewPiInstallCommand();
    }
}

console.log('✅ Remote Pi Manager external JS fully loaded');
