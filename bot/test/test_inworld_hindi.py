import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv()

AUTH = os.getenv("INWORLD_AUTH")
url = "https://api.inworld.ai/tts/v1/voice"
headers = {
    "Authorization": f"Basic {AUTH}",
    "Content-Type": "application/json"
}
payload = {
    "text": "Namaste, mera naam Riya hai. Kaise help karun?",
    "voice_id": "Riya",
    "model_id": "inworld-tts-1.5-mini",
    "audio_config": {
        "audio_encoding": "LINEAR16",
        "sample_rate_hertz": 48000,
        "language_code": "hi",
        "speaking_rate": 1.11
    }
}

try:
    print(f"Testing Inworld Hindi with voice Riya...")
    resp = requests.post(url, headers=headers, json=payload)
    print(f"HTTP Status: {resp.status_code}")
    if resp.status_code == 200:
        print(f"Success! Hindi Audio generated.")
    else:
        print(f"Error: {resp.text}")
except Exception as e:
    print(f"Failed: {e}")
