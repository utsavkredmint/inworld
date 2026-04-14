import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============= CONFIG =============
PLIVO_AUTH_ID    = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")
PLIVO_NUMBER     = os.getenv("PLIVO_NUMBER")
SERVER_URL       = os.getenv("SERVER_URL")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
INWORLD_AUTH     = os.getenv("INWORLD_AUTH")

# ============= CALL DATA (per distributor) ============
CALL_DATA = {
    "skus": [
        "Rajnigandha 2.5 Gram",
        "Rajnigandha 17 Gram",
        "Khajoor Pouch",
    ],
    "current_time": datetime.now().strftime("%d %B %Y, %I:%M %p"),
}

GREETING = "नमस्ते, O2R से बात कर रही हूँ। आपकी inventory check करने के लिए phone किया था। क्या आपके पास दो मिनट हैं?"
