# Screen Preview Feature Implementation

## Overview
Added live screen preview/mirror functionality to the Remote Pi Manager, allowing you to see what's displayed on the Pi screen directly in the dashboard without being physically present.

## Changes Made

### 1. Dashboard HTML (`templates/dashboard.html`)

#### Added Preview UI (after line 7212)
```html
<!-- Pi Screen Preview -->
<div id="piScreenPreview" style="display: none; padding: 0 18px; margin-bottom: 16px;">
    <div style="background: #f5f5f5; border-radius: 8px; padding: 12px; border: 1px solid #ddd;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <label style="font-weight: 500; margin: 0;">📺 Screen Preview</label>
            <button type="button" onclick="toggleScreenPreview()">
                <span id="previewToggleText">▶ Start</span>
            </button>
        </div>
        <div id="piScreenContainer" style="background: #000; border-radius: 6px; aspect-ratio: 16/9;">
            <img id="piScreenImage" src="" alt="Pi Screen" style="width: 100%; height: 100%; object-fit: contain;">
            <div id="piScreenPlaceholder">No preview - Click "Start" to view screen</div>
            <div id="piScreenLoading" style="display: none;">Loading...</div>
        </div>
        <div style="font-size: 11px; color: #666;">
            <span id="piScreenInfo">Ready</span>
            <span id="piScreenFps"></span>
        </div>
    </div>
</div>
```

#### Added JavaScript Functions (before line 7148 `</script>`)
- **`toggleScreenPreview()`** - Start/stop preview
- **`startScreenPreview()`** - Begin requesting screenshots every 2 seconds
- **`stopScreenPreview()`** - Stop preview and clear display
- **`requestScreenshot(piId)`** - Emit WebSocket event to request screenshot
- **Socket.IO listener `screenshot_data`** - Receive and display screenshots from Pi
- **Modified `connectToPi()`** - Show preview section when Pi connects successfully

### 2. Pi Client (`complete_pi_client.py`)

#### Added Screenshot Handler (after line 750)
```python
@self.sio.on('request_screenshot')
def on_request_screenshot(data):
    """Handle screenshot request from dashboard"""
    screenshot_base64 = self.capture_screenshot()
    
    if screenshot_base64:
        self.sio.emit('screenshot_data', {
            'pi_id': self.pi_id,
            'screenshot': screenshot_base64,
            'timestamp': time.time()
        })
    else:
        self.sio.emit('screenshot_data', {
            'pi_id': self.pi_id,
            'error': 'Failed to capture screenshot',
            'timestamp': time.time()
        })
```

#### Added Screenshot Capture Method (after line 837)
```python
def capture_screenshot(self) -> str:
    """Capture screenshot of current display and return as base64 JPEG"""
    # Try pygame screen capture first
    if hasattr(self, 'screen') and self.screen:
        screen_data = pygame.image.tostring(self.screen, 'RGB')
        size = self.screen.get_size()
        
        # Convert to PIL Image for JPEG compression
        from PIL import Image
        img = Image.frombytes('RGB', size, screen_data)
        
        # Resize for bandwidth (max 800px wide)
        if img.width > 800:
            ratio = 800 / img.width
            new_size = (800, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to JPEG quality=70
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=70)
        
        # Encode to base64
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    # Fallback to scrot system screenshot
    subprocess.run(['scrot', '-q', '70', '-z', tmp_path])
    # ... (resize and encode)
```

**Features:**
- Primary: Pygame screen capture (captures actual display buffer)
- Fallback: scrot system screenshot tool
- Automatic resizing to 800px max width for bandwidth efficiency
- JPEG compression at quality=70
- Base64 encoding for WebSocket transmission

### 3. Server (`app.py`)

#### Added Screenshot Relay Handlers (after line 9807)

**Request Relay:**
```python
@socketio.on('request_screenshot')
def handle_screenshot_request(data):
    """Dashboard requests screenshot from a Pi - relay to target Pi"""
    pi_id = data.get('pi_id')
    
    if pi_id and pi_id in connected_pis:
        pi_session = connected_pis[pi_id]['sid']
        socketio.emit('request_screenshot', data, room=pi_session)
    else:
        emit('screenshot_data', {
            'pi_id': pi_id,
            'error': 'Pi not connected'
        })
```

**Response Relay:**
```python
@socketio.on('screenshot_data')
def handle_screenshot_data(data):
    """Pi sends screenshot back - broadcast to all dashboards"""
    pi_id = data.get('pi_id')
    socketio.emit('screenshot_data', data, broadcast=True)
```

## How It Works

### Flow Diagram
```
Dashboard                Server                    Pi
   |                       |                        |
   |--- request_screenshot -->|                     |
   |    {pi_id: "xyz"}     |                        |
   |                       |--- request_screenshot -->|
   |                       |                        |
   |                       |                   [Capture]
   |                       |                   [Pygame]
   |                       |                   [Resize]
   |                       |                   [JPEG]
   |                       |                   [Base64]
   |                       |                        |
   |                       |<-- screenshot_data ----|
   |<-- screenshot_data ---|    {screenshot: "..."} |
   |                       |                        |
  [Display]                |                        |
```

### Update Cycle
1. User clicks "▶ Start" button in preview section
2. Dashboard sends `request_screenshot` every 2 seconds
3. Server relays request to target Pi
4. Pi captures pygame screen or falls back to scrot
5. Pi resizes to 800px max width
6. Pi compresses to JPEG quality=70
7. Pi encodes to base64 string
8. Pi sends `screenshot_data` back to server
9. Server broadcasts to all dashboard sessions
10. Dashboard receives and displays: `<img src="data:image/jpeg;base64,...">`

