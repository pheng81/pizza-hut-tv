import requests
import json

# Test using IP address
url = "http://172.67.166.34:5002/api/stores_by_code/1769"
print(f"Testing IP-based URL: {url}")

try:
    response = requests.get(url, timeout=15)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("JSON Response:", json.dumps(data, indent=2))
        except:
            print("Not valid JSON")
            
except Exception as e:
    print(f"Error: {e}")