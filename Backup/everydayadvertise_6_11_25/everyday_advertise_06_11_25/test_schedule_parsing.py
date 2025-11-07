#!/usr/bin/env python3
"""Test the parse_datetime function with your actual schedule format"""

from datetime import datetime, time as time_type

def parse_datetime(time_str: str):
    """
    Parse time string from dashboard.
    Supports: "HH:MM:SS", "HH:MM", "mm/dd/yyyy HH:MM:SS"
    Returns: datetime, time, or None
    """
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # Try full datetime: "mm/dd/yyyy HH:MM:SS"
    try:
        return datetime.strptime(time_str, "%m/%d/%Y %H:%M:%S")
    except:
        pass
    # Try date only: "mm/dd/yyyy" (treated as that day at 00:00)
    try:
        d = datetime.strptime(time_str, "%m/%d/%Y").date()
        from datetime import time as _t
        return datetime.combine(d, _t(0,0,0))
    except:
        pass
    
    # Try time with seconds: "HH:MM:SS"
    try:
        return datetime.strptime(time_str, "%H:%M:%S").time()
    except:
        pass
    
    # Try time without seconds: "HH:MM"
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except:
        pass
    
    return None

# Test with your actual schedule values
print("="*80)
print("Testing parse_datetime with your schedule")
print("="*80)

start_str = "11/06/2025 10:00:00"
end_str = "11/06/2025 16:28:00"

print(f"\nSTART string: '{start_str}'")
start_dt = parse_datetime(start_str)
print(f"Parsed to: {start_dt}")
print(f"Type: {type(start_dt)}")

print(f"\nEND string: '{end_str}'")
end_dt = parse_datetime(end_str)
print(f"Parsed to: {end_dt}")
print(f"Type: {type(end_dt)}")

# Now test the comparison
current_date = datetime.now().date()
current_time = datetime.now().time()
current_dt = datetime.combine(current_date, current_time)

print(f"\n" + "="*80)
print(f"Current datetime: {current_dt}")
print(f"End datetime: {end_dt}")
print(f"Current > End? {current_dt > end_dt}")

if isinstance(end_dt, datetime):
    if current_dt > end_dt:
        print("\n✅ CORRECT: Current time IS after end time - SHOULD BLOCK")
    else:
        print("\n❌ WRONG: Current time is NOT after end time - would allow playback")
else:
    print("\n❌ ERROR: end_dt is not a datetime object!")
