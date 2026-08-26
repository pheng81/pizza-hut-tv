"""
Basic tests for Pizza Hut TV
Run with: python test_app.py
"""
import sys
import os

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    try:
        import flask
        import flask_socketio
        import boto3
        from dotenv import load_dotenv
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("Testing configuration...")
    try:
        from config import config
        assert config.FLASK_ENV in ['development', 'production']
        assert config.DATABASE_PATH is not None
        assert config.SERVER_PORT > 0
        print(f"✓ Config loaded: {config.FLASK_ENV} environment")
        return True
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False

def test_database_path():
    """Test database file exists"""
    print("Testing database...")
    try:
        from config import config
        if config.is_development():
            db_path = config.DATABASE_PATH
            if os.path.exists(db_path):
                print(f"✓ Database found: {db_path}")
                return True
            else:
                print(f"⚠ Database not found: {db_path} (will be created on first run)")
                return True
        else:
            print("✓ Production mode (skipping local DB check)")
            return True
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False

def test_critical_files():
    """Test that critical files exist"""
    print("Testing critical files...")
    critical_files = ['app.py', 'requirements.txt', 'config.py']
    all_exist = True
    
    for file in critical_files:
        if os.path.exists(file):
            print(f"✓ Found: {file}")
        else:
            print(f"✗ Missing: {file}")
            all_exist = False
    
    return all_exist

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  PIZZA HUT TV - TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        test_imports,
        test_config,
        test_database_path,
        test_critical_files
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        print()
    
    # Summary
    print("="*60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("="*60)
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("="*60)
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
