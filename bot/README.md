# Kredmint Voice Agent — Hindi EMI Reminder

AI-powered outbound voice agent for EMI payment reminders. Makes phone calls, speaks Hindi naturally, handles edge cases, and closes calls with payment commitments.

## Architecture

```
Phone Call (Plivo PSTN)
    ↕ mu-law 8kHz WebSocket
FastAPI Server
    ├── STT:  Deepgram Nova-3 (streaming WebSocket, Hindi)
    ├── LLM:  Groq Llama 3.1 8B (conversational agent)
    ├── TTS:  Inworld AI Riya (streaming WebSocket, Hindi)
    └── VAD:  Silero VAD (interrupt detection)
```

### Audio Flow

```
Caller speaks → Plivo (mu-law 8kHz) → Deepgram STT (streaming)
                                            ↓
                                      Hindi transcript
                                            ↓
                                    Groq LLM (agent response)
                                            ↓
                                    Inworld TTS (streaming MP3)
                                            ↓
                                    MP3 → mu-law conversion
                                            ↓
Caller hears ← Plivo (playAudio chunks) ←──┘
```

## Latency

| Component | Time |
|-----------|------|
| STT (Deepgram streaming) | ~0ms after speech ends |
| LLM (Groq) | 400-700ms |
| TTS TTFB (Inworld streaming) | 500-600ms |
| **User wait after speaking** | **~1.3-1.6s** |

## Project Structure

```
├── app.py                  # FastAPI entry point, startup pre-caching
├── config.py               # Environment vars, user data, greeting
├── requirements.txt
│
├── core/
│   ├── audio.py            # LINEAR16 → mu-law 8kHz conversion
│   ├── conversation.py     # States (INTRO/ASK/HANDLE/CLOSE), static responses
│   └── vad.py              # Silero VAD — speech + interrupt detection
│
├── services/
│   ├── stt.py              # Deepgram Nova-3 WebSocket streaming STT
│   ├── llm.py              # Groq Llama agent with Hindi prompt
│   └── tts.py              # Inworld TTS — WebSocket streaming + REST fallback
│
├── routes/
│   ├── answer.py           # GET/POST /api/plivo/answer — Plivo webhook
│   ├── stream.py           # WS /api/plivo/stream — main call handler
│   └── call.py             # GET /call/test — trigger test call
│
└── test/
    ├── test_inworld.py
    └── test_inworld_hindi.py
```

## Setup

### Prerequisites

- Python 3.10+
- ffmpeg (via `static-ffmpeg` pip package, no system install needed)
- ngrok (for exposing local server to Plivo)

### Install

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Environment Variables

Create `.env`:

```env
PLIVO_AUTH_ID=your_plivo_auth_id
PLIVO_AUTH_TOKEN=your_plivo_auth_token
PLIVO_NUMBER=+91XXXXXXXXXX

SERVER_URL=https://your-ngrok-url.ngrok-free.dev

GROQ_API_KEY=gsk_xxxxx
DEEPGRAM_API_KEY=your_deepgram_key
INWORLD_AUTH=your_inworld_base64_key
```

### Run

```bash
# Terminal 1: Start server
python app.py

# Terminal 2: Expose via ngrok
ngrok http 8001
```

Update `SERVER_URL` in `.env` with the ngrok URL, restart the server.

### Test Call

```
http://45.195.83.136:8001/call/test
```

## Conversation Flow

```
INTRO → User picks up, bot greets
  ↓
ASK → Bot gives EMI details, asks payment date
  ↓
  ├── User gives date → Confirm + Close (1 turn)
  ├── User refuses → Ask why → Escalate to team → Close
  ├── User has problem → Empathize → Close
  └── User asks question → Answer → Re-ask
  ↓
CLOSE → "धन्यवाद जी, दिन शुभ हो।" → Hangup
```

### State Machine

| State | Order | Transitions |
|-------|-------|-------------|
| INTRO | 0 | → ASK, CALLBACK |
| ASK | 1 | → HANDLE, CLOSE |
| CALLBACK | 1 | → CLOSE |
| HANDLE | 2 | → CLOSE |
| CLOSE | 3 | → terminate |

