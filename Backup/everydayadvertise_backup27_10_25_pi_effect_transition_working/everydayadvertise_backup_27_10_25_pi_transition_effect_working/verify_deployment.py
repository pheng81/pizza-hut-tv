"""
Verify video fix deployment on production server
"""
import subprocess
import sys

SERVER = "54.252.90.27"
KEY_PATH = r"C:\Users\toeng\Downloads\LightsailDefaultKey-ap-southeast-2(3).pem"

def run_ssh_command(cmd):
    """Run SSH command on server"""
    full_cmd = f'ssh -i "{KEY_PATH}" ubuntu@{SERVER} "{cmd}"'
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode

def check_url(url):
    """Check if URL returns 200"""
    cmd = f"curl -s -o /dev/null -w '%{{http_code}}' {url}"
    output, _ = run_ssh_command(cmd)
    return output == "200"

print("=" * 70)
print("🔍 PRODUCTION SERVER VERIFICATION")
print("=" * 70)
print(f"Server: {SERVER}")
print()

# Check service status
print("📊 Service Status:")
print("-" * 70)
cmd = "sudo systemctl is-active pizza-hut-tv"
output, code = run_ssh_command(cmd)
if output == "active":
    print("✅ Service is running")
else:
    print(f"❌ Service is {output}")
    sys.exit(1)

# Check routes
print("\n🌐 Route Tests:")
print("-" * 70)
routes = {
    "Homepage": "http://localhost:5002/",
    "Video Test": "http://localhost:5002/video-test",
    "Health Check": "http://localhost:5002/healthz"
}

all_ok = True
for name, url in routes.items():
    if check_url(url):
        print(f"✅ {name:20s} - 200 OK")
    else:
        print(f"❌ {name:20s} - Failed")
        all_ok = False

# Check files exist
print("\n📁 Deployed Files:")
print("-" * 70)
files = [
    "/var/www/pizza-hut-tv/app.py",
    "/var/www/pizza-hut-tv/templates/home.html",
    "/var/www/pizza-hut-tv/templates/video_test.html",
    "/var/www/pizza-hut-tv/VIDEO_FIX_LOG.md"
]

for filepath in files:
    cmd = f"test -f {filepath} && echo 'exists' || echo 'missing'"
    output, _ = run_ssh_command(cmd)
    status = "✅" if output == "exists" else "❌"
    filename = filepath.split('/')[-1]
    print(f"{status} {filename}")

# Check for video-test route in code
print("\n🔍 Code Verification:")
print("-" * 70)
cmd = "grep -c '/video-test' /var/www/pizza-hut-tv/app.py"
output, _ = run_ssh_command(cmd)
if int(output) > 0:
    print("✅ video-test route found in app.py")
else:
    print("❌ video-test route NOT found in app.py")
    all_ok = False

# Check video files in static
print("\n🎬 Video Files on Server:")
print("-" * 70)
video_files = ['promotion5.mp4', 'promotion.mp4', 'sync-demo.mp4', 'dashboard.mp4']
cmd = "ls -lh /var/www/pizza-hut-tv/static/*.mp4 2>/dev/null | awk '{print $9, $5}'"
output, _ = run_ssh_command(cmd)

if output:
    for line in output.split('\n'):
        if line.strip():
            parts = line.split()
            filename = parts[0].split('/')[-1] if parts else 'unknown'
            size = parts[1] if len(parts) > 1 else 'N/A'
            print(f"✅ {filename:20s} - {size}")
else:
    print("❌ No video files found!")
    all_ok = False

print("\n" + "=" * 70)
if all_ok:
    print("✅ ALL CHECKS PASSED!")
    print("=" * 70)
    print("\n🎯 Test URLs:")
    print(f"   Homepage:   http://{SERVER}/")
    print(f"   Video Test: http://{SERVER}/video-test")
    print("\n💡 Open browser and check:")
    print("   1. Videos play automatically")
    print("   2. Browser console (F12) shows video logs")
    print("   3. Video test page shows all green checkmarks")
else:
    print("❌ SOME CHECKS FAILED!")
    print("=" * 70)
    print("Review errors above and redeploy if needed")
    sys.exit(1)
