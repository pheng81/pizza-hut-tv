import sqlite3
import json

# Connect to database
conn = sqlite3.connect('pizzahut_tv.db')
cursor = conn.cursor()

# First check what tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("=== Available Tables ===")
for table in tables:
    print(f"- {table[0]}")

print("\n=== Checking for Pi2 Registration ===")

# Check if auto_registered_pis table exists
table_to_use = None
for table in tables:
    if 'pi' in table[0].lower() and 'register' in table[0].lower():
        table_to_use = table[0]
        print(f"Using table: {table_to_use}")
        break

if not table_to_use:
    print("No Pi registration table found!")
    print("\n=== All User Configs ===")
    cursor.execute("SELECT store_id, screen_id FROM user_configs")
    configs = cursor.fetchall()
    for config in configs:
        print(f"Store: {config[0]}, Screen: {config[1]}")
    conn.close()
    exit()

# Get pi2 registration
if table_to_use == 'auto_registered_pis':
    cursor.execute(f"""
        SELECT store_id, screen_id, device_id, last_seen, status
        FROM {table_to_use}
        WHERE device_id LIKE '%pi2%' OR device_id LIKE '%0002%' OR device_id LIKE '%113%'
    """)
    pi2_registrations = cursor.fetchall()
    
    if not pi2_registrations:
        # Show all registrations
        print("No pi2 found, showing all registrations:")
        cursor.execute(f"SELECT store_id, screen_id, device_id, last_seen, status FROM {table_to_use}")
        all_regs = cursor.fetchall()
        for reg in all_regs:
            print(f"Store: {reg[0]}, Screen: {reg[1]}, Device: {reg[2]}, Last: {reg[3]}, Status: {reg[4]}")
else:
    cursor.execute(f"""
        SELECT store_id, screen_id, pi_id, last_seen 
        FROM {table_to_use}
        WHERE pi_id LIKE '%pi2%' OR pi_id LIKE '%0002%' OR pi_id LIKE '%113%'
    """)
    pi2_registrations = cursor.fetchall()
    
    if not pi2_registrations:
        print("No pi2 found, showing all registrations:")
        cursor.execute(f"SELECT store_id, screen_id, pi_id, last_seen FROM {table_to_use}")
        all_regs = cursor.fetchall()
        for reg in all_regs:
            print(f"Store: {reg[0]}, Screen: {reg[1]}, Pi ID: {reg[2]}, Last: {reg[3]}")

pi2_registrations = cursor.fetchall()

print("=== Pi2 Registrations ===")
if pi2_registrations:
    for reg in pi2_registrations:
        print(f"Store: {reg[0]}, Screen: {reg[1]}, Pi ID: {reg[2]}, Last Seen: {reg[3]}")
else:
    print("No registrations found for pi2")
    
    # Show all registrations to help identify
    print("\n=== All Registered Pis ===")
    cursor.execute("SELECT store_id, screen_id, pi_id, last_seen FROM registered_pis")
    all_pis = cursor.fetchall()
    for reg in all_pis:
        print(f"Store: {reg[0]}, Screen: {reg[1]}, Pi ID: {reg[2]}, Last Seen: {reg[3]}")

# If we found pi2, get its playlist
if pi2_registrations:
    for reg in pi2_registrations:
        store_id = reg[0]
        screen_id = reg[1]
        
        print(f"\n=== Playlist for {store_id}/{screen_id} ===")
        
        # Get the configuration
        cursor.execute("""
            SELECT config FROM user_configs 
            WHERE store_id = ? AND screen_id = ?
        """, (store_id, screen_id))
        
        result = cursor.fetchone()
        if result:
            config = json.loads(result[0])
            playlist = config.get('playlist', [])
            
            print(f"Total items in playlist: {len(playlist)}")
            print("\nPlaylist items:")
            for i, item in enumerate(playlist, 1):
                print(f"\n{i}. Type: {item.get('type', 'unknown')}")
                print(f"   Duration: {item.get('duration', 'N/A')} seconds")
                print(f"   URL: {item.get('url', 'N/A')[:80]}...")
                
                # Check for schedule
                schedule = item.get('schedule', {})
                if schedule:
                    print(f"   Schedule:")
                    print(f"     - Start Date: {schedule.get('start_date', 'N/A')}")
                    print(f"     - End Date: {schedule.get('end_date', 'N/A')}")
                    print(f"     - Start Time: {schedule.get('start_time', 'N/A')}")
                    print(f"     - End Time: {schedule.get('end_time', 'N/A')}")
                    print(f"     - Days: {schedule.get('days', [])}")
                else:
                    print(f"   Schedule: No schedule (plays 24/7)")
        else:
            print("No configuration found for this screen")

conn.close()
