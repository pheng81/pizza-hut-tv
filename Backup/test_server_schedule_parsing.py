#!/usr/bin/env python3
"""Test server-side schedule logic with Sydney timezone"""

from datetime import datetime, timedelta

# Server is using Sydney time (UTC+11)
timezone_offset_hours = 11

# Get current time in Sydney
now_sydney = datetime.utcnow() + timedelta(hours=timezone_offset_hours)

print("="*80)
print("SERVER-SIDE SCHEDULE CHECK (Sydney Time)")
print("="*80)
print(f"\nCurrent UTC time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Sydney time (UTC+{timezone_offset_hours}): {now_sydney.strftime('%Y-%m-%d %H:%M:%S')}")

# Your schedule uses mm/dd/yyyy format
start_str = "11/06/2025 10:00:00"
end_str = "11/06/2025 16:28:00"

# Server code tries to parse these dates
# But it's looking for YYYY-MM-DD format or ISO format!
# Let's see what happens:

def parse_time_string_server(time_str, now):
    """This is what the SERVER uses (from app.py line 7126)"""
    if not time_str:
        return None
    
    time_str = str(time_str).strip()
    if not time_str:
        return None
    
    # ISO datetime with T: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM
    if 'T' in time_str:
        try:
            return datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
        except:
            try:
                return datetime.strptime(time_str, '%Y-%m-%dT%H:%M')
            except:
                return None
    
    # Full datetime with space: YYYY-MM-DD HH:MM:SS
    if len(time_str) == 19 and time_str.count('-') == 2 and time_str.count(':') == 2:
        try:
            return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except:
            return None
    
    # Date only: YYYY-MM-DD
    if len(time_str) == 10 and time_str.count('-') == 2:
        try:
            return datetime.strptime(time_str, '%Y-%m-%d')
        except:
            return None
    
    # Time only: HH:MM or HH:MM:SS
    if ':' in time_str:
        try:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        except:
            return None
    
    return None

print(f"\n🔍 Testing SERVER's parse_time_string function:")
print(f"\nStart: '{start_str}'")
start_parsed = parse_time_string_server(start_str, now_sydney)
print(f"   Parsed to: {start_parsed}")
print(f"   Type: {type(start_parsed)}")

print(f"\nEnd: '{end_str}'")
end_parsed = parse_time_string_server(end_str, now_sydney)
print(f"   Parsed to: {end_parsed}")
print(f"   Type: {type(end_parsed)}")

print("\n" + "="*80)
if start_parsed is None or end_parsed is None:
    print("🐛 BUG FOUND!")
    print("="*80)
    print("\nThe SERVER cannot parse mm/dd/yyyy format!")
    print("It only understands:")
    print("  - YYYY-MM-DD HH:MM:SS")
    print("  - YYYY-MM-DDTHH:MM:SS")
    print("  - HH:MM:SS (time only)")
    print("\nYour dashboard is saving: mm/dd/yyyy HH:MM:SS")
    print("Server sees: None")
    print("Result: Server thinks there's NO schedule, so it ALWAYS plays!")
    print("\nFIX: Dashboard needs to save dates in YYYY-MM-DD format")
else:
    print("Server can parse the dates correctly")
    print("="*80)