States only move **forward**. No backward transitions allowed.

## Key Features

### Streaming STT (Deepgram)
- Audio chunks sent to Deepgram in real-time as they arrive from Plivo
- No local VAD needed for speech detection — Deepgram handles endpointing
- `speech_final=True` triggers immediate processing
- Config: `endpointing=200ms`, `utterance_end_ms=1200ms`

### Streaming TTS (Inworld)
- Persistent WebSocket context per call (no creation overhead per turn)
- Audio chunks streamed to Plivo as they arrive (TTFB ~500ms)
- MP3 → mu-law conversion via pydub + ffmpeg
- REST fallback for pre-caching static responses
- In-memory cache: repeated responses served at 0ms

### Conversational LLM (Groq)
- Full Hindi conversation — not keyword matching
- Dynamic per-lead data (amounts, dates, names)
- State-aware: tracks INTRO → ASK → HANDLE → CLOSE
- Handles edge cases: refusal, anger, wrong person, financial hardship
- Female agent persona (नेहा) with natural Hindi tone

### Interrupt Handling
- Silero VAD detects user speech while bot is playing audio
- Threshold 0.75 (high enough to avoid echo false triggers)
- `clearAudio` sent to Plivo to stop bot immediately
- 3-second echo protection after speech starts
- User's interrupt speech is captured for processing

### Pre-caching
- 15 static responses cached at startup (greeting, closing, refusal, etc.)
- Dynamic responses cached after first synthesis
- Startup time: ~5 seconds for caching + WebSocket connections

## Configuration

### User Data (config.py)

```python
USER_DATA = {
    "Customer_Name": "राहुल वर्मा",
    "merchant_name": "Flipkart",
    "emi_amount": "2,500",
    "due_date_words": "दस अप्रैल दो हज़ार छब्बीस",
    "loan_id": "KM12345",
    "invoice_id": "INV-9876",
    "T5_amount": "2,400",    # Today
    "T4_amount": "2,420",    # Tomorrow
    "T3_amount": "2,440",    # 2 days
    "T2_amount": "2,460",    # 3 days
    "T1_amount": "2,480"     # 4 days
}
```

T-minus amounts represent early payment discounts. ₹2,400 today vs ₹2,500 on due date.

### VAD Thresholds (core/vad.py)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| SPEECH_THRESHOLD | 0.5 | Normal speech detection |
| INTERRUPT_THRESHOLD | 0.75 | Interrupt while bot speaking |

### Deepgram Config (services/stt.py)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| model | nova-3 | Latest Hindi model |
| language | hi | Hindi |
| endpointing | 200ms | Silence to finalize |
| utterance_end_ms | 1200ms | Full utterance end |
| interim_results | true | Required for utterance_end |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/plivo/answer` | GET/POST | Plivo call webhook — returns stream XML |
| `/api/plivo/stream` | WebSocket | Bidirectional audio stream |
| `/call/test` | GET | Trigger test call |

## Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | Web framework |
| uvicorn | ASGI server |
| aiohttp | Async HTTP + WebSocket client |
| plivo | Telephony SDK |
| groq | LLM API client |
| torch | Silero VAD runtime |
| pydub | MP3 → PCM conversion |
| static-ffmpeg | FFmpeg binary (no system install) |
| python-dotenv | Environment variable loading |

## Production Considerations

- **Multiple agents**: Each call gets its own STT WebSocket + TTS context. Up to 5 TTS contexts per Inworld WebSocket.
- **Dynamic user data**: `USER_DATA` can change per lead. TTS caches by exact text — same amounts share cache across leads.
- **Scaling**: The server handles one call at a time per worker. Use multiple uvicorn workers or container instances for concurrent calls.
- **Error recovery**: STT/TTS WebSocket disconnects are handled with automatic reconnection. REST TTS fallback if WebSocket fails.
- **Cost per call**: Deepgram ($0.0043/min) + Groq (free tier) + Inworld (~$5/1M chars) + Plivo (~₹0.5/min) ≈ **₹1-2 per call**.
