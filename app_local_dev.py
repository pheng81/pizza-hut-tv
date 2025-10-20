"""
🍕 Pizza Hut TV - LOCAL DEVELOPMENT SERVER
Simplified local testing version with HTTP cookies enabled
Completely separate from production deployment
"""

from flask import Flask, session, request, redirect, url_for, render_template, jsonify
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3
import logging
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with BOTH template folders (production + local dev)
from flask import Flask
from jinja2 import ChoiceLoader, FileSystemLoader

app = Flask(__name__)

# Use both template folders: production templates/ and local templates_local/
# This allows us to use production dashboard.html while keeping local login.html
app.jinja_loader = ChoiceLoader([
    FileSystemLoader('templates'),  # Production templates (dashboard, etc.)
    FileSystemLoader('templates_local')  # Local dev templates (login fallback)
])

# SECRET KEY for sessions
app.secret_key = 'local-dev-secret-key-pizza-hut-tv-2025'

# LOCAL DEVELOPMENT Cookie Settings (HTTP-compatible)
app.config.update(
    SECRET_KEY='local-dev-secret-key-pizza-hut-tv-2025',
    SESSION_COOKIE_SECURE=False,  # Allow HTTP (no HTTPS required)
    SESSION_COOKIE_SAMESITE='Lax',  # Lax for local dev
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JS access
    SESSION_COOKIE_DOMAIN=None,  # No domain restriction
    PREFERRED_URL_SCHEME='http',  # HTTP not HTTPS
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=86400  # 24 hours
)

# Apply ProxyFix for local development
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Database path
DATABASE_PATH = 'database_from_server.db'

logger.info("=" * 60)
logger.info("🍕 LOCAL DEVELOPMENT SERVER STARTED")
logger.info("=" * 60)
logger.info(f"Database: {DATABASE_PATH}")
logger.info(f"Session Secure: {app.config['SESSION_COOKIE_SECURE']}")
logger.info(f"Session SameSite: {app.config['SESSION_COOKIE_SAMESITE']}")
logger.info(f"Session Domain: {app.config['SESSION_COOKIE_DOMAIN']}")
logger.info("=" * 60)


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def home():
    """Home page - redirect to login or dashboard."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        logger.info(f"🔐 Login attempt: {username}")
        
        if not username or not password:
            logger.warning("❌ Empty username or password")
            return render_template('login.html', error='Please enter both username and password')
        
        try:
            db = get_db()
            cursor = db.cursor()
            
            # Query user by username (database_from_server.db doesn't have is_active column)
            cursor.execute("""
                SELECT id, username, password_hash, email_verified
                FROM users 
                WHERE username = ?
            """, (username,))
            
            user = cursor.fetchone()
            db.close()
            
            if user:
                logger.info(f"✅ User found: {username} (ID: {user['id']}, Email Verified: {user['email_verified']})")
                
                # Note: database_from_server.db doesn't have is_active column
                # Assuming all users in the database are active for local testing
                
                # Verify password
                if check_password_hash(user['password_hash'], password):
                    logger.info(f"✅ Password correct for {username}")
                    
                    # Set session
                    session.clear()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session.permanent = True
                    
                    logger.info(f"✅ Session created for user {username} (ID: {user['id']})")
                    logger.info(f"✅ Session data: {dict(session)}")
                    
                    # Redirect to dashboard
                    next_page = request.args.get('next', url_for('dashboard'))
                    logger.info(f"✅ Redirecting to: {next_page}")
                    return redirect(next_page)
                else:
                    logger.warning(f"❌ Invalid password for {username}")
                    return render_template('login.html', error='Invalid username or password')
            else:
                logger.warning(f"❌ User not found: {username}")
                return render_template('login.html', error='Invalid username or password')
                
        except Exception as e:
            logger.error(f"❌ Login error: {e}", exc_info=True)
            return render_template('login.html', error='An error occurred. Please try again.')
    
    # GET request - show login form
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard page - using production template for full features"""
    if 'user_id' not in session:
        logger.warning("⚠️ Dashboard access denied - no session")
        logger.info(f"⚠️ Current session data: {dict(session)}")
        return redirect(url_for('login', next='/dashboard'))
    
    logger.info(f"✅ Dashboard access granted for user {session.get('username')} (ID: {session.get('user_id')})")
    
    # Production-compatible config structure
    config = {
        'stores': [],
        'screens': {},
        'settings': {
            'media_base_url': 'https://everydayadvertise.com'
        },
        'media_base_url': 'https://everydayadvertise.com'
    }
    
    # User info
    username = session.get('username', '')
    link_code = ''  # Could fetch from database if needed
    
    # Asset busting
    import time
    asset_bust = int(time.time())
    
    try:
        # Try production dashboard template (templates/dashboard.html)
        logger.info("📄 Loading production dashboard template...")
        return render_template(
            'dashboard.html',
            config=config,
            media_base_url='https://everydayadvertise.com',
            asset_bust=asset_bust,
            build_stamp='local-dev',
            git_commit='local',
            user_email=username,
            link_code=link_code
        )
    except Exception as e:
        logger.error(f"❌ Failed to load production dashboard: {e}")
        # Fallback to simple local dashboard
        return f"<h1>Dashboard</h1><p>Welcome, {username}</p><p>Error loading full dashboard: {e}</p>"