### Performance Optimizations
- **2-second update interval** - Balance between responsiveness and bandwidth
- **800px max width** - Reduces data by ~4x for 2560px displays
- **JPEG quality 70** - Good quality vs file size balance
- **Base64 encoding** - Direct display in HTML without file handling
- **Async capture** - Non-blocking screenshot capture
- **Frame counter** - Shows FPS and frame count for monitoring

## User Interface

### Preview Controls
- **▶ Start** - Begin live preview (changes to ⏸ Stop)
- **⏸ Stop** - Stop preview and clear display
- **Status line** - Shows: "Live preview • Frame X" or "Preview stopped"
- **FPS counter** - Shows actual frame rate (e.g., "0.5 fps" for 2-second intervals)

### Visual States
1. **Not Started** - Black box with "No preview - Click Start to view screen"
2. **Loading** - "Loading..." displayed while waiting for first frame
3. **Active** - Live screenshot displayed with frame counter and FPS
4. **Error** - Error message displayed if Pi not connected or capture fails

## Requirements

### Pi Dependencies
- **Pillow (PIL)** - For image processing and JPEG compression
  ```bash
  pip install Pillow
  ```
- **scrot** - System screenshot tool (fallback method)
  ```bash
  sudo apt-get install scrot
  ```

### Bandwidth Estimate
- **800px width screenshot** at JPEG quality 70
- Estimated size: 50-150 KB per frame
- At 0.5 fps (2-second interval): 25-75 KB/s
- Per minute: 1.5-4.5 MB
- Per hour: 90-270 MB

## Deployment Steps

### 1. Deploy to Server
```bash
# Upload files
scp app.py ubuntu@everydayadvertise.com:~/Pizza-Hut-TV/
scp templates/dashboard.html ubuntu@everydayadvertise.com:~/Pizza-Hut-TV/templates/

# Restart Flask
ssh ubuntu@everydayadvertise.com
sudo systemctl restart pizza-hut-tv
```

### 2. Deploy to Pi
```bash
# Upload file
scp complete_pi_client.py everydayadvertise@raspberrypi:~/

# Install Pillow if not present
ssh everydayadvertise@raspberrypi
cd ~/pizza-hut-tv
source bin/activate
pip install Pillow

# Install scrot
sudo apt-get update
sudo apt-get install -y scrot

# Restart client
pkill -f complete_pi_client.py
nohup ~/pizza-hut-tv/bin/python ~/complete_pi_client.py > /tmp/pi_test.log 2>&1 &
```

### 3. Test Preview
1. Open dashboard at https://everydayadvertise.com/dashboard
2. Go to Remote Pi Manager section
3. Enter Pi identifier (e.g., raspberrypi-ce39)
4. Click "Connect" - should show "✅ Pi Online"
5. Preview section should appear below connection status
6. Click "▶ Start" to begin preview
7. Should see live screenshots updating every 2 seconds

## Troubleshooting

### Preview Shows "Pi not connected"
- Check Pi is actually connected in Remote Pi Manager
- Verify WebSocket connection: look for green online status
- Check Pi logs: `tail -f /tmp/pi_test.log | grep screenshot`

### No Screenshot Received
- Check Pi has Pillow: `pip list | grep -i pillow`
- Check scrot installed: `which scrot`
- Check pygame screen initialized: Look for "Pygame display error" in logs
- Try scrot manually: `scrot /tmp/test.jpg` then check if file created

### Preview Very Slow
- Check network bandwidth between Pi and server
- Increase update interval from 2 to 5 seconds in dashboard.html line ~7185
- Reduce screenshot quality in complete_pi_client.py from 70 to 50
- Reduce max width from 800 to 640

### Black Screen Preview
- This shows what Pi actually displays - if Pi screen is black due to GL context errors, preview will also be black
- Screenshot captures current display buffer, including black screens
- Fix underlying display issue to see content in preview

## Future Enhancements

### Possible Improvements
1. **Click to view full resolution** - Modal popup with full-size screenshot
2. **Configurable update rate** - Slider to adjust 0.5-5 seconds
3. **Record screen** - Save screenshots to file or create video
4. **Multiple Pi preview grid** - View all connected Pis at once
5. **H.264 video streaming** - Real-time video instead of screenshots for smoother preview
6. **Bandwidth indicator** - Show current data usage
7. **Quality presets** - Low/Medium/High quality buttons
8. **Touch interaction** - Click on preview to send commands to Pi

## Notes

- Preview shows ACTUAL Pi display including any black screens or errors
- Screenshot capture happens on Pi side, not server side
- WebSocket broadcast means multiple dashboard users see same screenshots
- Preview automatically stops when Pi disconnects
- No authentication on screenshots - same security as rest of dashboard
- Base64 encoding increases data size by ~33% vs raw JPEG
- pygame capture is preferred (accurate) vs scrot (may include desktop artifacts)

## Related Issues

### Close Screen Handler
Also modified `close_screen` handler in `complete_pi_client.py` (line 691-730) to:
- Clear saved config file
- Reset variables to None
- Set `setup_step = None` (no input boxes shown)
- Show only Pi ID in clean state

**Status:** Code modified, awaiting deployment to Pi

### GL Context Display Issue
Preview will show whatever Pi displays, including black screens caused by:
- pygame.display.flip() BadAccess errors
- transition_engine GL context failures
- See logs for: "Could not make GL context current: BadAccess"

**Status:** Ongoing issue, not fixed by preview feature
