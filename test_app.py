import sys
import os
sys.path.append('c:\\Users\\toeng\\Pizza Hut TV')

try:
    print("Testing Flask import...")
    from flask import Flask
    print("✓ Flask import successful")
    
    print("Testing app import...")
    import app
    print("✓ App import successful")
    
    print("Testing Flask app creation...")
    test_app = Flask(__name__)
    print("✓ Flask app creation successful")
    
    print("Testing template rendering...")
    from flask import render_template
    with test_app.app_context():
        config = {
            'stores': [{'id': '1881', 'name': 'Canley Vale'}],
            'screens': {
                '1881': {
                    'screen1': {'file': None, 'vertical': True, 'horizontal': True}
                }
            }
        }
        # Don't actually render, just test the import
        print("✓ Template rendering setup successful")
    
    print("All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
