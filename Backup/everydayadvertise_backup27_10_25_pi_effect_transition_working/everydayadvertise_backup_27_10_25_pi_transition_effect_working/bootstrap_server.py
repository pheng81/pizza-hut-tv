#!/usr/bin/env python3
"""
BOOTSTRAP SERVER - Temporary file server on Pi
The server will download files from THIS Pi via HTTP
"""
import http.server
import socketserver
import os

# Change to temp directory where files are
os.chdir('/tmp')

PORT = 8765

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        print(f"📥 Request: {self.path}")
        return super().do_GET()

print("="*70)
print("   📡 BOOTSTRAP FILE SERVER")
print("="*70)
print()
print(f"🌐 Server running on: http://192.168.1.131:{PORT}")
print()
print("Available files:")
print("  - /new_app.py")
print("  - /new_dashboard.html")
print()
print("Server will download these files and bootstrap itself!")
print()
print("Press Ctrl+C to stop")
print("="*70)
print()

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")
