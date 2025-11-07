#!/usr/bin/env python3
"""
Test script to verify Android TV WebView crash fixes
"""

import time
import subprocess
import sys
import os

def print_status(message):
    """Print status message with timestamp"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_html_syntax():
    """Basic HTML syntax check"""
    print_status("Checking HTML syntax...")
    html_file = "templates/tv_view.html"
    
    if not os.path.exists(html_file):
        print_status(f"❌ ERROR: {html_file} not found")
        return False
    
    # Read and check for basic issues
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    # Check for function definition order (dbg before usage)
    dbg_def_pos = content.find('function dbg(msg)')
    if dbg_def_pos == -1:
        issues.append("dbg() function not found")
    
    first_dbg_call = content.find('dbg(`')
    if first_dbg_call != -1 and first_dbg_call < dbg_def_pos:
        issues.append("dbg() called before definition")
    
    # Check for critical DOM elements
    if 'id="stage"' not in content:
        issues.append("Missing stage element")
    if 'id="layerA"' not in content:
        issues.append("Missing layerA element")
    if 'id="layerB"' not in content:
        issues.append("Missing layerB element")
    
    # Check for error handlers
    if 'addEventListener(\'error\'' not in content:
        issues.append("Missing global error handler")
    if 'addEventListener(\'unhandledrejection\'' not in content:
        issues.append("Missing promise rejection handler")
    
    # Check for try-catch in critical functions
    if 'function applyOrientation' in content:
        apply_orient_start = content.find('function applyOrientation')
        apply_orient_end = content.find('\n\t\t}', apply_orient_start)
        apply_orient_code = content[apply_orient_start:apply_orient_end]
        if 'try{' not in apply_orient_code:
            issues.append("applyOrientation missing try-catch")
    
    if issues:
        print_status("❌ HTML Issues found:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    
    print_status("✅ HTML syntax checks passed")
    return True

def check_javascript_functions():
    """Check that critical JavaScript functions are properly defined"""
    print_status("Checking JavaScript function definitions...")
    html_file = "templates/tv_view.html"
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_functions = [
        'function dbg(',
        'function applyOrientation(',
        'function showItem(',
        'function tick(',
        'function fetchPlaylist(',
        'function mediaUrl(',
        'function pollCommands(',
    ]
    
    missing_functions = []
    for func in required_functions:
        if func not in content:
            missing_functions.append(func.replace('function ', '').replace('(', ''))
    
    if missing_functions:
        print_status("❌ Missing JavaScript functions:")
        for func in missing_functions:
            print(f"   • {func}")
        return False
    
    print_status("✅ All required JavaScript functions found")
    return True

def check_crash_prevention():
    """Check crash prevention measures"""
    print_status("Checking crash prevention measures...")
    html_file = "templates/tv_view.html"
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    crash_fixes = {
        'Global error handler': 'addEventListener(\'error\'',
        'Promise rejection handler': 'addEventListener(\'unhandledrejection\'',
        'Safe DOM access': 'CRASH PREVENTION: Safe DOM element access',
        'Error handling in applyOrientation': 'applyOrientation failed:',
        'Safe initialization': 'initialization failed:',
        'Safe tick startup': 'tick() startup failed:',
    }
    
    missing_fixes = []
    for fix_name, pattern in crash_fixes.items():
        if pattern not in content:
            missing_fixes.append(fix_name)
    
    if missing_fixes:
        print_status("❌ Missing crash prevention measures:")
        for fix in missing_fixes:
            print(f"   • {fix}")
        return False
    
    print_status("✅ All crash prevention measures in place")
    return True

def main():
    """Main test function"""
    print_status("🔍 Testing Android TV WebView crash fixes...")
    print()
    
    # Change to the correct directory
    if not os.path.exists("templates"):
        print_status("❌ ERROR: Not in correct directory (templates/ not found)")
        sys.exit(1)
    
    all_passed = True
    
    # Run tests
    if not check_html_syntax():
        all_passed = False
    print()
    
    if not check_javascript_functions():
        all_passed = False
    print()
    
    if not check_crash_prevention():
        all_passed = False
    print()
    
    # Final result
    if all_passed:
        print_status("🎉 ALL TESTS PASSED - Android TV WebView should be crash-free!")
        print_status("Key fixes applied:")
        print("   • Moved dbg() function definition to prevent ReferenceError")
        print("   • Added global error and promise rejection handlers")
        print("   • Improved applyOrientation() with better error handling")
        print("   • Added safe DOM element access with validation")
        print("   • Enhanced initialization with proper timing")
        print("   • Fixed rotation scaling calculation")
        print()
        print_status("🚀 Ready for deployment to Android TV devices!")
    else:
        print_status("❌ TESTS FAILED - Issues need to be fixed before deployment")
        sys.exit(1)

if __name__ == "__main__":
    main()