# Start local Flask server with production database
$env:USERS_DB_PATH = "database_from_server.db"
$env:FLASK_ENV = "development"
$env:SESSION_COOKIE_DOMAIN = $null  # Allow any domain
python app.py