@app.route('/logout')
def logout():
    """Logout - clear session."""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"👋 User {username} logged out")
    return redirect(url_for('login'))


@app.route('/profile')
def profile():
    """User profile page - placeholder for local dev"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    username = session.get('username', 'Unknown')
    return f"""
    <html>
    <head><title>Profile</title></head>
    <body style="font-family: Arial; padding: 40px;">
        <h1>User Profile</h1>
        <p><strong>Username:</strong> {username}</p>
        <p><strong>User ID:</strong> {session.get('user_id')}</p>
        <br>
        <a href="/dashboard">← Back to Dashboard</a> | 
        <a href="/logout">Logout</a>
    </body>
    </html>
    """


# Remote Pi Manager page
@app.route('/remote-pi-manager')
def remote_pi_manager():
    """Remote Pi Manager page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('remote_pi_manager.html')


# Remote Pi Manager API endpoints
@app.route('/api/configure-pi', methods=['POST'])
def configure_pi():
    """Configure a Pi remotely using Pi ID"""
    try:
        logger.info(f'🔧 Remote Pi Manager API called')
        
        data = request.get_json(force=True)
        if not data:
            logger.error('❌ No JSON data received')
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
            
        logger.info(f'📥 Parsed JSON data: {data}')
        
        pi_id = data.get('pi_id', '').strip()
        pair_code = data.get('pair_code', '').strip()
        store_id = data.get('store_id', '').strip()
        screen_id = data.get('screen_id', '').strip()
        pi_ip = data.get('pi_ip', '').strip()

        # Validate required fields (except pi_ip which can be auto-resolved)
        if not all([pi_id, pair_code, store_id, screen_id]):
            logger.error(f'❌ Missing fields: pi_id={pi_id}, pair_code={pair_code}, store_id={store_id}, screen_id={screen_id}')
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        # If no IP provided, resolve from mapping file
        if not pi_ip:
            import json
            try:
                with open('pi_id_ip_map.json', 'r') as f:
                    pi_map = json.load(f)
                pi_ip = pi_map.get(pi_id)
                if pi_ip:
                    logger.info(f'✅ Resolved Pi IP from mapping: {pi_id} -> {pi_ip}')
            except Exception as e:
                logger.error(f'❌ Error loading pi_id_ip_map.json: {e}')
                return jsonify({'success': False, 'message': 'Could not resolve Pi IP'}), 400

        if not pi_ip:
            logger.error(f'❌ No IP found for Pi ID: {pi_id}')
            return jsonify({'success': False, 'message': f'No IP found for Pi ID: {pi_id}. Pi may not be registered.'}), 400

        # POST configuration to Pi's HTTP server
        import requests
        logger.info(f'📡 Sending config to Pi at http://{pi_ip}:8080/configure')
        pi_url = f'http://{pi_ip}:8080/configure'
        payload = {
            'pi_id': pi_id,
            'pair_code': pair_code,
            'store_id': store_id,
            'screen_id': screen_id
        }
        
        try:
            logger.info(f'📡 Sending config to Pi at {pi_url}')
            resp = requests.post(pi_url, json=payload, timeout=5)
            resp.raise_for_status()
            pi_response = resp.json()
            logger.info(f'✅ Pi response: {pi_response}')
            return jsonify({'success': True, 'message': 'Configuration sent to Pi', 'pi_response': pi_response})
        except Exception as e:
            logger.error(f'❌ Error sending config to Pi: {e}')
            return jsonify({'success': False, 'message': f'Failed to configure Pi: {e}'}), 500
        
    except Exception as e:
        logger.error(f'❌ Remote Pi configuration error: {e}')
        return jsonify({'success': False, 'message': 'Configuration failed'}), 500


