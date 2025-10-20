"""
Emergency File Upload Endpoint
Add this to app.py to allow uploading files via web interface
"""

import os
import base64
from functools import wraps

# Add this secret upload key
UPLOAD_SECRET = "pizza_hut_emergency_upload_2025"

def require_upload_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('X-Upload-Secret')
        if auth_header != UPLOAD_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/emergency-upload', methods=['POST'])
@require_upload_auth
def emergency_upload():
    """
    Emergency endpoint to upload files via HTTP POST
    Used when SSH is blocked
    
    POST /api/emergency-upload
    Headers:
        X-Upload-Secret: pizza_hut_emergency_upload_2025
    Body:
        {
            "filename": "dashboard.html" or "app.py",
            "content": "base64_encoded_file_content",
            "destination": "templates/dashboard.html" or "app.py"
        }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        content_b64 = data.get('content')
        destination = data.get('destination')
        
        if not all([filename, content_b64, destination]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Decode base64 content
        content = base64.b64decode(content_b64).decode('utf-8')
        
        # Determine full path
        base_path = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(base_path, destination)
        
        # Create directory if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Emergency upload: {filename} -> {full_path}")
        
        return jsonify({
            'success': True,
            'message': f'File {filename} uploaded successfully',
            'path': full_path
        })
        
    except Exception as e:
        logging.error(f"Emergency upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/emergency-restart', methods=['POST'])
@require_upload_auth
def emergency_restart():
    """
    Restart the Flask application
    """
    try:
        import subprocess
        subprocess.Popen(['sudo', 'systemctl', 'restart', 'pizza-hut-tv'])
        return jsonify({
            'success': True,
            'message': 'Server restart initiated'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
