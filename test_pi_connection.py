import requests

pi_id = "raspberrypi-ce39"
url = f"https://everydayadvertise.com/api/pi-status/{pi_id}"

print(f"Testing Pi connection: {pi_id}")
print(f"URL: {url}\n")

r = requests.get(url)
print(f"Status Code: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print(f"\nPi Status: {data.get('status')}")
    print(f"Pi ID: {data.get('pi_id')}")
    print(f"Current State: {data.get('current_state')}")
    print(f"Version: {data.get('version')}")
    print(f"\nFull Response:")
    print(data)
else:
    print(f"Error: {r.text}")
