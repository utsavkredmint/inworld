import asyncio
import json
import logging
import aiohttp
from config import DEEPGRAM_API_KEY

log = logging.getLogger(__name__)

DG_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=mulaw"
    "&sample_rate=8000"
    "&channels=1"
    "&model=nova-2"
    "&language=hi"
    "&interim_results=true"
    "&endpointing=50" # 🚀 RTX 6000 POWER: 50ms near-instant transcription
    "&smart_format=true"
    "&punctuate=true"
)

_dg_ws = None
_dg_session = None
_dg_lock = asyncio.Lock()
_transcript_queue = None
_dg_reader_task = None


async def connect():
    """Connect to Deepgram streaming WebSocket. Call at start of each phone call."""
    global _dg_ws, _dg_session, _dg_reader_task, _transcript_queue

    # Close existing connection if any
    await disconnect()

    async with _dg_lock:
        if _dg_session is None or _dg_session.closed:
            _dg_session = aiohttp.ClientSession()

        _transcript_queue = asyncio.Queue()

        _dg_ws = await _dg_session.ws_connect(
            DG_URL,
            headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
            heartbeat=8
        )
        log.info("[STT] Deepgram WebSocket connected")
        _dg_reader_task = asyncio.create_task(_dg_reader())


async def disconnect():
    """Close Deepgram connection. Call at end of each phone call."""
    global _dg_ws, _dg_reader_task
    if _dg_ws and not _dg_ws.closed:
        try:
            await _dg_ws.send_str(json.dumps({"type": "CloseStream"}))
            await _dg_ws.close()
        except:
            pass
    _dg_ws = None
    if _dg_reader_task and not _dg_reader_task.done():
        _dg_reader_task.cancel()
    _dg_reader_task = None
    log.info("[STT] Deepgram disconnected")


async def _dg_reader():
    global _dg_ws
    try:
        async for msg in _dg_ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                msg_type = data.get("type", "")

                if msg_type == "Results":
                    transcript = (
                        data.get("channel", {})
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)

                    if is_final and transcript:
                        log.info(f"[STT] Final: '{transcript}' (speech_final={speech_final})")
                        if _transcript_queue:
                            await _transcript_queue.put(("final", transcript, speech_final))

                elif msg_type == "UtteranceEnd":
                    log.info("[STT] UtteranceEnd detected")
                    if _transcript_queue:
                        await _transcript_queue.put(("utterance_end", "", True))

                elif msg_type == "Metadata":
                    log.info("[STT] Deepgram ready (Metadata received)")

            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"[STT] Reader error: {e}")
    finally:
        log.info("[STT] Deepgram reader stopped")
        _dg_ws = None
        if _transcript_queue:
            await _transcript_queue.put(("error", "", False))


async def send_audio_chunk(chunk):
    """Send raw mu-law audio chunk to Deepgram."""
    if _dg_ws and not _dg_ws.closed:
        try:
            await _dg_ws.send_bytes(chunk)
        except:
            pass


async def get_final_transcript(timeout=8.0):
    """Wait for complete utterance transcript from Deepgram."""
    if not _transcript_queue:
        return ""

    collected = []
    deadline = asyncio.get_event_loop().time() + timeout

    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            msg_type, text, speech_final = await asyncio.wait_for(
                _transcript_queue.get(), timeout=remaining
            )
            if msg_type == "error":
                break
            if msg_type == "final" and text:
                collected.append(text)
                # speech_final=True means user finished speaking — return immediately
                if speech_final:
                    break
            # Ignore utterance_end with no speech (echo/noise)
            if not collected and msg_type == "utterance_end":
                continue
            # utterance_end with collected text — also return
            if collected and msg_type == "utterance_end":
                break
        except asyncio.TimeoutError:
            # 🚀 LATENCY WIN: If we have text and timed out waiting for more, assume user finished
            if collected:
                log.info("[STT] Silence timeout (no activity). Completing.")
                break
            continue
        
        # 🚀 ULTRA LATENCY: If we have text and it's been > 0.4s since last fragment, assume user is done
        if collected and (asyncio.get_event_loop().time() > deadline - timeout + 0.4):
            log.info("[STT] Force completing due to 0.4s silence")
            break

    result = " ".join(collected).strip()
    if result:
        log.info(f"[STT] Complete: '{result}'")
    return result
