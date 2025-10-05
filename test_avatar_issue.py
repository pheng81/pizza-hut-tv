"""
Test script to diagnose avatar upload issues
"""
import os
import sqlite3

# Check folder structure
UPLOAD_FOLDER = os.path.join('static', 'uploads')
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, 'avatars')

print("=" * 60)
print("AVATAR UPLOAD DIAGNOSTICS")
print("=" * 60)

# 1. Check if folders exist
print("\n1. FOLDER EXISTENCE:")
print(f"   Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
print(f"   Avatar folder exists: {os.path.exists(AVATAR_FOLDER)}")
print(f"   Upload folder path: {os.path.abspath(UPLOAD_FOLDER)}")
print(f"   Avatar folder path: {os.path.abspath(AVATAR_FOLDER)}")

# 2. Check folder permissions
print("\n2. FOLDER PERMISSIONS:")
try:
    print(f"   Upload folder writable: {os.access(UPLOAD_FOLDER, os.W_OK)}")
    print(f"   Avatar folder writable: {os.access(AVATAR_FOLDER, os.W_OK)}")
except Exception as e:
    print(f"   Error checking permissions: {e}")

# 3. List existing avatar files
print("\n3. EXISTING AVATAR FILES:")
try:
    if os.path.exists(AVATAR_FOLDER):
        files = os.listdir(AVATAR_FOLDER)
        if files:
            for f in files:
                full_path = os.path.join(AVATAR_FOLDER, f)
                size = os.path.getsize(full_path)
                print(f"   - {f} ({size} bytes)")
        else:
            print("   (No avatar files found)")
    else:
        print("   Avatar folder doesn't exist!")
except Exception as e:
    print(f"   Error listing files: {e}")

# 4. Check database for avatar entries
print("\n4. DATABASE AVATAR ENTRIES:")
try:
    db = sqlite3.connect('database.db')
    db.row_factory = sqlite3.Row
    cursor = db.execute("SELECT username, avatar FROM users WHERE avatar IS NOT NULL AND avatar != ''")
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"   - {row['username']}: {row['avatar']}")
            # Check if the file actually exists
            avatar_path = os.path.join('static', row['avatar']) if not row['avatar'].startswith('static') else row['avatar']
            file_exists = os.path.exists(avatar_path)
            print(f"     File exists: {file_exists}")
            if file_exists:
                size = os.path.getsize(avatar_path)
                print(f"     File size: {size} bytes")
    else:
        print("   (No avatar entries in database)")
    db.close()
except Exception as e:
    print(f"   Error checking database: {e}")

# 5. Check for PIL/Pillow
print("\n5. IMAGE PROCESSING LIBRARY:")
try:
    from PIL import Image, ImageOps
    print(f"   PIL/Pillow available: YES")
    print(f"   PIL version: {Image.__version__ if hasattr(Image, '__version__') else 'Unknown'}")
except ImportError as e:
    print(f"   PIL/Pillow available: NO - {e}")
    print("   ERROR: This is required for avatar uploads!")

# 6. Test write permissions
print("\n6. TEST WRITE PERMISSIONS:")
try:
    test_file = os.path.join(AVATAR_FOLDER, '_test_write.txt')
    with open(test_file, 'w') as f:
        f.write('test')
    print(f"   Can create file: YES")
    os.remove(test_file)
    print(f"   Can delete file: YES")
except Exception as e:
    print(f"   Write test FAILED: {e}")

print("\n" + "=" * 60)
print("POTENTIAL ISSUES TO CHECK:")
print("=" * 60)

issues = []

if not os.path.exists(AVATAR_FOLDER):
    issues.append("⚠️  Avatar folder doesn't exist - needs to be created")

if os.path.exists(AVATAR_FOLDER) and not os.access(AVATAR_FOLDER, os.W_OK):
    issues.append("⚠️  Avatar folder is not writable - check permissions")

try:
    from PIL import Image
except ImportError:
    issues.append("⚠️  PIL/Pillow not installed - avatar uploads will fail")

if not issues:
    print("✅ No obvious issues found")
    print("\nIf uploads still fail intermittently, check:")
    print("  1. Network issues during upload")
    print("  2. File size limits")
    print("  3. Browser console for JavaScript errors")
    print("  4. Server logs during failed uploads")
else:
    for issue in issues:
        print(issue)

print("\n")
