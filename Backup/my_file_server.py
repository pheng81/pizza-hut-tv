"""
YOUR OWN FILE SERVER
Run this on your PC to receive files from Pi, then you manually upload to server
No RealVNC, No WinSCP dependencies!
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import base64
import os

class FileReceiver(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/upload':
            # Read request body
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            filename = data['filename']
            content = base64.b64decode(data['content']).decode('utf-8')
            
            # Save to local directory
            output_dir = 'received_files'
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Received: {filename} ({len(content)} bytes)")
            print(f"   Saved to: {output_path}")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == '__main__':
    port = 8080
    server = HTTPServer(('0.0.0.0', port), FileReceiver)
    
    print("="*70)
    print("   📡 YOUR OWN FILE SERVER")
    print("="*70)
    print(f"\n✅ Server running on port {port}")
    print(f"✅ Listening on all network interfaces")
    print(f"✅ Ready to receive files from Pi")
    print("\nFiles will be saved to: received_files/")
    print("\nWaiting for Pi to send files...")
    print("(Press Ctrl+C to stop)\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")
        print("\nFiles received in: received_files/")
        print("Now manually upload these to server using WinSCP or other method")
