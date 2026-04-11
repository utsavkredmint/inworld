import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

AUTH = os.getenv("INWORLD_AUTH")
# Test endpoint
url = "https://api.inworld.ai/tts/v1/voice"
headers = {
    "Authorization": f"Basic {AUTH}",
    "Content-Type": "application/json"
}
payload = {
    "text": "Hello, testing Riya voice.",
    "voice_id": "Riya",
    "model_id": "inworld-tts-1.5-mini",
    "audio_config": {
        "audio_encoding": "LINEAR16",
        "sample_rate_hertz": 16000
    }
}

try:
    print(f"Testing Inworld with token: {AUTH[:10]}...")
    resp = requests.post(url, headers=headers, json=payload)
    print(f"HTTP Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Success! Audio length: {len(data['audioContent'])}")
    else:
        print(f"Error: {resp.text}")
except Exception as e:
    print(f"Failed: {e}")
