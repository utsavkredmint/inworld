import asyncio
import base64
import json
import logging
import time
from datetime import datetime

import aiohttp
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from plivo import RestClient

from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN, CALL_DATA, GREETING
from database import get_call, get_agent, add_message, update_call
from services.tts import omnivoice_tts, stream_tts_to_plivo, TTSContext, TTS_CACHE, prepare_for_tts
from services.stt import send_audio_chunk, get_final_transcript, connect as stt_connect, disconnect as stt_disconnect
from services.llm import get_agent_response
from core.conversation import INTRO, STATE_ORDER
from core.vad import SileroVAD

log = logging.getLogger(__name__)
router = APIRouter()
plivo_client = RestClient(auth_id=PLIVO_AUTH_ID, auth_token=PLIVO_AUTH_TOKEN)


@router.websocket("/api/plivo/stream")
async def plivo_stream(websocket: WebSocket):
    log.info("[STREAM] Incoming WebSocket connection attempt...")
    query_params = dict(websocket.query_params)
    call_uuid = query_params.get("call_uuid")
    call_id = query_params.get("call_id", "")
    to_number = query_params.get("to_number", "").replace(" ", "+")
    
    start_connect = time.time()
    try:
        await websocket.accept()
        log.info(f"[STREAM] WebSocket ACCEPTED for {call_uuid}")
    except Exception as e:
        log.error(f"[STREAM] Failed to accept WebSocket: {e}")
        return

    # scope variables
    user_data = None
    user_name = None

    # Load User Context
    from pathlib import Path
    dummy_path = Path(__file__).parent.parent / "dummy_data.json"
    if dummy_path.exists():
        try:
            with open(dummy_path, "r", encoding="utf-8") as f:
                users_list = json.load(f)
                target_number = to_number if to_number.startswith("+") else "+" + to_number
                for u in users_list:
                    if u.get("phone") and target_number.endswith(u["phone"]):
                        user_data = u
                        user_name = u.get("name")
                        break
            if user_name and any('a' <= char.lower() <= 'z' for char in user_name):
                async with aiohttp.ClientSession() as s:
                    async with s.get(f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q={user_name}', timeout=1.0) as r:
                        if r.status == 200:
                            d = await r.json()
                            user_name = d[0][0][0]
        except Exception: pass
    
    from config import CALL_DATA as GLOBAL_CALL_DATA
    local_call_data = GLOBAL_CALL_DATA.copy()
    if user_data:
        local_call_data["skus"] = user_data.get("skus", GLOBAL_CALL_DATA["skus"])

    agent = None
    greeting = GREETING
    system_prompt_override = None

    if call_id:
        db_call = get_call(call_id)
        if db_call:
            agent = get_agent(db_call["agent_id"])
            if agent:
                greeting = agent["greeting"]
                system_prompt_override = agent["system_prompt"]
                update_call(call_id, status="in-progress", started_at=datetime.utcnow().isoformat() + "Z")
                try:
                    from config import SERVER_URL
                    plivo_client.calls.record(call_uuid=call_uuid, file_format="mp3", time_limit=3600,
                        callback_url=f"{SERVER_URL}/api/plivo/record_callback?call_id={call_id}")
                except Exception: pass

    if user_name:
        greeting = greeting.replace("नमस्ते", f"नमस्ते {user_name}").replace("O2R से", f"O2R से {user_name}")

    agent_language = agent.get("language", "hindi") if agent else "hindi"
    voice_id = agent.get("voice") if agent else None
    tts_language = "hi" if agent_language.lower() == "hinglish" else agent_language

    history = []
    is_speaking = False
    filler_cache = {}
    last_stock = {}
    call_state = INTRO
    last_bot_response = greeting
    is_generic_agent = len(local_call_data.get("skus", [])) == 0
    interrupt_event = asyncio.Event()
    stream_sid = None
    stream_ready_event = asyncio.Event()
    vad = SileroVAD()
    is_initial_greeting = True

    # Fillers & TTS Prep
    from services.tts import get_tts_cache_key, TTS_CACHE, update_tts_cache

    async def speak(text, is_filler=False, language=None):
        nonlocal is_speaking
        if not stream_sid:
            log.info(f"[SPEAK] Waiting for SID to speak: {text[:20]}...")
            try:
                await asyncio.wait_for(stream_ready_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                log.warning("[SPEAK] Timeout waiting for SID. Proceeding anyway.")
            
        is_speaking = True
        interrupt_event.clear()
        target_tts_lang = language or tts_language
        prepared = prepare_for_tts(text)
        cache_key = get_tts_cache_key(prepared, voice_id, target_tts_lang)

        audio = None
        if cache_key in TTS_CACHE:
            audio = TTS_CACHE[cache_key]
            log.info(f"[SPEAK] Cache HIT: {text[:40]} | Bytes: {len(audio)}")
            # 🚀 CHUNKING: Send cached audio in small parts to prevent Plivo overflow
            chunk_size = 320 # 40ms
            try:
                for i in range(0, len(audio), chunk_size):
                    if interrupt_event.is_set(): break
                    chunk = audio[i:i+chunk_size]
                    msg = {
                        "event": "playAudio",
                        "media": {
                            "payload": base64.b64encode(chunk).decode(),
                            "contentType": "audio/x-mulaw",
                            "sampleRate": 8000
                        },
                        "streamSid": stream_sid
                    }
                    await websocket.send_text(json.dumps(msg))
                    # Buffer management: sleep 0.04s to match real-time better
                    await asyncio.sleep(0.04)
            except Exception as e:
                log.error(f"[STREAM] WS Send Error: {e}")
        else:
            log.info(f"[SPEAK] Streaming TTS: {text[:40]}")
            audio = await stream_tts_to_plivo(text, TTSContext(), websocket, voice_id=voice_id, language=target_tts_lang, stream_sid=stream_sid)
            if not audio:
                log.info(f"[SPEAK] Fallback TTS: {text[:40]}")
                audio = await omnivoice_tts(text, voice_id=voice_id, language=target_tts_lang)
                if audio:
                    msg = {
                        "event": "playAudio",
                        "media": {
                            "payload": base64.b64encode(audio).decode(),
                            "contentType": "audio/x-mulaw",
                            "sampleRate": 8000
                        },
                        "streamSid": stream_sid
                    }
                    await websocket.send_text(json.dumps(msg))

        if not audio:
            is_speaking = False
            return

        # Wait for actual playback to finish (heuristic)
        duration = len(audio) / 8000
        try:
            await asyncio.wait_for(interrupt_event.wait(), timeout=duration)
        except asyncio.TimeoutError: pass
        if interrupt_event.is_set():
            try: await websocket.send_text(json.dumps({"event": "clearAudio", "streamSid": stream_sid, "streamId": stream_sid}))
            except: pass
        is_speaking = False
        vad.reset()

    async def _process_text(text, target_lang=None):
        nonlocal call_state, last_bot_response, last_stock
        full_text = ""
        last_metadata = None
        
        # Log to DB/History
        if call_id: add_message(call_id, "user", text)
        history.append({"role": "user", "content": text})

        async for chunk, is_final, metadata in get_agent_response(
            call_state, last_bot_response, history, text, local_call_data, last_stock,
            system_prompt_override=system_prompt_override, is_generic=is_generic_agent
        ):
            if chunk:
                full_text += chunk
                asyncio.create_task(speak(chunk, language=target_lang))
            if is_final: last_metadata = metadata

        if last_metadata:
            llm_text, next_state, terminate_call, stock = last_metadata
            call_state = next_state
            last_bot_response = llm_text
            if stock: last_stock.update(stock)
            history.append({"role": "assistant", "content": llm_text})
            if call_id: add_message(call_id, "assistant", llm_text)
            
            if terminate_call:
                await asyncio.sleep(1.5)
                try: plivo_client.calls.group_hangup(call_uuid)
                except: pass
                return "TERMINATE"
        return "CONTINUE"

    async def _init_and_greet():
        nonlocal is_initial_greeting
        log.info("[GREET] Session init started...")
        await stt_connect()
        # Warmup greeting
        g_key = get_tts_cache_key(greeting, voice_id, agent_language)
        if g_key not in TTS_CACHE:
            log.info("[GREET] Pre-generating greeting...")
            audio = await omnivoice_tts(greeting, voice_id=voice_id, language=agent_language)
            if audio: update_tts_cache(greeting, audio, voice_id=voice_id, language=agent_language)
        
        is_initial_greeting = True
        await speak(greeting)
        is_initial_greeting = False
        
        # 🚀 Fix: Add greeting to history so LLM knows context
        history.append({"role": "assistant", "content": greeting})
        nonlocal last_bot_response
        last_bot_response = greeting
        if call_id: add_message(call_id, "assistant", greeting)

    asyncio.create_task(_init_and_greet())

    async def audio_forwarder():
        nonlocal stream_sid
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")
                if event == "start":
                    sd = msg.get("start", {})
                    stream_sid = sd.get("stream_id") or sd.get("streamId") or sd.get("stream_sid") or sd.get("streamSid")
                    log.info(f"[PLIVO] SID Detected: {stream_sid}")
                    stream_ready_event.set()
                elif event == "media":
                    payload = msg.get("media", {}).get("payload", "")
                    if payload: await send_audio_chunk(base64.b64decode(payload))
                elif event == "stop": break
        except Exception: pass

    async def transcript_loop():
        while True:
            try:
                text = await get_final_transcript(timeout=5)
                if not text: continue
                
                if is_speaking:
                    # Allow user to interrupt the greeting specifically
                    if len(text.split()) >= 2:
                        log.info(f"[INTERRUPT] User said: {text}")
                        interrupt_event.set()
                        while is_speaking: await asyncio.sleep(0.01)
                    else: continue
                
                log.info(f"[USER] {text}")
                result = await _process_text(text, target_lang=tts_language)
                if result == "TERMINATE": break
            except Exception: pass

    try:
        await asyncio.wait([asyncio.create_task(audio_forwarder()), asyncio.create_task(transcript_loop())], return_when=asyncio.FIRST_COMPLETED)
    except: pass
    
    if call_id:
        update_call(call_id, status="completed", ended_at=datetime.utcnow().isoformat()+"Z",
                   duration_sec=int(time.time()-start_connect), metadata=json.dumps({"stock":last_stock}))
    
    await stt_disconnect()
    try:
        # Check if websocket state is suitable for closing
        if websocket.client_state != WebSocketDisconnect:
            await websocket.close()
    except: pass
