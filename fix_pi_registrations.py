import requests
import json

server = "https://everydayadvertise.com"

# Get current registrations
print("=== Checking Pi Registrations ===\n")

# Pi1 should be: store_id="1111", screen_id="1111_screen2"
pi1_device_id = "raspberrypi-ce39"
pi1_correct = {
    "store_id": "1111",
    "screen_id": "1111_screen2"
}

# Pi2 should be: store_id="1111", screen_id="1111_screen1"
pi2_device_id = "raspberrypi-new-3ef9"
pi2_correct = {
    "store_id": "1111", 
    "screen_id": "1111_screen1"
}

print(f"Pi1 ({pi1_device_id}) should be: {pi1_correct}")
print(f"Pi2 ({pi2_device_id}) should be: {pi2_correct}")
print("\nTo fix this, you need to:")
print("1. In your dashboard, go to Pi Manager")
print("2. Delete both Pi registrations")
print("3. Use the 'Restart' button on each Pi to generate new pairing codes")
print("4. Re-pair each Pi to the correct store/screen")
print("\nOr we can update the database directly if you have access.")
