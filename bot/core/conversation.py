# States
INTRO = "INTRO"
STOCK = "STOCK"
CONFIRM = "CONFIRM"
CLOSE = "CLOSE"
CALLBACK = "CALLBACK"

# Static responses — safe to pre-cache (no dynamic data)
STATIC_RESPONSES = {
    "callback": "ठीक है जी, किस समय कॉल करूँ तो सही रहेगा?",
    "callback_noted": "ठीक है जी, मैंने नोट कर लिया। उस समय कॉल करेंगे। धन्यवाद।",
    "close": "आपका समय देने के लिए धन्यवाद।",
    "not_available": "ठीक है जी, कोई बात नहीं।",
    "no_smoking": "माफ़ कीजिए, हम smoking products नहीं बेचते।",
}

# State order for forward-only guard
STATE_ORDER = {INTRO: 0, CALLBACK: 0, STOCK: 1, CONFIRM: 2, CLOSE: 3}
