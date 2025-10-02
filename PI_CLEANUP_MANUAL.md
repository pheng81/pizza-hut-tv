# 🧹 Manual Pi Cleanup Instructions

Since we can't connect automatically, here's how to clean the Pi manually:

## Step 1: Connect to Pi
```bash
# Try these connection methods:
ssh everydayadvertise@raspberrypi
# OR
ssh everydayadvertise@192.168.1.115
# OR find Pi IP and use that
```

## Step 2: Run These Commands on Pi
Copy and paste these commands one by one:

```bash
# Show current files
echo "Files before cleanup:"
ls -la | wc -l

# Stop all processes
pkill -f pizza || true
pkill -f phtv || true
pkill -f vlc || true
pkill -f client || true

# Delete all files (NUCLEAR OPTION)
cd /home/everydayadvertise
rm -rf *
rm -rf .*pizza* .*phtv* .*tv* .*client* 2>/dev/null || true

# Clean desktop
rm -rf Desktop/*.desktop 2>/dev/null || true

# Show remaining files
echo "Files after cleanup:"
ls -la
```

## Step 3: Verify Clean
You should see only basic system files like:
- `.bashrc`
- `.profile` 
- `.bash_logout`
- Maybe `.ssh/` directory

## Alternative: Complete Nuclear Option
If you want to delete EVERYTHING (be careful!):
```bash
cd /home/everydayadvertise
rm -rf * .*
ls -la  # Should show almost empty directory
```

## What This Removes:
- ✅ All Python clients (webplayer_style_pi_client.py, pizza_hut_tv_*.py, etc.)
- ✅ All shell scripts (.sh files)
- ✅ All logs, configs, json files
- ✅ All desktop shortcuts
- ✅ All media files (mp4, m3u, etc.)
- ✅ All directories (pizza-hut-tv, phtv, etc.)
- ✅ All running processes

## Result:
Pi will be completely clean and ready for fresh start! 🎉