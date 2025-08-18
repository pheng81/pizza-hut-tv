import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel expects the Flask app to be named 'app'
if __name__ == "__main__":
    app.run()
