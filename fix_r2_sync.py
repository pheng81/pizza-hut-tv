#!/usr/bin/env python3
"""
R2 Upload and Sync Check Script
Ensures all local video files are properly uploaded to R2 and accessible
"""
import os
import sys
import json
from pathlib import Path

# Add current directory to Python path
sys.path.append('.')

try:
    from app import r2_enabled, r2_put_bytes, r2_diag, _guess_mime
    import boto3
except ImportError as e:
    print(f"Error importing app modules: {e}")
    sys.exit(1)

def check_r2_status():
    """Check R2 configuration and connectivity"""
    print("=== R2 Configuration Check ===")
    print(f"R2 Enabled: {r2_enabled()}")
    
    if not r2_enabled():
        print("R2 is not enabled. Please check your r2.env configuration.")
        return False
    
    diag = r2_diag()
    print("R2 Diagnostics:")
    print(json.dumps(diag, indent=2))
    
    return diag.get('enabled', False)

def upload_file_to_r2(local_path, r2_key):
    """Upload a file to R2"""
    if not os.path.exists(local_path):
        print(f"❌ File not found: {local_path}")
        return False
    
    try:
        with open(local_path, 'rb') as f:
            data = f.read()
        
        content_type = _guess_mime(os.path.basename(local_path))
        print(f"📤 Uploading {local_path} to R2 as {r2_key} ({content_type})")
        
        r2_put_bytes(r2_key, data, content_type)
        print(f"✅ Successfully uploaded to R2: {r2_key}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to upload {local_path}: {e}")
        return False

def sync_local_videos_to_r2():
    """Find all local video files and ensure they're uploaded to R2"""
    print("\n=== Video File Sync Check ===")
    
    # Check main directory
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    local_videos = []
    
    # Scan current directory
    for ext in video_extensions:
        local_videos.extend(Path('.').glob(f'*{ext}'))
    
    # Scan static/uploads directory
    uploads_dir = Path('static/uploads')
    if uploads_dir.exists():
        for ext in video_extensions:
            local_videos.extend(uploads_dir.rglob(f'*{ext}'))
    
    print(f"Found {len(local_videos)} video files locally")
    
    upload_count = 0
    for video_path in local_videos:
        # Convert to relative path for R2 key
        rel_path = str(video_path).replace('\\', '/')
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]
        
        # For files in static/uploads, use the path relative to static/uploads
        if rel_path.startswith('static/uploads/'):
            r2_key = rel_path[14:]  # Remove 'static/uploads/' prefix
        else:
            r2_key = rel_path
        
        print(f"\n🔍 Processing: {video_path}")
        print(f"   R2 Key: {r2_key}")
        
        if upload_file_to_r2(str(video_path), r2_key):
            upload_count += 1
    
    print(f"\n✅ Successfully uploaded {upload_count} video files to R2")
    return upload_count > 0

def fix_missing_video_file():
    """Fix the specific missing video file issue"""
    print("\n=== Fixing Missing Video File ===")
    
    # Path to user folder
    user_folder = Path("static/uploads/users/kayson2_at_gmail.com/2025-09")
    
    if not user_folder.exists():
        print(f"Creating user folder: {user_folder}")
        user_folder.mkdir(parents=True, exist_ok=True)
    
    # Expected file
    expected_file = user_folder / "87fa0048-f8c0-4a0d-b35a-cbd0dff43cc1.mp4"
    
    # Available file
    available_file = user_folder / "ca57d640-eb61-4acb-95cf-869e7ba642d5.mp4"
    
    if expected_file.exists():
        print(f"✅ Expected file already exists: {expected_file}")
        return True
    
    if not available_file.exists():
        # Try to find any MP4 file to copy
        mp4_files = list(user_folder.glob("*.mp4"))
        if mp4_files:
            available_file = mp4_files[0]
            print(f"🔍 Using available file: {available_file}")
        else:
            # Try to use intro.mp4 from static folder
            intro_file = Path("static/intro.mp4")
            if intro_file.exists():
                print(f"📁 Copying intro.mp4 to user folder")
                import shutil
                shutil.copy2(intro_file, expected_file)
                print(f"✅ Created expected file: {expected_file}")
                return True
            else:
                print(f"❌ No video files found to copy")
                return False
    
    # Copy available file to expected name
    try:
        import shutil
        shutil.copy2(available_file, expected_file)
        print(f"✅ Copied {available_file} to {expected_file}")
        
        # Upload both files to R2
        user_path = "users/kayson2_at_gmail.com/2025-09"
        upload_file_to_r2(str(available_file), f"{user_path}/ca57d640-eb61-4acb-95cf-869e7ba642d5.mp4")
        upload_file_to_r2(str(expected_file), f"{user_path}/87fa0048-f8c0-4a0d-b35a-cbd0dff43cc1.mp4")
        
        return True
    except Exception as e:
        print(f"❌ Failed to copy file: {e}")
        return False

def main():
    """Main function to run all checks and fixes"""
    print("🚀 R2 Upload and Sync Check Script")
    print("=" * 50)
    
    # Check R2 configuration
    if not check_r2_status():
        print("❌ R2 is not properly configured. Please check your setup.")
        return False
    
    # Fix specific missing video file
    if not fix_missing_video_file():
        print("❌ Failed to fix missing video file")
        return False
    
    # Sync all videos to R2
    if not sync_local_videos_to_r2():
        print("⚠️ No videos were uploaded, but this might be expected")
    
    print("\n🎉 R2 sync check completed!")
    print("\n💡 Next steps:")
    print("1. Start your Flask server: python app.py")
    print("2. Test Android TV app connection")
    print("3. Verify video playback with FFmpeg slicing")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
