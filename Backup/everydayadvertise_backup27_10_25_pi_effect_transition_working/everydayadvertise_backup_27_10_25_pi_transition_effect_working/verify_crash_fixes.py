#!/usr/bin/env python3
"""
Verify Android TV crash fixes are properly implemented
"""

import os
import time

def check_crash_fixes():
    """Check for specific crash prevention measures"""
    print(f"[{time.strftime('%H:%M:%S')}] 🔧 Verifying crash fixes...")
    
    html_file = "templates/tv_view.html"
    if not os.path.exists(html_file):
        print(f"❌ ERROR: {html_file} not found")
        return False
    
    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for critical crash fixes
    crash_fixes = {
        '🚫 Removed GPU-intensive backface-visibility': 'backface-visibility:hidden' not in content.replace('/* REMOVED:', '').replace('*/', ''),
        '🚫 Removed GPU-intensive transform-style': 'transform-style:preserve-3d' not in content.replace('/* REMOVED:', '').replace('*/', ''),
        '🚫 Removed GPU-intensive will-change': 'will-change: transform, opacity' not in content.replace('/* REMOVED:', '').replace('*/', ''),
        '✅ Added memory cleanup interval': 'setInterval' in content and 'gc()' in content,
        '✅ Safer video preload setting': 'v.preload = \'metadata\'' in content,
        '✅ Reduced video timeout': '}, 5000); // Reduced from 8000ms' in content,
        '✅ Image size limits': 'img.style.maxWidth = \'100vw\'' in content,
        '✅ Video size limits': 'v.style.maxWidth = \'100vw\'' in content,
        '✅ Disabled automatic rotation testing': '// CRASH FIX: Disable automatic rotation testing' in content,
        '✅ Simplified rotation approach': 'stage.style.transform = \'rotate(90deg)\'' in content,
        '✅ Resource cleanup on errors': 'v.removeAttribute(\'src\'); v.load()' in content,
    }
    
    print()
    all_good = True
    for fix_name, is_applied in crash_fixes.items():
        status = "✅" if is_applied else "❌"
        print(f"  {status} {fix_name}")
        if not is_applied:
            all_good = False
    
    print()
    if all_good:
        print(f"[{time.strftime('%H:%M:%S')}] 🎉 ALL CRASH FIXES VERIFIED!")
        print("   The app should now be stable on Android TV")
        print()
        print("📱 Ready to test:")
        print("   http://your-server/tv_view.html?debug=1")
        print()
        print("🔍 Watch for:")
        print("   • No renderer crashes in logcat")
        print("   • 'MEMORY CLEANUP' messages every 30s") 
        print("   • 'INIT: Initial orientation applied successfully'")
        print("   • Stable video playback without crashes")
        return True
    else:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ SOME FIXES MISSING")
        print("   Please check the implementation")
        return False

if __name__ == "__main__":
    success = check_crash_fixes()
    if not success:
        exit(1)