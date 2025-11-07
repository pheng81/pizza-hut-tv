#!/bin/bash
# Fix webplayer to only use global sync for items WITH sync_ref

cd /var/www/pizza-hut-tv

# Backup original
cp templates/webplayer/player.html templates/webplayer/player.html.backup-sync-fix

# Create the fixed version using Python
python3 << 'PYTHON_EOF'
with open('templates/webplayer/player.html', 'r') as f:
    content = f.read()

# Find and replace the sync logic
old_code = '''// 🏆 GLOBAL SYNC: All screens synchronized to server timestamp
\t\t\tconst syncMoment = syncCoordinator.calculateSyncMoment(dur);
\t\t\tconst currentTime = Date.now();
\t\t\tconst syncDelay = Math.max(0, syncMoment - currentTime);
\t\t\t
\t\t\tconsole.log('🎯 GLOBAL SYNC: All screens syncing in', syncDelay, 'ms to timestamp', syncMoment);
\t\t\t
\t\t\t// Wait for sync moment, then show item simultaneously across all screens
\t\t\tif(syncDelay > 0) {
\t\t\t\tif(timer){ clearTimeout(timer); }
\t\t\t\ttimer = setTimeout(async () => {
\t\t\t\t\tawait showItem(item);
\t\t\t\t\tconsole.log('✅ SYNCHRONIZED: Screen', screenId, 'started at global sync timestamp');
\t\t\t\t\t
\t\t\t\t\t// Schedule next tick at synchronized interval
\t\t\t\t\tif(timer){ clearTimeout(timer); }
\t\t\t\t\ttimer = setTimeout(tick, dur*1000);
\t\t\t\t}, syncDelay);
\t\t\t\treturn;
\t\t\t}
\t\t\t
\t\t\t// Immediate show if already at sync moment
\t\t\tawait showItem(item);
\t\t\tidx = nextIndex();
\t\t\tif(Date.now() - lastFetchTs > PLAYLIST_REFRESH_MIN_MS){ fetchPlaylist(); }
\t\t\t
\t\t\t// Use global sync for next transition instead of individual timing
\t\t\tif(timer){ clearTimeout(timer); }
\t\t\ttimer = setTimeout(tick, dur*1000);'''

new_code = '''// 🏆 SMART SYNC: Only use global sync for items WITH sync_ref, normal rotation for others
\t\t\tconst hasSync = item && item.sync_ref;
\t\t\t
\t\t\tif(hasSync) {
\t\t\t\t// SYNCHRONIZED PLAYBACK: Wait for global sync moment for synced items
\t\t\t\tconst syncMoment = syncCoordinator.calculateSyncMoment(dur);
\t\t\t\tconst currentTime = Date.now();
\t\t\t\tconst syncDelay = Math.max(0, syncMoment - currentTime);
\t\t\t\t
\t\t\t\tconsole.log('🎯 SYNC ITEM: Waiting', syncDelay, 'ms for global sync timestamp', syncMoment);
\t\t\t\t
\t\t\t\tif(syncDelay > 0) {
\t\t\t\t\tif(timer){ clearTimeout(timer); }
\t\t\t\t\ttimer = setTimeout(async () => {
\t\t\t\t\t\tawait showItem(item);
\t\t\t\t\t\tconsole.log('✅ SYNCHRONIZED: Screen', screenId, 'synced item started');
\t\t\t\t\t\t
\t\t\t\t\t\tidx = nextIndex();
\t\t\t\t\t\tif(timer){ clearTimeout(timer); }
\t\t\t\t\t\ttimer = setTimeout(tick, dur*1000);
\t\t\t\t\t}, syncDelay);
\t\t\t\t\treturn;
\t\t\t\t}
\t\t\t}
\t\t\t
\t\t\t// NORMAL PLAYBACK: Immediate show for non-synced items (images, etc.)
\t\t\tconsole.log(hasSync ? '🎯 SYNC ITEM: Immediate show (already at sync moment)' : '📸 NORMAL ITEM: Playing immediately');
\t\t\tawait showItem(item);
\t\t\tidx = nextIndex();
\t\t\tif(Date.now() - lastFetchTs > PLAYLIST_REFRESH_MIN_MS){ fetchPlaylist(); }
\t\t\t
\t\t\t// Schedule next tick based on item duration
\t\t\tif(timer){ clearTimeout(timer); }
\t\t\ttimer = setTimeout(tick, dur*1000);'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('templates/webplayer/player.html', 'w') as f:
        f.write(content)
    print("✅ Successfully applied smart sync fix!")
    print("   - Items WITH sync_ref: Use global sync (videos stay synchronized)")
    print("   - Items WITHOUT sync_ref: Play immediately (images display instantly)")
else:
    print("❌ Could not find target code to replace")
    print("   Looking for: '// 🏆 GLOBAL SYNC: All screens synchronized...'")
PYTHON_EOF

echo ""
echo "Restarting service..."
sudo systemctl restart pizza-hut-tv
sleep 2
echo ""
echo "Service status:"
sudo systemctl status pizza-hut-tv --no-pager | head -10
