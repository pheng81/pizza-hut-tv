
import json
import time

# Load config
with open("store_config__toengpheng_at_gmail.com.json", "r") as f:
    config = json.load(f)

# Update rotation metadata to current time
current_ts = int(time.time())
print(f"Updating rotation timestamps to current time: {current_ts}")

updated_count = 0
for store_id, store in config.get("screens", {}).items():
    for screen_id, screen in store.items():
        if "rotation_meta" in screen:
            old_ts = screen["rotation_meta"].get("last_ts", 0)
            screen["rotation_meta"]["last_ts"] = current_ts
            print(f"Updated {screen_id}: {old_ts} -> {current_ts}")
            updated_count += 1

# Save config
with open("store_config__toengpheng_at_gmail.com.json", "w") as f:
    json.dump(config, f, indent=2)

print(f"Configuration updated successfully! {updated_count} screens updated.")
