"""Test session configuration"""
import os

# Set environment variables like the script does
os.environ['SESSION_COOKIE_SECURE'] = 'False'
os.environ['SESSION_COOKIE_SAMESITE'] = 'Lax'
os.environ['SESSION_COOKIE_DOMAIN'] = ''

# Read them back
cookie_secure = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
cookie_samesite = os.environ.get('SESSION_COOKIE_SAMESITE', 'None')
cookie_domain_env = os.environ.get('SESSION_COOKIE_DOMAIN', '.everydayadvertise.com')
cookie_domain = cookie_domain_env if cookie_domain_env != '' else None

print("✅ Environment Variables:")
print(f"   SESSION_COOKIE_SECURE env: {os.environ.get('SESSION_COOKIE_SECURE')}")
print(f"   SESSION_COOKIE_SAMESITE env: {os.environ.get('SESSION_COOKIE_SAMESITE')}")
print(f"   SESSION_COOKIE_DOMAIN env: '{os.environ.get('SESSION_COOKIE_DOMAIN')}'")
print()
print("✅ Computed Config:")
print(f"   cookie_secure: {cookie_secure}")
print(f"   cookie_samesite: {cookie_samesite}")
print(f"   cookie_domain: {cookie_domain}")
