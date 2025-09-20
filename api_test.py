import requests
import json

# Test the API endpoint
url = "http://everydayadvertise.com:5002/api/stores_by_code/1769"
print(f"Testing: {url}")
print("=" * 50)

try:
    response = requests.get(url, timeout=15)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"Response Text: {response.text}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"JSON Data: {json.dumps(data, indent=2)}")
        except:
            print("Response is not valid JSON")
    
except Exception as e:
    print(f"Error: {e}")
    
print("=" * 50)