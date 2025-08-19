from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
import uuid
import json
import shutil

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

print("DEBUG: Flask app initialized")

# Commented out for testing - might be causing issues
# @app.before_request  
# def before_request():
#     print(f"DEBUG: Request received: {request.method} {request.path}")

# Configure upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'mp4', 'webm', 'ogg', 'mov', 'avi'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size for videos

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Store configuration file
CONFIG_FILE = 'store_config.json'

def load_store_config():
    """Load store configuration from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read().strip()
                if not content:
                    print(f"Warning: {CONFIG_FILE} is empty, creating default config")
                    return get_default_config()
                config = json.loads(content)
                
                # Migrate old screen IDs to store-specific format
                config = migrate_screen_ids(config)
                return config
        else:
            print(f"Warning: {CONFIG_FILE} not found, creating default config")
            return get_default_config()
    except json.JSONDecodeError as e:
        print(f"JSON Error in {CONFIG_FILE}: {e}")
        print("Creating backup and using default config")
        # Create backup of corrupted file
        if os.path.exists(CONFIG_FILE):
            backup_name = f"{CONFIG_FILE}.backup"
            import shutil
            shutil.copy(CONFIG_FILE, backup_name)
            print(f"Corrupted file backed up as {backup_name}")
        return get_default_config()
    except Exception as e:
        print(f"Error loading config: {e}")
        return get_default_config()

def migrate_screen_ids(config):
    """Migrate old screen IDs to store-specific format"""
    migrated = False
    
    for store_id in config.get('screens', {}):
        store_screens = config['screens'][store_id]
        screens_to_migrate = {}
        
        for screen_id, screen_data in list(store_screens.items()):
            # Check if screen_id already has store prefix
            if not screen_id.startswith(f"{store_id}_"):
                # Need to migrate this screen
                new_screen_id = f"{store_id}_{screen_id}"
                screens_to_migrate[screen_id] = new_screen_id
                migrated = True
        
        # Apply migrations
        for old_id, new_id in screens_to_migrate.items():
            config['screens'][store_id][new_id] = config['screens'][store_id][old_id]
            del config['screens'][store_id][old_id]
            print(f"Migrated screen ID: {old_id} -> {new_id} in store {store_id}")
    
    # Save migrated config
    if migrated:
        save_store_config(config)
        print("Screen ID migration completed and saved")
    
    return config

def get_default_config():
    """Get default store configuration"""
    return {
        'stores': [
            {'id': '1881', 'name': 'Canley Vale'}
        ],
        'screens': {
            '1881': {
                'screen1': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0},
                'screen2': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0},
                'screen3': {'file': None, 'vertical': True, 'horizontal': True, 'rotation': 0},
                'promo1': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0},
                'promo2': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0},
                'promo3': {'file': None, 'vertical': True, 'horizontal': False, 'rotation': 0}
            }
        }
    }

def save_store_config(config):
    """Save store configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"Configuration saved successfully to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving configuration: {e}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def dashboard():
    """Main dashboard page"""
    print("DEBUG: Dashboard route called")
    try:
        print("DEBUG: Loading store config...")
        config = load_store_config()
        print("DEBUG: Config loaded successfully")
        print(f"DEBUG: Config has {len(config.get('stores', []))} stores")
        print("DEBUG: Rendering template...")
        return render_template('dashboard.html', config=config)
    except Exception as e:
        print(f"DEBUG: Error in dashboard route: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {e}", 500

@app.route('/upload_to_screen', methods=['POST'])
def upload_to_screen():
    """Upload file to specific screen"""
    store_id = request.form.get('store_id')
    screen_id = request.form.get('screen_id')
    apply_to_all = request.form.get('apply_to_all', '').lower() == 'true'
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Update configuration
        config = load_store_config()
        
        if apply_to_all:
            # Check if the current store is the master store
            master_store_id = config.get('master_store_id')
            if store_id != master_store_id:
                return jsonify({
                    'error': 'Only the Master Store can use "Apply to All Stores" functionality'
                }), 403

            # Normalize screen id: ensure we propagate the "type" portion only
            # so if master store uses "0000_screen1" we extract "screen1" as the screen_type
            original_screen_id = screen_id
            if '_' in screen_id:
                # assume format <store>_<rest>
                screen_type = screen_id.split('_', 1)[1]
            else:
                screen_type = screen_id  # legacy already just type
            print(f"DEBUG: Apply-to-all normalization: original={original_screen_id} -> screen_type={screen_type}")
            print(f"DEBUG: Stores to iterate: {list(config['screens'].keys())}")
            
            # Apply to all stores, create missing screens if needed
            updated_stores = []
            skipped_stores = []
            created_screens = []
            print(f"DEBUG: Apply to all - checking stores for screen_id: {screen_id}")
            print(f"DEBUG: Available stores in config: {list(config['screens'].keys())}")
            
            for current_store_id in config['screens']:
                print(f"DEBUG: Checking store {current_store_id}")
                print(f"DEBUG: Available screens in store {current_store_id}: {list(config['screens'][current_store_id].keys())}")
                
                # Create screen if it doesn't exist - use store-specific ID
                # For each store, compute its store-specific screen id
                target_screen_id = f"{current_store_id}_{screen_type}"

                if target_screen_id not in config['screens'][current_store_id]:
                    new_screen_id = target_screen_id
                    
                    # Determine default orientation based on screen type
                    is_promo = screen_type.startswith('promo')
                    config['screens'][current_store_id][target_screen_id] = {
                        'file': None,
                        'vertical': is_promo,  # Promos default to vertical
                        'horizontal': not is_promo,  # Regular screens default to horizontal
                        'rotation': 0,
                        'protected': False
                    }
                    created_screens.append(f"{current_store_id}:{target_screen_id}")
                    print(f"DEBUG: Created missing screen {target_screen_id} in store {current_store_id}")
                actual_screen_id = target_screen_id
                
                # Check if this screen is protected
                is_protected = config['screens'][current_store_id][actual_screen_id].get('protected', False)
                print(f"DEBUG: Screen {actual_screen_id} in store {current_store_id} - protected: {is_protected}")
                
                if is_protected:
                    skipped_stores.append(current_store_id)
                    print(f"DEBUG: Skipped protected screen in store {current_store_id}")
                else:
                    config['screens'][current_store_id][actual_screen_id]['file'] = filename
                    updated_stores.append(current_store_id)
                    print(f"DEBUG: Updated screen {actual_screen_id} in store {current_store_id} with file {filename}")
            
            print(f"DEBUG: Updated stores: {updated_stores}")
            print(f"DEBUG: Skipped stores: {skipped_stores}")
            print(f"DEBUG: Created screens: {created_screens}")
            
            save_store_config(config)
            
            message = f'File applied to {screen_type} in {len(updated_stores)} stores'
            if created_screens:
                message += f'. Created {len(created_screens)} missing screens'
            if skipped_stores:
                store_names = []
                for skip_id in skipped_stores:
                    store_name = next((s['name'] for s in config['stores'] if s['id'] == skip_id), skip_id)
                    store_names.append(store_name)
                message += f'. Skipped {len(skipped_stores)} protected stores: {", ".join(store_names)}'
            
            return jsonify({
                'success': True, 
                'filename': filename,
                'applied_to_all': True,
                'updated_stores': updated_stores,
                'skipped_stores': skipped_stores,
                'created_screens': created_screens,
                'message': message
            })
        else:
            # Apply to single store only
            if store_id in config['screens'] and screen_id in config['screens'][store_id]:
                config['screens'][store_id][screen_id]['file'] = filename
                save_store_config(config)
                return jsonify({'success': True, 'filename': filename, 'applied_to_all': False})
        
        return jsonify({'error': 'Store or screen not found'}), 404
    else:
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/update_rotation', methods=['POST'])
def update_rotation():
    """Update rotation setting for a screen"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        rotation = data.get('rotation', 0)
        
        if not store_id or not screen_id:
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400
            
        config = load_store_config()
        
        if store_id not in config['screens'] or screen_id not in config['screens'][store_id]:
            return jsonify({'error': 'Screen not found'}), 404
        
        # Update rotation (0, 90, 180, 270 degrees)
        config['screens'][store_id][screen_id]['rotation'] = rotation
        save_store_config(config)
        
        return jsonify({'success': True, 'rotation': rotation})
        
    except Exception as e:
        print(f"Error updating rotation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/update_orientation', methods=['POST'])
def update_orientation():
    """Update screen orientation settings"""
    data = request.get_json()
    store_id = data.get('store_id')
    screen_id = data.get('screen_id')
    orientation = data.get('orientation')
    value = data.get('value')
    
    config = load_store_config()
    if store_id in config['screens'] and screen_id in config['screens'][store_id]:
        config['screens'][store_id][screen_id][orientation] = value
        save_store_config(config)
        return jsonify({'success': True})
    
    return jsonify({'error': 'Invalid screen'}), 400

@app.route('/update_protection', methods=['POST'])
def update_protection():
    """Update screen protection status"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        protected = data.get('protected', False)
        
        if not store_id or not screen_id:
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400
            
        config = load_store_config()
        if store_id in config['screens'] and screen_id in config['screens'][store_id]:
            config['screens'][store_id][screen_id]['protected'] = protected
            save_store_config(config)
            return jsonify({'success': True, 'protected': protected})
        
        return jsonify({'error': 'Store or screen not found'}), 404
        
    except Exception as e:
        print(f"Error updating protection: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tv_view/<store_id>/<screen_id>')
def tv_view(store_id, screen_id):
    """TV display view for specific screen"""
    config = load_store_config()
    screen_config = config['screens'].get(store_id, {}).get(screen_id, {})
    return render_template('tv_view.html', screen_config=screen_config, screen_id=screen_id)

@app.route('/delete_from_screen', methods=['POST'])
def delete_from_screen():
    """Delete file from specific screen or force delete from gallery"""
    try:
        data = request.get_json()
        print(f"Delete request received: {data}")
        
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        filename = data.get('filename')
        force_delete = data.get('force_delete', False)
        
        config = load_store_config()
        print(f"Current config loaded successfully")

        # Basic validation
        if not force_delete and (not store_id or not screen_id):
            return jsonify({'error': 'store_id and screen_id are required'}), 400
        
        # Fallback: allow legacy (un-prefixed) screen IDs by auto-expanding
        if (not force_delete and store_id in config.get('screens', {}) and
            screen_id not in config['screens'][store_id]):
            legacy_candidate = f"{store_id}_{screen_id}"  # try store-specific form
            if legacy_candidate in config['screens'][store_id]:
                print(f"Mapped legacy screen_id '{screen_id}' -> '{legacy_candidate}'")
                screen_id = legacy_candidate
        
        # Handle force delete from gallery (delete file completely)
        if force_delete and filename:
            print(f"Processing force delete for filename: {filename}")
            try:
                # Remove file from filesystem
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Force deleted file: {filepath}")
                
                # Remove file from all screens that use it
                for sid, screens in config['screens'].items():
                    for scr_id, screen_data in screens.items():
                        if screen_data.get('file') == filename:
                            config['screens'][sid][scr_id]['file'] = None
                            print(f"Removed {filename} from store {sid}, screen {scr_id}")
                
                save_store_config(config)
                return jsonify({'success': True, 'message': 'File deleted successfully from all screens'})
                
            except Exception as e:
                print(f"Error force deleting file: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        
        # Handle regular delete from specific screen
        print(f"Processing screen delete for store_id: {store_id}, screen_id: {screen_id}")
        if (not force_delete and store_id in config.get('screens', {}) and
                screen_id in config['screens'][store_id]):
            current_filename = config['screens'][store_id][screen_id].get('file')
            print(f"Current filename for {store_id}/{screen_id}: {current_filename}")

            if not current_filename:
                print(f"No file attached to {store_id}/{screen_id}")
                return jsonify({'error': 'No file to delete', 'screen_id': screen_id}), 400

            try:
                # Determine if other screens still reference this file
                still_in_use = False
                for other_store_id, screens in config.get('screens', {}).items():
                    for other_screen_id, sdata in screens.items():
                        if (other_store_id, other_screen_id) != (store_id, screen_id) and sdata.get('file') == current_filename:
                            still_in_use = True
                            break
                    if still_in_use:
                        break
                print(f"Reference check - file '{current_filename}' still_in_use={still_in_use}")

                # Only remove the physical file if no other screen uses it
                if not still_in_use:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"Deleted physical file: {filepath}")
                    else:
                        print(f"Physical file already missing: {filepath}")
                else:
                    print(f"Skipping physical delete; file shared by other screens")

                # Update configuration for this screen
                config['screens'][store_id][screen_id]['file'] = None
                save_store_config(config)

                return jsonify({
                    'success': True,
                    'message': 'File removed from screen',
                    'file_was_shared': still_in_use,
                    'file_deleted': not still_in_use
                })
            except Exception as e:
                print(f"Error during delete operation: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        
        print(f"Invalid parameters - store_id: {store_id}, screen_id: {screen_id}")
        print(f"Available stores: {list(config['screens'].keys())}")
        if store_id in config['screens']:
            print(f"Available screens for {store_id}: {list(config['screens'][store_id].keys())}")
        
        return jsonify({'error': 'Invalid parameters or screen not found'}), 400
        
    except Exception as e:
        print(f"Unexpected error in delete_from_screen: {e}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/apply_to_all', methods=['POST'])
def apply_to_all():
    """Apply settings to all stores"""
    # This would implement the "Apply to all Stores" functionality
    return jsonify({'success': True, 'message': 'Settings applied to all stores'})

# Legacy routes for backward compatibility
@app.route('/upload')
def upload():
    return redirect(url_for('dashboard'))

@app.route('/gallery')
def gallery():
    """Enhanced gallery with file usage information"""
    images = []
    config = load_store_config()
    
    # Get all files in upload directory
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if allowed_file(filename):
                # Find which screens use this file
                used_by = []
                for store_id, screens in config['screens'].items():
                    for screen_id, screen_data in screens.items():
                        if screen_data.get('file') == filename:
                            store_name = next((s['name'] for s in config['stores'] if s['id'] == store_id), store_id)
                            used_by.append(f"{store_name} - {screen_id}")
                
                images.append({
                    'filename': filename,
                    'used_by': used_by,
                    'unused': len(used_by) == 0
                })
    
    return render_template('gallery.html', images=images)

@app.route('/delete_unused_files', methods=['POST'])
def delete_unused_files():
    """Delete all unused files"""
    try:
        config = load_store_config()
        used_files = set()
        
        # Collect all used files
        for store_id, screens in config['screens'].items():
            for screen_id, screen_data in screens.items():
                if screen_data.get('file'):
                    used_files.add(screen_data['file'])
        
        # Find and delete unused files
        deleted_count = 0
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if allowed_file(filename) and filename not in used_files:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"Deleted unused file: {filename}")
        
        return jsonify({'success': True, 'deleted_count': deleted_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_delete')
def test_delete():
    """Test page for debugging delete functionality"""
    return render_template('test_delete.html')

@app.route('/add_screen', methods=['POST'])
def add_screen():
    """Add a new screen to a store"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_type = data.get('screen_type', 'screen')  # 'screen' or 'promo'
        
        if not store_id:
            return jsonify({'error': 'Store ID is required'}), 400
            
        config = load_store_config()
        
        if store_id not in config['screens']:
            config['screens'][store_id] = {}
        
        # Find next available screen number for store-specific screen IDs
        store_prefix = f"{store_id}_"
        existing_screens = []
        
        for screen_id in config['screens'][store_id].keys():
            # Check if this screen belongs to current store and is of the requested type
            if screen_id.startswith(store_prefix):
                # Extract the part after store prefix (e.g., "screen1" from "1931_screen1")
                screen_part = screen_id[len(store_prefix):]
                if screen_part.startswith(screen_type):
                    existing_screens.append(screen_part)
        
        if existing_screens:
            # Extract numbers and find the highest
            numbers = []
            for screen in existing_screens:
                try:
                    # Remove the screen_type prefix to get just the number
                    num_str = screen.replace(screen_type, '')
                    if num_str:  # Make sure there's a number part
                        num = int(num_str)
                        numbers.append(num)
                except ValueError:
                    continue
            next_num = max(numbers) + 1 if numbers else 1
        else:
            next_num = 1

        # Create store-specific screen ID: store_id + screen_type + number
        new_screen_id = f"{store_id}_{screen_type}{next_num}"
        
        # Set default orientation based on screen type
        is_promo = screen_type.startswith('promo')
        
        # Add new screen with default settings
        config['screens'][store_id][new_screen_id] = {
            'file': None,
            'vertical': is_promo,  # Promos default to vertical
            'horizontal': not is_promo,  # Regular screens default to horizontal
            'rotation': 0,
            'protected': False
        }
        
        save_store_config(config)
        
        return jsonify({
            'success': True, 
            'screen_id': new_screen_id,
            'message': f'Added {new_screen_id} successfully'
        })
        
    except Exception as e:
        print(f"Error adding screen: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_screen', methods=['POST'])
def delete_screen():
    """Delete a screen and its associated file"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        screen_id = data.get('screen_id')
        
        print(f"DEBUG: Delete screen request - store_id: {store_id}, screen_id: {screen_id}")
        
        if not store_id or not screen_id:
            print("DEBUG: Missing store_id or screen_id")
            return jsonify({'error': 'Store ID and Screen ID are required'}), 400
            
        config = load_store_config()
        print(f"DEBUG: Available stores: {list(config['screens'].keys())}")
        
        if store_id not in config['screens']:
            print(f"DEBUG: Store {store_id} not found in config")
            return jsonify({'error': 'Store not found'}), 404
            
        if screen_id not in config['screens'][store_id]:
            print(f"DEBUG: Screen {screen_id} not found in store {store_id}")
            print(f"DEBUG: Available screens in store {store_id}: {list(config['screens'][store_id].keys())}")
            return jsonify({'error': 'Screen not found'}), 404
        
        print(f"DEBUG: Found screen {screen_id} in store {store_id}")
        
        # Delete associated file if exists
        screen_data = config['screens'][store_id][screen_id]
        if screen_data.get('file'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"DEBUG: Deleted file: {filepath}")
        
        # Remove screen from configuration
        del config['screens'][store_id][screen_id]
        print(f"DEBUG: Removed screen {screen_id} from config")
        
        save_store_config(config)
        print(f"DEBUG: Configuration saved successfully")
        
        return jsonify({
            'success': True,
            'message': f'Screen {screen_id} deleted successfully'
        })
        
    except Exception as e:
        print(f"ERROR: Error deleting screen: {e}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/add_store', methods=['POST'])
def add_store():
    """Add a new store with default screens"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        store_name = data.get('store_name')
        
        if not store_id or not store_name:
            return jsonify({'error': 'Store ID and Store Name are required'}), 400
            
        config = load_store_config()
        
        # Check if store already exists
        for store in config['stores']:
            if store['id'] == store_id:
                return jsonify({'error': f'Store {store_id} already exists'}), 400
        
        # Add new store to stores list
        config['stores'].append({
            'id': store_id,
            'name': store_name
        })
        
        # Add default screens for new store (2 screens + 1 promo) with store-specific IDs
        config['screens'][store_id] = {
            f'{store_id}_screen1': {
                'file': None,
                'vertical': False,
                'horizontal': False,
                'rotation': 0
            },
            f'{store_id}_screen2': {
                'file': None,
                'vertical': False,
                'horizontal': False,
                'rotation': 0
            },
            f'{store_id}_promo1': {
                'file': None,
                'vertical': True,
                'horizontal': False,
                'rotation': 0
            }
        }
        
        save_store_config(config)
        
        return jsonify({
            'success': True,
            'store_id': store_id,
            'store_name': store_name,
            'message': f'Store {store_id} - {store_name} added successfully with default screens'
        })
        
    except Exception as e:
        print(f"Error adding store: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_store', methods=['POST'])
def delete_store():
    """Delete a store and all its associated screens and files"""
    try:
        data = request.get_json()
        store_id = data.get('store_id')
        
        if not store_id:
            return jsonify({'error': 'Store ID is required'}), 400
            
        config = load_store_config()
        
        # Protect master store from deletion
        master_store_id = config.get('master_store_id')
        if store_id == master_store_id:
            return jsonify({'error': 'Master Store cannot be deleted'}), 403
        
        # Check if store exists
        store_found = False
        for i, store in enumerate(config['stores']):
            if store['id'] == store_id:
                store_found = True
                store_name = store['name']
                # Remove store from stores list
                del config['stores'][i]
                break
        
        if not store_found:
            return jsonify({'error': 'Store not found'}), 404
        
        # Delete all files associated with this store's screens
        if store_id in config['screens']:
            for screen_id, screen_data in config['screens'][store_id].items():
                if screen_data.get('file'):
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], screen_data['file'])
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"Deleted file: {filepath}")
            
            # Remove all screens for this store
            del config['screens'][store_id]
        
        save_store_config(config)
        
        return jsonify({
            'success': True,
            'message': f'Store {store_id} - {store_name} and all its screens deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting store: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))  # Use 5002 since 5000 seems blocked
    print(f"DEBUG: Starting Flask on port {port}")
    app.run(debug=True, host='0.0.0.0', port=port)
