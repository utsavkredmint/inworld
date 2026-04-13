"""Pre-setup call sessions. API creates them, stream.py uses them."""

from services.tts import TTSContext

# call_id → {"tts_ctx": TTSContext, "stt_ready": bool}
_sessions = {}


async def prepare_session(call_id, agent_id):
    """Pre-connect STT + open TTS context + pre-generate greeting before Plivo answer."""
    from services.stt import connect as stt_connect
    from services.tts import TTSContext, omnivoice_tts
    from database import get_agent
    import logging
    import asyncio
    log = logging.getLogger(__name__)

    # 1. Fetch Agent Data
    agent = get_agent(agent_id)
    greeting = agent.get("greeting", "नमस्ते") if agent else "नमस्ते"
    voice_id = agent.get("voice") if agent else None
    language = agent.get("language", "hi") if agent else "hi"

    tts_ctx = TTSContext()

    # 2. Start pre-generation tasks
    # We start greeting generation task immediately
    greeting_task = asyncio.create_task(omnivoice_tts(greeting, voice_id=voice_id, language=language))
    
    # 3. Connect STT and TTS in parallel
    await asyncio.gather(stt_connect(), tts_ctx.open())

    _sessions[call_id] = {
        "tts_ctx": tts_ctx,
        "stt_ready": True,
        "greeting_task": greeting_task, # Store the task for stream.py
        "agent": agent # Pre-loaded agent data
    }
    log.info(f"[SESSION] Pre-setup complete for {call_id} (Greeting pre-generation started)")


def get_session(call_id):
    """Get pre-setup session. Returns None if not pre-setup."""
    return _sessions.pop(call_id, None)
