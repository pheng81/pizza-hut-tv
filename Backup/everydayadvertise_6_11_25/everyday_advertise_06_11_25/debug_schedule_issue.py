#!/usr/bin/env python3
"""Debug why schedule is still active at 5:05 PM when it ends at 4:28 PM"""

import sqlite3
from datetime import datetime
import json

# Connect to database
conn = sqlite3.connect('pizza_hut_tv.db')
cursor = conn.cursor()

print("=" * 80)
print("SCHEDULE DEBUG - Checking test9 playlist")
print("=" * 80)

# Get test9 user's playlist
cursor.execute("SELECT id FROM users WHERE username = 'test9'")
user = cursor.fetchone()
if not user:
    print("❌ test9 user not found!")
    exit(1)

user_id = user[0]
print(f"✅ Found test9 user (ID: {user_id})")

# Get all playlist items for test9
cursor.execute("""
    SELECT id, file, schedule_data, enabled, days, start_time, end_time, position
    FROM playlists
    WHERE user_id = ?
    ORDER BY position
""", (user_id,))

items = cursor.fetchall()
print(f"\n📋 Found {len(items)} playlist items\n")

current_time = datetime.now()
print(f"⏰ Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} ({current_time.strftime('%A')})")
print(f"   Current day of week: {current_time.weekday()} (0=Mon, 6=Sun)")
print()

for row in items:
    item_id, file, schedule_data, enabled, days, start_time, end_time, position = row
    
    print("─" * 80)
    print(f"Item #{position}: {file}")
    print(f"  ID: {item_id}")
    print(f"  Enabled: {enabled}")
    print(f"  Legacy days field: {days}")
    print(f"  Legacy start_time: {start_time}")
    print(f"  Legacy end_time: {end_time}")
    
    # Parse schedule_data
    if schedule_data:
        try:
            schedules = json.loads(schedule_data)
            print(f"  Schedule Windows: {len(schedules)} window(s)")
            for i, sched in enumerate(schedules, 1):
                print(f"\n  Window #{i}:")
                print(f"    enabled: {sched.get('enabled', 'NOT SET')}")
                print(f"    days: {sched.get('days', 'NOT SET')}")
                print(f"    start: {sched.get('start', 'NOT SET')}")
                print(f"    end: {sched.get('end', 'NOT SET')}")
                
                # Check if this window should be active NOW
                days_list = sched.get('days', [])
                start_str = sched.get('start', '')
                end_str = sched.get('end', '')
                window_enabled = sched.get('enabled', True)
                
                print(f"\n    Analysis:")
                print(f"      Window enabled? {window_enabled}")
                
                if days_list:
                    print(f"      Days check: {days_list} (current: {current_time.weekday()})")
                    if current_time.weekday() in days_list:
                        print(f"        ✅ Current day IS in list")
                    else:
                        print(f"        ❌ Current day NOT in list - SHOULD BLOCK")
                else:
                    print(f"      Days check: EMPTY LIST [] - THIS IS THE BUG!")
                    print(f"        ⚠️  Empty days should mean 'NO DAYS' but code treats it as 'ALL DAYS'")
                
                if start_str:
                    print(f"      Start: {start_str}")
                if end_str:
                    print(f"      End: {end_str}")
                    try:
                        # Parse end time
                        if 'T' in end_str or ' ' in end_str:
                            # Full datetime
                            for fmt in ['%m/%d/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                                try:
                                    end_dt = datetime.strptime(end_str, fmt)
                                    print(f"        End datetime: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                                    if current_time > end_dt:
                                        print(f"        ❌ CURRENT TIME IS AFTER END - SHOULD BLOCK!")
                                    else:
                                        print(f"        ✅ Current time is before end")
                                    break
                                except:
                                    continue
                    except Exception as e:
                        print(f"        Error parsing: {e}")
        except json.JSONDecodeError as e:
            print(f"  ❌ Error parsing schedule_data: {e}")
    else:
        print(f"  Schedule Windows: None (using legacy fields)")
    
    print()

conn.close()

print("=" * 80)
print("CONCLUSION:")
print("The bug is that when days=[] (empty array), the code skips the day check")
print("and allows playback on ALL days instead of NO days.")
print("=" * 80)
