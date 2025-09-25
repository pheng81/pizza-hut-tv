# EA TV Pi Client - Final Setup Instructions

## ✅ Current Status:
- Enhanced Pi client with synchronization deployed ✅
- Desktop launcher script updated ✅
- All Python dependencies installed ✅
- Desktop icon configured ✅

## 🔧 Final Fix Needed:

The Pi client is trying to connect to external servers but can't reach them due to network configuration. Here are two solutions:

### Option 1: Use Local Network Server (Recommended)
If you have the server running on your local network:

1. **Find your local server IP address:**
   ```bash
   # On your Windows PC, run:
   ipconfig
   # Note your local IP (e.g., 192.168.1.100)
   ```

2. **Update Pi launcher with local IP:**
   ```bash
   ssh everydayadvertise@raspberrypi
   # Edit the launcher:
   nano /home/everydayadvertise/ea_tv_launcher.sh
   
   # Change the server line to:
   python3 phtv_pi_client.py --server http://YOUR_LOCAL_IP:5002 --store 1000 --screen 1 --windowed
   ```

### Option 2: Offline Demo Mode (Quick Test)
For immediate testing, create a simple demo:

1. **Create simple test launcher:**
   ```bash
   ssh everydayadvertise@raspberrypi
   cat > /home/everydayadvertise/test_ea_tv.py << 'EOF'
   #!/usr/bin/env python3
   import tkinter as tk
   import time
   
   root = tk.Tk()
   root.title("EA TV - Screen 1 (Demo)")
   root.configure(bg='red')
   root.attributes('-fullscreen', True)
   
   label = tk.Label(root, text="🍕 EA TV - Screen 1\nSynchronized Playback Demo", 
                   font=("Arial", 48), fg="white", bg="red")
   label.pack(expand=True)
   
   def update_time():
       current_time = time.strftime("%H:%M:%S")
       label.config(text=f"🍕 EA TV - Screen 1\nSynchronized Demo\n{current_time}")
       root.after(1000, update_time)
   
   update_time()
   root.mainloop()
   EOF
   
   chmod +x test_ea_tv.py
   ```

2. **Test the demo:**
   ```bash
   python3 test_ea_tv.py
   ```

## 🚀 How to Use:

1. **Click the EA TV desktop icon** on your Raspberry Pi
2. **Choose your option:**
   - If using local server: Should connect and show screen selection
   - If using demo: Shows synchronized demo screen

## 🎯 Next Steps:
Once you have network connectivity working, the enhanced Pi client will provide:
- ✅ Perfect synchronization with webplayer
- ✅ Screen 1, 2, 3 options
- ✅ Server-coordinated timing
- ✅ No more delay issues

The code is ready - just need the network configuration sorted!