@app.route('/api/pi-status/<pi_id>')
def pi_status(pi_id):
    """Get status of a specific Pi"""
    try:
        logger.info(f'📊 Pi status request for: {pi_id}')

        # Get Pi IP from query parameter or mapping file
        pi_ip = request.args.get('pi_ip')

        if not pi_ip:
            # Resolve from pi_id_ip_map.json
            try:
                with open('pi_id_ip_map.json', 'r') as f:
                    pi_map = json.load(f)
                    pi_ip = pi_map.get(pi_id)
                    if pi_ip:
                        logger.info(f'✅ Resolved Pi IP from mapping: {pi_id} -> {pi_ip}')
            except Exception as e:
                logger.warning(f'⚠️ Could not load pi_id_ip_map.json: {e}')

        if not pi_ip:
            logger.warning(f'❌ No IP found for Pi ID: {pi_id}')
            return jsonify({
                'success': False,
                'pi_id': pi_id,
                'status': 'offline',
                'message': 'Pi not registered or IP not found'
            }), 404

        # Check Pi status
        import requests
        pi_url = f'http://{pi_ip}:8080/status'
        
        try:
            resp = requests.get(pi_url, timeout=3)
            resp.raise_for_status()
            status = resp.json()
            status['success'] = True
            logger.info(f'✅ Pi {pi_id} is online at {pi_ip}')
            return jsonify(status)
        except Exception as e:
            logger.warning(f'❌ Pi {pi_id} unreachable at {pi_ip}: {e}')
            return jsonify({
                'success': False,
                'pi_id': pi_id,
                'status': 'offline',
                'message': f'Pi unreachable: {e}'
            }), 503
            
    except Exception as e:
        logger.error(f'❌ Pi status error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


# Dashboard API endpoints (for production dashboard compatibility)
@app.route('/api/me')
def api_me():
    """Get current user info"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'id': session.get('user_id'),
        'username': session.get('username'),
        'email': session.get('username'),
        'link_code': ''
    })


@app.route('/screens/<store_id>')
def get_screens(store_id):
    """Get screens for a store"""
    # Return empty screens for local dev
    return jsonify({
        'success': True,
        'screens': {}
    })


@app.route('/add_screen', methods=['POST'])
def add_screen():
    """Add a new screen - placeholder for local dev"""
    logger.info("📺 Add screen request (local dev - returning success)")
    return jsonify({
        'success': True,
        'message': 'Screen added (local dev mode - not persisted)',
        'screen_id': 'test_screen'
    })


@app.route('/save_config', methods=['POST'])
def save_config():
    """Save configuration - placeholder for local dev"""
    logger.info("💾 Save config request (local dev - returning success)")
    return jsonify({
        'success': True,
        'message': 'Configuration saved (local dev mode - not persisted)'
    })


@app.route('/api/register_pi', methods=['POST'])
def register_pi():
    """Register Pi identifier and IP address automatically."""
    try:
        data = request.get_json(force=True)
        pi_id = data.get('pi_id', '').strip()
        pi_ip = data.get('pi_ip', '').strip()
        
        if not pi_id or not pi_ip:
            logger.error('❌ Missing pi_id or pi_ip in registration request')
            return jsonify({'success': False, 'message': 'Missing pi_id or pi_ip'}), 400
        
        # Thread-safe update of pi_id_ip_map.json
        def update_map():
            try:
                map_path = 'pi_id_ip_map.json'
                try:
                    with open(map_path, 'r') as f:
                        pi_map = json.load(f)
                except Exception:
                    pi_map = {}
                
                pi_map[pi_id] = pi_ip
                
                with open(map_path, 'w') as f:
                    json.dump(pi_map, f, indent=4)
                
                logger.info(f'✅ Pi registered: {pi_id} -> {pi_ip}')
            except Exception as e:
                logger.error(f'❌ Error updating pi_id_ip_map.json: {e}')
        
        import threading
        threading.Thread(target=update_map).start()
        
        return jsonify({
            'success': True, 
            'message': f'Registered {pi_id} with IP {pi_ip}'
        }), 200
        
    except Exception as e:
        logger.error(f'❌ Pi registration error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/test-session')
def test_session():
    """Test endpoint to check session state."""
    return jsonify({
        'session_data': dict(session),
        'has_user_id': 'user_id' in session,
        'config': {
            'SESSION_COOKIE_SECURE': app.config['SESSION_COOKIE_SECURE'],
            'SESSION_COOKIE_SAMESITE': app.config['SESSION_COOKIE_SAMESITE'],
            'SESSION_COOKIE_DOMAIN': app.config['SESSION_COOKIE_DOMAIN'],
            'PREFERRED_URL_SCHEME': app.config['PREFERRED_URL_SCHEME']
        }
    })


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🍕 Pizza Hut TV - LOCAL DEVELOPMENT SERVER")
    print("=" * 60)
    print("📍 Access at: http://127.0.0.1:5002")
    print("🔑 Login: kayson5@gmail.com / test123")
    print("=" * 60)
    print()
    
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=True
    )
