"""
Quick diagnostic script to verify video files and web server setup
"""
import os
import sys

print("=" * 60)
print("🎬 VIDEO PLAYBACK DIAGNOSTIC")
print("=" * 60)

# Check video files
static_dir = os.path.join(os.path.dirname(__file__), 'static')
video_files = {
    'promotion5.mp4': 'Hero video (background)',
    'promotion.mp4': 'Demo video #1',
    'sync-demo.mp4': 'Demo video #2',
    'dashboard.mp4': 'Dashboard demo'
}

print("\n📁 Video Files Status:")
print("-" * 60)
all_exist = True
for filename, description in video_files.items():
    filepath = os.path.join(static_dir, filename)
    exists = os.path.exists(filepath)
    size = os.path.getsize(filepath) if exists else 0
    status = "✅ EXISTS" if exists else "❌ MISSING"
    size_mb = size / (1024 * 1024)
    print(f"{status} | {filename:20s} | {size_mb:6.2f} MB | {description}")
    if not exists:
        all_exist = False

print()
if all_exist:
    print("✅ All video files present and accessible!")
else:
    print("❌ Some video files are missing!")
    sys.exit(1)

# Check Flask app
print("\n🌐 Flask Application:")
print("-" * 60)
try:
    import flask
    print(f"✅ Flask installed (version {flask.__version__})")
except ImportError:
    print("❌ Flask not installed!")
    sys.exit(1)

# Check templates
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
template_files = ['home.html', 'video_test.html']

print("\n📄 Template Files:")
print("-" * 60)
for template in template_files:
    filepath = os.path.join(templates_dir, template)
    exists = os.path.exists(filepath)
    status = "✅" if exists else "❌"
    print(f"{status} {template}")

# Test app.py has video-test route
print("\n🛣️  Routes Check:")
print("-" * 60)
app_file = os.path.join(os.path.dirname(__file__), 'app.py')
if os.path.exists(app_file):
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
        has_home = "@app.route('/')" in content
        has_video_test = "@app.route('/video-test')" in content
        
        print(f"{'✅' if has_home else '❌'} Home route ('/')")
        print(f"{'✅' if has_video_test else '❌'} Video test route ('/video-test')")

print("\n" + "=" * 60)
print("🎯 NEXT STEPS:")
print("=" * 60)
print("1. Start Flask: python app.py")
print("2. Open browser: http://localhost:5000")
print("3. Test videos: http://localhost:5000/video-test")
print("4. Check browser console (F12) for video logs")
print("=" * 60)
