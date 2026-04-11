"""Pre-setup call sessions. API creates them, stream.py uses them."""

from services.tts import TTSContext

# call_id → {"tts_ctx": TTSContext, "stt_ready": bool}
_sessions = {}


async def prepare_session(call_id):
    """Pre-connect STT + open TTS context before Plivo dials."""
    from services.stt import connect as stt_connect
    import logging
    log = logging.getLogger(__name__)

    tts_ctx = TTSContext()

    # Connect both in parallel
    import asyncio
    await asyncio.gather(stt_connect(), tts_ctx.open())

    _sessions[call_id] = {
        "tts_ctx": tts_ctx,
        "stt_ready": True,
    }
    log.info(f"[SESSION] Pre-setup complete for {call_id}")


def get_session(call_id):
    """Get pre-setup session. Returns None if not pre-setup."""
    return _sessions.pop(call_id, None)
