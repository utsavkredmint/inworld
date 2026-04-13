"""Pre-setup call sessions. API creates them, stream.py uses them."""
import asyncio

from services.tts import TTSContext

# call_id → {"tts_ctx": TTSContext, "stt_ready": bool}
_sessions = {}


async def prepare_session(call_id, greeting=None, voice_id=None, language="hindi"):
    """Pre-connect STT + open TTS context + PRE-GENERATE GREETING before Plivo dials."""
    from services.stt import connect as stt_connect
    from services.tts import omnivoice_tts, update_tts_cache
    import logging
    log = logging.getLogger(__name__)

    tts_ctx = TTSContext()

    # Define tasks: STT connect, TTS context open, AND Greeting generation
    tasks = [stt_connect(), tts_ctx.open()]
    
    if greeting:
        log.info(f"[SESSION] Pre-generating greeting for {call_id}: {greeting[:40]}...")
        # Use Fast Mode (20 steps) to ensure it's done before the phone rings
        tasks.append(omnivoice_tts(greeting, voice_id=voice_id, language=language, num_inference_steps=20))

    # Connect/Generate everything in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # If greeting was generated, cache it
    if greeting and len(results) > 2:
        audio = results[2]
        if not isinstance(audio, Exception) and audio:
            update_tts_cache(greeting, audio, voice_id=voice_id, language=language)
            log.info(f"[SESSION] Greeting pre-cached for {call_id}")

    _sessions[call_id] = {
        "tts_ctx": tts_ctx,
        "stt_ready": True,
    }
    log.info(f"[SESSION] Pre-setup complete for {call_id}")


def get_session(call_id):
    """Get pre-setup session. Returns None if not pre-setup."""
    return _sessions.pop(call_id, None)
