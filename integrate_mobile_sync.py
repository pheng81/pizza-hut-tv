#!/usr/bin/env python3
"""
🔧 Integration Script - Add Mobile Sync to Complete Pi Client
Automatically integrates pi_mobile_sync_addon.py into complete_pi_client.py
WITHOUT breaking existing functionality
"""

import sys

def integrate_mobile_sync():
    """Add mobile sync functionality to complete_pi_client.py"""
    
    print("🔧 Integrating Mobile Sync Add-on...")
    print("=" * 60)
    
    # Read the original file
    with open('complete_pi_client.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    new_lines = []
    
    # Track what we've added
    added_import = False
    added_init = False
    added_websocket_setup = False
    added_code_qr = False
    added_store_qr = False
    added_screen_qr = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # 1. Add import after other imports (after socketio import)
        if not added_import and 'import socketio' in line:
            new_lines.append('from pi_mobile_sync_addon import MobileSyncAddon  # MOBILE SYNC ADDON\n')
            added_import = True
            modified = True
            print("✅ Added import statement")
        
        # 2. Add mobile_sync initialization in __init__ (after self.sio setup)
        if not added_init and 'self.setup_websocket()' in line:
            new_lines.append('        \n')
            new_lines.append('        # MOBILE SYNC ADDON: Initialize mobile sync functionality\n')
            new_lines.append('        self.mobile_sync = MobileSyncAddon(self)\n')
            new_lines.append('        logger.info("📱 Mobile sync addon integrated")\n')
            added_init = True
            modified = True
            print("✅ Added mobile_sync initialization")
        
        # 3. Register WebSocket handlers (after self.sio.emit('heartbeat'))
        if not added_websocket_setup and "self.sio.emit('heartbeat'" in line:
            # Look ahead to find the end of setup_websocket method
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('def '):
                new_lines.append(lines[j])
                j += 1
            
            # Add mobile sync handler registration before next method
            new_lines.append('\n')
            new_lines.append('        # MOBILE SYNC ADDON: Register mobile sync WebSocket handlers\n')
            new_lines.append('        if hasattr(self, "mobile_sync"):\n')
            new_lines.append('            self.mobile_sync.setup_websocket_handlers(self.sio)\n')
            new_lines.append('            logger.info("📱 Mobile sync WebSocket handlers registered")\n')
            
            # Skip to where we are now
            i = j - 1
            added_websocket_setup = True
            modified = True
            print("✅ Added WebSocket handler registration")
        
        # 4. Add QR code to draw_code_input_screen (at the end of method)
        if not added_code_qr and 'def draw_code_input_screen(' in line:
            # Find the end of this method (next 'def ' or significant dedent)
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Look for next method definition at same indent level
                if next_line.strip().startswith('def ') and not next_line.startswith('        '):
                    break
                j += 1
            
            # Insert QR code drawing before the next method
            insertion_point = j
            for k in range(i + 1, j):
                new_lines.append(lines[k])
            
            new_lines.append('\n')
            new_lines.append('        # MOBILE SYNC ADDON: Draw QR code for mobile input\n')
            new_lines.append('        if hasattr(self, "mobile_sync"):\n')
            new_lines.append('            self.mobile_sync.draw_qr_code(self.screen, "code")\n')
            
            i = insertion_point - 1
            added_code_qr = True
            modified = True
            print("✅ Added QR code to code input screen")
        
        # 5. Add QR code to draw_store_selection_screen
        if not added_store_qr and 'def draw_store_selection_screen(' in line:
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip().startswith('def ') and not next_line.startswith('        '):
                    break
                j += 1
            
            insertion_point = j
            for k in range(i + 1, j):
                new_lines.append(lines[k])
            
            new_lines.append('\n')
            new_lines.append('        # MOBILE SYNC ADDON: Draw QR code for mobile store input\n')
            new_lines.append('        if hasattr(self, "mobile_sync"):\n')
            new_lines.append('            self.mobile_sync.draw_qr_code(self.screen, "store")\n')
            
            i = insertion_point - 1
            added_store_qr = True
            modified = True
            print("✅ Added QR code to store selection screen")
        
        # 6. Add QR code to draw_screen_selection_screen
        if not added_screen_qr and 'def draw_screen_selection_screen(' in line:
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip().startswith('def ') and not next_line.startswith('        '):
                    break
                j += 1
            
            insertion_point = j
            for k in range(i + 1, j):
                new_lines.append(lines[k])
            
            new_lines.append('\n')
            new_lines.append('        # MOBILE SYNC ADDON: Draw QR code for mobile screen selection\n')
            new_lines.append('        if hasattr(self, "mobile_sync"):\n')
            new_lines.append('            self.mobile_sync.draw_qr_code(self.screen, "screen")\n')
            
            i = insertion_point - 1
            added_screen_qr = True
            modified = True
            print("✅ Added QR code to screen selection screen")
        
        i += 1
    
    if modified:
        # Create backup
        with open('complete_pi_client.py.backup', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("\n💾 Backup saved as: complete_pi_client.py.backup")
        
        # Write modified file
        with open('complete_pi_client_with_mobile_sync.py', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print("=" * 60)
        print("✅ SUCCESS! Mobile sync integrated!")
        print("=" * 60)
        print("\n📝 Integration Summary:")
        print(f"   ✓ Import added: {added_import}")
        print(f"   ✓ Initialization added: {added_init}")
        print(f"   ✓ WebSocket setup added: {added_websocket_setup}")
        print(f"   ✓ Code screen QR added: {added_code_qr}")
        print(f"   ✓ Store screen QR added: {added_store_qr}")
        print(f"   ✓ Screen selection QR added: {added_screen_qr}")
        print("\n📁 New file created: complete_pi_client_with_mobile_sync.py")
        print("📁 Original backed up: complete_pi_client.py.backup")
        print("\n🚀 Next Steps:")
        print("   1. Copy pi_mobile_sync_addon.py to Pi")
        print("   2. Copy complete_pi_client_with_mobile_sync.py to Pi")
        print("   3. Install qrcode: pip3 install qrcode[pil]")
        print("   4. Test on Pi!")
    else:
        print("⚠️  No modifications needed or integration already exists")
    
    return modified

if __name__ == "__main__":
    try:
        integrate_mobile_sync()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
