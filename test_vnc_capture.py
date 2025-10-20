#!/usr/bin/env python3
"""
Test VNC tunnel on Pi - manually trigger screen capture
"""
import sys
import os

# Set DISPLAY
os.environ['DISPLAY'] = ':0'

print("Testing VNC screen capture...")
print(f"DISPLAY={os.environ.get('DISPLAY')}")

try:
    import mss
    print("✅ mss library imported")
    
    with mss.mss() as sct:
        monitors = sct.monitors
        print(f"📺 Monitors found: {len(monitors)}")
        print(f"Primary monitor: {monitors[1]}")
        
        # Capture screenshot
        print("\n📸 Capturing screenshot...")
        screenshot = sct.grab(monitors[1])
        print(f"✅ Screenshot captured: {screenshot.size}")
        
        # Convert to PIL Image
        from PIL import Image
        import io
        import base64
        
        img = Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')
        print(f"✅ Converted to PIL Image: {img.size}")
        
        # Resize
        img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        print(f"✅ Resized to: {img.size}")
        
        # Compress to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=75, optimize=True)
        jpeg_bytes = buffer.getvalue()
        print(f"✅ JPEG compressed: {len(jpeg_bytes)} bytes")
        
        # Base64 encode
        frame_b64 = base64.b64encode(jpeg_bytes).decode('utf-8')
        print(f"✅ Base64 encoded: {len(frame_b64)} chars")
        
        print("\n🎉 VNC screen capture is working!")
        print(f"Frame size: {len(jpeg_bytes) / 1024:.1f} KB")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
