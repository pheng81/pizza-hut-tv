#!/usr/bin/env python3
"""
Test script to verify the schedule logic is working properly
"""

import datetime
from dateutil import parser, tz

def parse_time_string(timestr, ref_time):
    """Parse time string into datetime object"""
    if not timestr:
        return None
    
    # Handle date + time format (ISO)
    if 'T' in timestr:
        try:
            return parser.parse(timestr).replace(tzinfo=None)
        except:
            return None
    
    # Handle date-only format
    if len(timestr) == 10 and timestr[4] == '-' and timestr[7] == '-':
        try:
            dt = datetime.datetime.strptime(timestr, '%Y-%m-%d')
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        except:
            return None
    
    # Handle time-only format
    try:
        parts = timestr.split(':')
        if len(parts) >= 2:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return ref_time.replace(hour=h, minute=m, second=s, microsecond=0)
    except:
        return None
    
    return None

def interval_active(raw_s, raw_e, now, days=None):
    """Return True if now is inside the interval defined by raw_s/raw_e."""
    def is_time_only(v):
        return bool(v) and (len(v) <= 8) and (':' in v) and ('-' not in v)
    def is_date_only(v):
        return bool(v) and (len(v) == 10) and (v[4] == '-' and v[7] == '-')
    def is_absolute(v):
        return bool(v) and (('T' in v) or is_date_only(v))

    # If either boundary is absolute (has a date), ignore weekday gating
    if not (is_absolute(raw_s) or is_absolute(raw_e)):
        if days:
            wd = ['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]
            if wd not in days:
                return False

    if not (raw_s or raw_e):
        return False
    
    ws = parse_time_string(raw_s, now) if raw_s else None
    we = parse_time_string(raw_e, now) if raw_e else None
    
    # Normalize date-only single-sided inputs to same-day window
    if raw_e and is_date_only(raw_e) and we:
        we = we.replace(hour=23, minute=59, second=59, microsecond=999999)
    if (raw_s and is_date_only(raw_s)) and not raw_e and ws:
        # start is date-only, no end -> clamp end to end-of-day
        we = ws.replace(hour=23, minute=59, second=59, microsecond=999999)
    if (raw_e and is_date_only(raw_e)) and not raw_s and we:
        # end is date-only, no start -> clamp start to start-of-day
        ws = we.replace(hour=0, minute=0, second=0, microsecond=0)

    time_only = (is_time_only(raw_s) or is_time_only(raw_e))
    if ws and we:
        if we < ws:
            if not time_only and ws.date() == we.date():
                we_plus = we + datetime.timedelta(days=1)
                return ws <= now <= we_plus
            return (now >= ws) or (now <= we)
        return ws <= now <= we
    if ws and now < ws:
        return False
    if we and now > we:
        return False
    return True

def test_schedule_logic():
    """Test various scheduling scenarios"""
    
    # Test current time: Wednesday 3:30 PM
    now = datetime.datetime(2025, 9, 19, 15, 30, 0)  # Wed 3:30 PM
    
    print(f"Testing schedule logic with current time: {now} ({['mon','tue','wed','thu','fri','sat','sun'][now.weekday()]})")
    print("="*60)
    
    # Test cases
    test_cases = [
        # Time-only tests with weekdays
        ("14:00", "16:00", ["wed"], "Time range 2-4 PM on Wednesday", True),
        ("14:00", "16:00", ["tue"], "Time range 2-4 PM on Tuesday", False),
        ("16:00", "18:00", ["wed"], "Time range 4-6 PM on Wednesday", False),
        
        # Overnight time-only
        ("22:00", "02:00", ["wed"], "Overnight 10PM-2AM on Wednesday", False),
        ("22:00", "02:00", ["tue"], "Overnight 10PM-2AM on Tuesday", True), # Should be active (starts yesterday)
        
        # Date-only tests (ignore weekdays)
        ("2025-09-19", None, ["tue"], "Today (2025-09-19), ignores weekday", True),
        ("2025-09-18", None, ["wed"], "Yesterday (2025-09-18)", False),
        
        # DateTime tests (absolute)
        ("2025-09-19T14:00:00", "2025-09-19T16:00:00", ["tue"], "Absolute datetime today 2-4 PM, ignores weekday", True),
        ("2025-09-19T16:00:00", "2025-09-19T18:00:00", ["wed"], "Absolute datetime today 4-6 PM", False),
        
        # Edge cases
        ("", "", None, "Empty start and end", False),
        ("15:30", "", ["wed"], "Exact current time as start, no end", True),
        ("", "15:30", ["wed"], "No start, exact current time as end", True),
        ("15:31", "", ["wed"], "1 minute in future as start", False),
    ]
    
    for start, end, days, description, expected in test_cases:
        result = interval_active(start, end, now, days)
        status = "✓ PASS" if result == expected else "✗ FAIL"
        print(f"{status}: {description}")
        print(f"       Start: {start}, End: {end}, Days: {days}, Result: {result}, Expected: {expected}")
        if result != expected:
            print(f"       ERROR: Expected {expected}, got {result}")
        print()

if __name__ == "__main__":
    test_schedule_logic()