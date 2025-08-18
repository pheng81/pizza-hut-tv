from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def optimize_image(image_path, max_width=1920, max_height=1080, quality=85):
    """Optimize image for TV display"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Save optimized version
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            return True
    except Exception as e:
        print(f"Error optimizing image: {e}")
        return False

@app.route('/')
def index():
    """Main upload page"""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        file.save(filepath)
        
        # Optimize for TV display
        if optimize_image(filepath):
            flash('Image uploaded and optimized successfully!')
        else:
            flash('Image uploaded but optimization failed')
        
        return redirect(url_for('display', filename=filename))
    else:
        flash('Invalid file type. Please upload: PNG, JPG, JPEG, GIF, BMP, or WEBP')
        return redirect(request.url)

@app.route('/display/<filename>')
def display(filename):
    """Display image on TV-friendly page"""
    return render_template('display.html', filename=filename)

@app.route('/tv/<filename>')
def tv_display(filename):
    """Full-screen TV display"""
    return render_template('tv_display.html', filename=filename)

@app.route('/gallery')
def gallery():
    """Show all uploaded images"""
    images = []
    upload_dir = app.config['UPLOAD_FOLDER']
    
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            if allowed_file(filename):
                images.append(filename)
    
    return render_template('gallery.html', images=images)

@app.route('/api/images')
def api_images():
    """API endpoint to get list of images"""
    images = []
    upload_dir = app.config['UPLOAD_FOLDER']
    
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            if allowed_file(filename):
                images.append({
                    'filename': filename,
                    'url': url_for('static', filename=f'uploads/{filename}')
                })
    
    return jsonify(images)

@app.route('/delete/<filename>', methods=['POST'])
def delete_image(filename):
    """Delete an uploaded image"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash('Image deleted successfully!')
        except Exception as e:
            flash(f'Error deleting image: {e}')
    else:
        flash('Image not found')
    
    return redirect(url_for('gallery'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
