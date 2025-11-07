#!/usr/bin/env python3
"""
Diagnose why schedule ending at 16:28 is still playing at 17:05
This simulates exactly what the Pi client does
"""

from datetime import datetime, time as time_type
import json

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

def matches_schedule_window(sched: dict, current_day: int, current_time, current_date) -> bool:
    """Check if current time matches a single schedule window"""
    
    print(f"\n  🔍 Checking schedule window:")
    print(f"     Input: {sched}")
    
    # Check days of week (M T W T F S S from dashboard)
    days = sched.get('days', [])
    print(f"     Days: {days}")
    
    if days:
        if current_day not in days:
            print(f"     ❌ Day check failed: current_day={current_day} not in {days}")
            return False
        print(f"     ✅ Day check passed")
    else:
        print(f"     ✅ No days specified = all days allowed")
    
    # Check start date/time
    start_str = sched.get('start', '')
    start_dt = None
    if start_str:
        try:
            start_dt = parse_datetime(start_str)
            print(f"     Start: '{start_str}' → {start_dt} (type: {type(start_dt).__name__})")
            if start_dt:
                if isinstance(start_dt, datetime):
                    current_dt = datetime.combine(current_date, current_time)
                    if current_dt < start_dt:
                        print(f"     ❌ Start check failed: {current_dt} < {start_dt}")
                        return False
                    print(f"     ✅ Start check passed: {current_dt} >= {start_dt}")
        except Exception as e:
            print(f"     ⚠️  Start parse error: {e}")
    
    # Check end date/time
    end_str = sched.get('end', '')
    if end_str:
        try:
            end_dt = parse_datetime(end_str)
            print(f"     End: '{end_str}' → {end_dt} (type: {type(end_dt).__name__})")
            if end_dt:
                if isinstance(end_dt, datetime):
                    # Full datetime comparison
                    current_dt = datetime.combine(current_date, current_time)
                    print(f"     Comparing: {current_dt} > {end_dt}?")
                    if current_dt > end_dt:
                        print(f"     ❌ END CHECK FAILED: Current time IS AFTER end time - SHOULD BLOCK!")
                        return False
                    else:
                        print(f"     ✅ End check passed: {current_dt} <= {end_dt}")
                else:
                    # Time-only comparison
                    if isinstance(start_dt, datetime):
                        pass  # Mixed types already handled
                    else:
                        st_t = start_dt if start_dt else None
                        en_t = end_dt
                        if st_t is None:
                            if current_time > en_t:
                                print(f"     ❌ Time-only end check failed")
                                return False
                        else:
                            if st_t <= en_t:
                                if not (st_t <= current_time <= en_t):
                                    print(f"     ❌ Time window check failed")
                                    return False
                            else:
                                # Overnight
                                if not (current_time >= st_t or current_time <= en_t):
                                    print(f"     ❌ Overnight window check failed")
                                    return False
                        print(f"     ✅ Time-only check passed")
        except Exception as e:
            print(f"     ⚠️  End parse error: {e}")
    
    print(f"     ✅ ALL CHECKS PASSED - Schedule is ACTIVE")
    return True

# Test with your exact schedule
print("="*80)
print("SCHEDULE DIAGNOSIS")
print("="*80)

# Your schedule from the screenshot
schedule_window = {
    'days': [],  # No days selected = all days
    'start': '11/06/2025 10:00:00',
    'end': '11/06/2025 16:28:00',
    'enabled': True
}

# Current time
current_dt = datetime.now()
current_day = current_dt.isoweekday()  # 1=Monday, 7=Sunday
current_time = current_dt.time()
current_date = current_dt.date()

print(f"\n📅 Current DateTime: {current_dt.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Day of week: {current_day} (1=Mon, 7=Sun)")
print(f"   Time: {current_time}")
print(f"   Date: {current_date}")

print(f"\n📋 Testing Schedule Window:")
result = matches_schedule_window(schedule_window, current_day, current_time, current_date)

print(f"\n{'='*80}")
print(f"RESULT: Schedule is {'ACTIVE ✅' if result else 'INACTIVE ❌'}")
print(f"{'='*80}")

if result:
    print("\n🐛 BUG CONFIRMED: Schedule should be INACTIVE but is returning ACTIVE!")
    print("   Expected: INACTIVE (current time 17:05 > end time 16:28)")
    print("   Actual: ACTIVE (bug in code)")
else:
    print("\n✅ Schedule check is working correctly!")
    print("   The problem must be elsewhere (server filtering, multiple schedules, etc.)")
