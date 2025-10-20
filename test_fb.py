#!/usr/bin/env python3
import fcntl
import struct

try:
    with open('/dev/fb0', 'rb') as fb:
        # Get framebuffer info
        FBIOGET_VSCREENINFO = 0x4600
        vinfo = fcntl.ioctl(fb, FBIOGET_VSCREENINFO, bytes(160))
        
        xres, yres, xres_virtual, yres_virtual = struct.unpack('IIII', vinfo[:16])
        bits_per_pixel = struct.unpack('I', vinfo[24:28])[0]
        
        print(f"✅ Framebuffer accessible!")
        print(f"Resolution: {xres}x{yres}")
        print(f"Virtual: {xres_virtual}x{yres_virtual}")
        print(f"Bits per pixel: {bits_per_pixel}")
        
        # Try to read some data
        fb.seek(0)
        data = fb.read(1024)
        print(f"Read {len(data)} bytes")
        print(f"First 32 bytes: {data[:32].hex()}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
