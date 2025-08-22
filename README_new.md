# Pizza Hut TV - Store Management Dashboard

A comprehensive web application for managing digital menu displays across Pizza Hut stores. Upload images to multiple screens and control their display settings from a centralized dashboard.

## Features

### 🎯 Store Management Dashboard
- **Multi-Store Support**: Manage displays for multiple store locations
- **Screen Configuration**: Configure up to 6 displays per store (3 main screens + 3 promo displays)
- **Real-time Upload**: Upload images directly to specific screens
- **Orientation Control**: Set vertical/horizontal display preferences for each screen
- **Live Preview**: See uploaded content in the dashboard before it goes live

### 📺 TV Display System
- **Full-Screen Display**: Optimized for TV/monitor displays
- **Auto-Refresh**: Automatically updates content every 30 seconds
- **Responsive Design**: Adapts to different screen sizes and orientations
- **Pizza Hut Branding**: Professional branded interface

### 🔧 Technical Features
- **File Management**: Secure file upload with type validation
- **Configuration Persistence**: Settings saved in JSON format
- **RESTful API**: Modern API endpoints for screen management
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Quick Start

### Installation
1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
python app.py
```

The application will be available at: http://localhost:5000

## Usage

### Dashboard Access
1. Open http://localhost:5000 in your web browser
2. You'll see the main dashboard with store "Canley Vale (1881)"

### Uploading Content
1. Click "Upload : File" on any screen card
2. Select an image file (PNG, JPG, JPEG, GIF, BMP, WEBP)
3. The image will be uploaded and displayed in the preview

### Setting Orientation
- Check/uncheck "Vertical" for portrait orientation
- Check/uncheck "Horizontal" for landscape orientation
- Status indicators show current settings (green = enabled, red = disabled)

### TV Display
- Access individual screen displays at: `/tv_view/{store_id}/{screen_id}`
- Example: http://localhost:5000/tv_view/1881/screen1
- Press F11 for fullscreen mode

### Apply to All Stores
- Use the "Submit" button to apply current settings to all stores
- (This feature can be extended for multi-store deployments)

## API Endpoints

### Upload to Screen
```
POST /upload_to_screen
Content-Type: multipart/form-data

Parameters:
- file: Image file
- store_id: Store identifier
- screen_id: Screen identifier (screen1, screen2, screen3, promo1, promo2, promo3)
```

### Update Orientation
```
POST /update_orientation
Content-Type: application/json

Body:
{
  "store_id": "1881",
  "screen_id": "screen1",
  "orientation": "vertical",
  "value": true
}
```

## File Structure
```
Pizza Hut TV/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── store_config.json     # Store configuration (auto-generated)
├── static/
│   └── uploads/          # Uploaded images
└── templates/
    ├── dashboard.html    # Main management dashboard
    ├── tv_view.html     # TV display template
    ├── gallery.html     # Image gallery (legacy)
    └── base.html        # Base template
```

## Screen Types

### Main Screens (screen1, screen2, screen3)
- Large format displays for main menu content
- Support both vertical and horizontal orientations
- Ideal for: Menu boards, daily specials, promotional content

### Promo Displays (promo1, promo2, promo3)
- Smaller promotional displays
- Typically vertical orientation
- Ideal for: Limited time offers, add-on items, social media content

## Configuration

### Store Configuration
The application uses `store_config.json` to store:
- Store information (ID, name)
- Screen configurations per store
- Uploaded file assignments
- Orientation settings

### Supported Image Formats
- PNG
- JPG/JPEG
- GIF
- BMP
- WEBP

### File Size Limits
- Maximum file size: 16MB
- Automatic filename generation prevents conflicts

## Deployment

### Local Development
```bash
python app.py
```

### Production Deployment
1. Set `debug=False` in `app.py`
2. Use a production WSGI server like Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

3. Consider using nginx as a reverse proxy for static file serving

## Browser Compatibility
- Modern browsers (Chrome, Firefox, Safari, Edge)
- JavaScript required for full functionality
- HTML5 file upload support

## Security & Privacy
For business use, ensure your repository and deployments follow security best practices:
- Keep the GitHub repository **private** to protect business logic and configurations
- Use environment variables for sensitive settings (API keys, database connections)
- Review the `PRIVACY_SETUP.md` guide for making your repository private
- Consider using a private Docker registry for production deployments

## Contributing
This is a demonstration project for Pizza Hut TV display management. Extend functionality as needed for your specific requirements.

## License
Educational/Demo purposes.
