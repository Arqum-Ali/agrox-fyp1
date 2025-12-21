import requests
import json

# Test backend chat endpoint
url = 'http://localhost:5000/chat/rooms'

# You need a valid token - get it from your app after login
token = "YOUR_TOKEN_HERE"  # Replace with actual token from Flutter app

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

data = {
    'listing_id': 1,
    'listing_type': 'wheat'
}

print(f"Testing POST {url}")
print(f"Headers: {headers}")
print(f"Data: {data}\n")

try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except requests.exceptions.ConnectionError as e:
    print(f"❌ CONNECTION ERROR: Cannot connect to backend")
    print(f"Make sure backend is running on port 5000")
    print(f"Error: {e}")
except requests.exceptions.Timeout:
    print(f"❌ TIMEOUT: Backend not responding")
except Exception as e:
    print(f"❌ ERROR: {e}")
