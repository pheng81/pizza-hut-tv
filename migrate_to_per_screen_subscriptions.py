#!/usr/bin/env python3
"""
Migrate existing screens to individual per-screen subscriptions
"""
import sqlite3
import json
import os
import time
from datetime import datetime

# Get database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')

def get_user_screens(username):
    """Get all screens for a user from their config file"""
    # Convert username to safe key format
    safe_key = username.lower().replace('@', '_at_')
    safe_key = ''.join(c for c in safe_key if c.isalnum() or c in '._-')
    
    config_path = os.path.join(BASE_DIR, f'store_config__{safe_key}.json')
    
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return []
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    screens = []
    screens_dict = config.get('screens', {})
    stores = {s['id']: s['name'] for s in config.get('stores', [])}
    
    for store_id, store_screens in screens_dict.items():
        store_name = stores.get(store_id, f'Store {store_id}')
        for screen_id, screen_data in store_screens.items():
            screens.append({
                'screen_id': screen_id,
                'store_id': store_id,
                'store_name': store_name,
                'screen_name': screen_id
            })
    
    return screens

def migrate_user_screens(user_id, username):
    """Create screen subscriptions for existing screens"""
    print(f"\n=== Migrating screens for {username} (ID: {user_id}) ===")
    
    screens = get_user_screens(username)
    print(f"Found {len(screens)} screens")
    
    if not screens:
        print("No screens to migrate")
        return
    
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Get existing subscription info
    sub = db.execute(
        'SELECT status, current_period_start, current_period_end FROM subscriptions WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    
    if sub:
        status = sub['status']
        period_start = sub['current_period_start']
        period_end = sub['current_period_end']
        print(f"Existing subscription: status={status}, period_end={datetime.fromtimestamp(period_end).strftime('%Y-%m-%d') if period_end else 'None'}")
    else:
        status = 'trialing'
        period_start = int(time.time())
        period_end = period_start + (14 * 24 * 60 * 60)  # 14 days trial
        print(f"No existing subscription, creating trial subscriptions")
    
    # Create individual screen subscriptions
    for screen in screens:
        try:
            # Check if already exists
            existing = db.execute(
                'SELECT id FROM screen_subscriptions WHERE user_id = ? AND screen_id = ? AND store_id = ?',
                (user_id, screen['screen_id'], screen['store_id'])
            ).fetchone()
            
            if existing:
                print(f"  ✓ Already exists: {screen['screen_name']}")
                continue
            
            # Insert screen subscription
            db.execute(
                'INSERT INTO screen_subscriptions '
                '(user_id, screen_id, store_id, screen_name, status, '
                'current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)',
                (user_id, screen['screen_id'], screen['store_id'], screen['screen_name'],
                 status, period_start, period_end, int(time.time()), int(time.time()))
            )
            print(f"  ✓ Created: {screen['screen_name']} (Store: {screen['store_name']})")
        except Exception as e:
            print(f"  ✗ Error creating {screen['screen_name']}: {e}")
    
    db.commit()
    db.close()
    print(f"Migration complete for {username}")

def main():
    """Main migration function"""
    print("=" * 60)
    print("MIGRATING EXISTING SCREENS TO PER-SCREEN SUBSCRIPTIONS")
    print("=" * 60)
    
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Get all users with subscriptions
    users = db.execute(
        'SELECT u.id, u.username FROM users u '
        'JOIN subscriptions s ON u.id = s.user_id '
        'WHERE u.username != "test9@gmail.com"'  # Skip admin
    ).fetchall()
    
    print(f"\nFound {len(users)} users with subscriptions")
    
    for user in users:
        migrate_user_screens(user['id'], user['username'])
    
    db.close()
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE!")
    print("=" * 60)
    print("\nYou can now:")
    print("1. View individual screen subscriptions in Account page")
    print("2. Cancel individual screens")
    print("3. Each screen shows its own billing date")

if __name__ == '__main__':
    main()
