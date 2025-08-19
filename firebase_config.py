import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import json

class FirebaseConfig:
    def __init__(self):
        self.db = None
        self.bucket = None
        self.init_firebase()
    
    def init_firebase(self):
        """Initialize Firebase connection"""
        try:
            # For deployment, use environment variables
            if os.getenv('FIREBASE_CREDENTIALS'):
                cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
                cred = credentials.Certificate(cred_dict)
            else:
                # For local development, use service account file
                if os.path.exists('firebase_credentials.json'):
                    cred = credentials.Certificate('firebase_credentials.json')
                else:
                    # Default initialization for testing
                    firebase_admin.initialize_app()
                    self.db = firestore.client()
                    self.bucket = storage.bucket('pizza-hut-tv-default-rtdb.appspot.com')
                    return
            
            # Initialize Firebase app
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'pizza-hut-tv.appspot.com'  # Replace with your bucket name
            })
            
            # Initialize Firestore and Storage
            self.db = firestore.client()
            self.bucket = storage.bucket()
            
        except Exception as e:
            print(f"Firebase initialization error: {e}")
            # Fallback to default initialization
            try:
                firebase_admin.initialize_app()
                self.db = firestore.client()
                self.bucket = storage.bucket()
            except:
                print("Using local storage fallback")
    
    def upload_file(self, file_data, filename):
        """Upload file to Firebase Storage"""
        try:
            if self.bucket:
                blob = self.bucket.blob(f"uploads/{filename}")
                blob.upload_from_string(file_data, content_type='image/jpeg')
                blob.make_public()
                return blob.public_url
            else:
                # Fallback to local storage
                return None
        except Exception as e:
            print(f"File upload error: {e}")
            return None
    
    def delete_file(self, filename):
        """Delete file from Firebase Storage"""
        try:
            if self.bucket:
                blob = self.bucket.blob(f"uploads/{filename}")
                blob.delete()
                return True
        except Exception as e:
            print(f"File delete error: {e}")
            return False
    
    def save_config(self, config_data):
        """Save configuration to Firestore"""
        try:
            if self.db:
                doc_ref = self.db.collection('store_configs').document('main')
                doc_ref.set(config_data)
                return True
        except Exception as e:
            print(f"Config save error: {e}")
            return False
    
    def load_config(self):
        """Load configuration from Firestore"""
        try:
            if self.db:
                doc_ref = self.db.collection('store_configs').document('main')
                doc = doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
        except Exception as e:
            print(f"Config load error: {e}")
        
        # Return default config if Firebase fails
        return {
            "stores": [{"id": "1881", "name": "Canley Vale"}],
            "screens": {
                "1881": {
                    "screen1": {"file": None, "vertical": True, "horizontal": True},
                    "screen2": {"file": None, "vertical": True, "horizontal": True},
                    "screen3": {"file": None, "vertical": True, "horizontal": True},
                    "promo1": {"file": None, "vertical": True, "horizontal": False},
                    "promo2": {"file": None, "vertical": True, "horizontal": false},
                    "promo3": {"file": None, "vertical": True, "horizontal": False}
                }
            }
        }

# Global Firebase instance
firebase_config = FirebaseConfig()
