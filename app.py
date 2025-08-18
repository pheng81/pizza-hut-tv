from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
import uuid
import json
import shutil

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configure upload settings
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

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
                return json.loads(content)
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

def get_default_config():
    """Get default store configuration"""
    return {
        'stores': [
            {'id': '1881', 'name': 'Canley Vale'}
        ],
        'screens': {
            '1881': {
                'screen1': {'file': None, 'vertical': True, 'horizontal': True},
                'screen2': {'file': None, 'vertical': True, 'horizontal': True},
                'screen3': {'file': None, 'vertical': True, 'horizontal': True},
                'promo1': {'file': None, 'vertical': True, 'horizontal': False},
                'promo2': {'file': None, 'vertical': True, 'horizontal': False},
                'promo3': {'file': None, 'vertical': True, 'horizontal': False}
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
    config = load_store_config()
    return render_template('dashboard.html', config=config)

@app.route('/upload_to_screen', methods=['POST'])
def upload_to_screen():
    """Upload file to specific screen"""
    store_id = request.form.get('store_id')
    screen_id = request.form.get('screen_id')
    
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
        if store_id in config['screens'] and screen_id in config['screens'][store_id]:
            config['screens'][store_id][screen_id]['file'] = filename
            save_store_config(config)
        
        return jsonify({'success': True, 'filename': filename})
    else:
        return jsonify({'error': 'Invalid file type'}), 400

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

@app.route('/tv_view/<store_id>/<screen_id>')
def tv_view(store_id, screen_id):
    """TV display view for specific screen"""
    config = load_store_config()
    screen_config = config['screens'].get(store_id, {}).get(screen_id, {})
    return render_template('tv_view.html', screen_config=screen_config, screen_id=screen_id)

@app.route('/delete_from_screen', methods=['POST'])
def delete_from_screen():
    """Delete file from specific screen or force delete from gallery"""
    data = request.get_json()
    print(f"Delete request received: {data}")
    
    store_id = data.get('store_id')
    screen_id = data.get('screen_id')
    filename = data.get('filename')
    force_delete = data.get('force_delete', False)
    
    config = load_store_config()
    print(f"Current config: {config}")
    
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
    if store_id and screen_id and store_id in config['screens'] and screen_id in config['screens'][store_id]:
        current_filename = config['screens'][store_id][screen_id]['file']
        print(f"Current filename for {store_id}/{screen_id}: {current_filename}")
        
        if current_filename:
            # Remove file from filesystem
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Deleted file: {filepath}")
                
                # Update configuration
                config['screens'][store_id][screen_id]['file'] = None
                save_store_config(config)
                
                return jsonify({'success': True, 'message': 'File deleted successfully'})
            except Exception as e:
                print(f"Error deleting file: {e}")
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        else:
            print(f"No file to delete for {store_id}/{screen_id}")
            return jsonify({'error': 'No file to delete'}), 400
    
    print(f"Invalid parameters - store_id: {store_id}, screen_id: {screen_id}")
    return jsonify({'error': 'Invalid parameters'}), 400

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
