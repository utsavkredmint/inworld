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

    # Initialize scope variables
    user_data = None
    user_name = None

    # Parallel data loading
    async def load_user_data_task():
        nonlocal user_data, user_name
        try:
            from pathlib import Path
            dummy_path = Path(__file__).parent.parent / "dummy_data.json"
            if dummy_path.exists():
                with open(dummy_path, "r", encoding="utf-8") as f:
                    users_list = json.load(f)
                    target_number = to_number if to_number.startswith("+") else "+" + to_number
                    for u in users_list:
                        if u.get("phone") and target_number.endswith(u["phone"]):
                            user_data = u
                            user_name = u.get("name")
                            break
            
            if user_name and any('a' <= char.lower() <= 'z' for char in user_name):
                try:
                    async with aiohttp.ClientSession() as translate_session:
                        async with translate_session.get(f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q={user_name}', timeout=1.5) as res:
                            if res.status == 200:
                                data = await res.json()
                                user_name = data[0][0][0]
                except Exception: pass
        except Exception: pass

    user_data_future = asyncio.create_task(load_user_data_task())
    await user_data_future
    
    from config import CALL_DATA as GLOBAL_CALL_DATA
    local_call_data = GLOBAL_CALL_DATA.copy()
    if user_data:
        local_call_data["skus"] = user_data.get("skus", GLOBAL_CALL_DATA["skus"])
        local_call_data["current_time"] = user_data.get("current_time", GLOBAL_CALL_DATA["current_time"])

    agent = None
    db_call = None
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
                    plivo_client.calls.record(call_uuid=call_uuid, file_format="mp3",
                        time_limit=3600,
                        callback_url=f"{SERVER_URL}/api/plivo/record_callback?call_id={call_id}",
                        callback_method="POST")
                except Exception: pass

    if user_name:
        if "नमस्ते, O2R से" in greeting:
            greeting = greeting.replace("नमस्ते, O2R से", f"नमस्ते {user_name}, O2R से")
        elif "नमस्ते" in greeting:
            greeting = greeting.replace("नमस्ते", f"नमस्ते {user_name}")

    # Voice & Identity Setup
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
    session = aiohttp.ClientSession()
    stream_sid = None
    first_chunk_ts = None
    vad = SileroVAD()
    speak_start_ts = 0
    stream_ready_event = asyncio.Event() # New event for sync

    # 🔥 LATENCY PREP: Greeting & Fillers
    from services.tts import update_tts_cache, get_tts_cache_key, TTS_CACHE
    
    async def prepare_fillers():
        fillers = ["जी", "जी बताइए", "जी देख रही हूँ"]
        for f in fillers:
            try:
                key = get_tts_cache_key(f, voice_id=voice_id, language=agent_language)
                if key in TTS_CACHE:
                    filler_cache[f] = TTS_CACHE[key]
                    continue
                audio = await omnivoice_tts(f, voice_id=voice_id, language=agent_language, num_inference_steps=12)
                if audio:
                    update_tts_cache(f, audio, voice_id=voice_id, language=agent_language)
                    filler_cache[f] = audio
            except Exception: pass

    async def prepare_greeting():
        log.info(f"[GREET] Generating: {greeting[:30]}...")
        audio = await omnivoice_tts(greeting, voice_id=voice_id, language=agent_language, num_inference_steps=12)
        if audio:
            update_tts_cache(greeting, audio, voice_id=voice_id, language=agent_language)

    g_key = get_tts_cache_key(greeting, voice_id, agent_language)
    if g_key not in TTS_CACHE:
        greeting_prep_task = asyncio.create_task(prepare_greeting())
    else:
        greeting_prep_task = asyncio.create_task(asyncio.sleep(0))
        
    asyncio.create_task(prepare_fillers())

    from call_sessions import get_session
    pre_session = get_session(call_id) if call_id else None
    tts_ctx = pre_session["tts_ctx"] if pre_session else TTSContext()
    stt_pre_connected = bool(pre_session and pre_session.get("stt_ready"))
    is_initial_greeting = True

    # ── Helpers ──
    async def _play_filler():
        try:
            if not filler_cache: return
            import random
            choice = random.choice(list(filler_cache.keys()))
            audio = filler_cache[choice]
            payload = base64.b64encode(audio).decode("utf-8")
            msg = {"event": "media", "media": {"payload": payload}}
            if stream_sid: msg["streamSid"] = stream_sid
            await websocket.send_text(json.dumps(msg))
        except Exception: pass

    async def speak(text, is_filler=False, language=None):
        nonlocal is_speaking, speak_start_ts
        # 🚀 SYNC: Wait for streamSid before sending ANY audio
        if not stream_sid:
            log.info("[SPEAK] Waiting for streamSid synchronization...")
            await stream_ready_event.wait()
            
        tts_start = time.time()
        is_speaking = True
        speak_start_ts = time.time()
        interrupt_event.clear()

        target_tts_lang = language or tts_language
        prepared = prepare_for_tts(text)
        cache_key = get_tts_cache_key(prepared, voice_id, target_tts_lang)

        if cache_key in TTS_CACHE:
            audio = TTS_CACHE[cache_key]
            try:
                msg = {"event": "media", "media": {"payload": base64.b64encode(audio).decode()}}
                if stream_sid: msg["streamSid"] = stream_sid
                await websocket.send_text(json.dumps(msg))
            except: pass
        else:
            audio = await stream_tts_to_plivo(text, tts_ctx, websocket, voice_id=voice_id, language=target_tts_lang)
            if not audio:
                audio = await omnivoice_tts(text, voice_id=voice_id, language=target_tts_lang)
                if audio:
                    try:
                        msg = {"event": "media", "media": {"payload": base64.b64encode(audio).decode()}}
                        if stream_sid: msg["streamSid"] = stream_sid
                        await websocket.send_text(json.dumps(msg))
                    except: pass

        if not audio:
            is_speaking = False
            return

        duration = len(audio) / 8000
        try:
            await asyncio.wait_for(interrupt_event.wait(), timeout=duration)
        except asyncio.TimeoutError: pass
        if interrupt_event.is_set():
            try: await websocket.send_text(json.dumps({"event": "clearAudio"}))
            except: pass
        is_speaking = False
        vad.reset()

    async def _process_text(text, target_lang=None):
        nonlocal call_state, last_bot_response, last_stock
        from services.llm import get_agent_response
        full_text = ""
        last_metadata = None
        
        async for chunk, is_final, metadata in get_agent_response(
            call_state, last_bot_response, history, text, local_call_data, last_stock,
            system_prompt_override=system_prompt_override, is_generic=is_generic_agent
        ):
            if chunk:
                full_text += chunk
                asyncio.create_task(speak(chunk, language=target_lang))
            if is_final:
                last_metadata = metadata

        if last_metadata:
            llm_text, next_state, terminate_call, stock = last_metadata
            if stock: last_stock.update(stock)
            
            cur_order = STATE_ORDER.get(call_state, 0)
            new_order = STATE_ORDER.get(next_state, 0)
            if new_order < cur_order: next_state = call_state
            if call_state != "INTRO" and next_state == "INTRO": next_state = call_state
            
            call_state = next_state
            last_bot_response = llm_text
            if call_id:
                add_message(call_id, "user", text)
                add_message(call_id, "assistant", llm_text)
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": llm_text})

            if terminate_call:
                try:
                    await asyncio.sleep(2)
                    plivo_client.calls.group_hangup(call_uuid)
                except: pass
                return "TERMINATE"
        return "CONTINUE"

    async def _init_and_greet():
        nonlocal is_initial_greeting
        setup_tasks = []
        if not stt_pre_connected: setup_tasks.append(stt_connect())
        if not (pre_session and pre_session.get("tts_ctx")): setup_tasks.append(tts_ctx.open())
        setup_future = asyncio.gather(*setup_tasks) if setup_tasks else asyncio.sleep(0)
        
        await greeting_prep_task
        
        # 🚀 SYNC: Wait for Plivo stream to be fully ready before greeting
        if not stream_sid:
            log.info("[GREET] Waiting for streamSid before speaking...")
            await stream_ready_event.wait()
            
        is_initial_greeting = True
        await speak(greeting)
        is_initial_greeting = False
        if call_id: add_message(call_id, "assistant", greeting)
        await setup_future
        from services.tts import omnivoice_tts # Ensure available
        # Pre-cache SKUs logic removed for brevity but could be added back
        
    asyncio.create_task(_init_and_greet())

    async def audio_forwarder():
        nonlocal first_chunk_ts, stream_sid
        from services import stt as stt_module
        while stt_module._dg_ws is None or stt_module._dg_ws.closed:
            await asyncio.sleep(0.05)
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                if msg.get("event") == "start":
                    stream_sid = msg.get("start", {}).get("streamSid")
                    log.info(f"[PLIVO] Stream started with SID: {stream_sid}")
                    stream_ready_event.set() # Release any waiting audio calls
                if msg.get("event") == "media":
                    payload = msg.get("media", {}).get("payload", "")
                    if payload:
                        chunk = base64.b64decode(payload)
                        await send_audio_chunk(chunk)
                elif msg.get("event") == "stop": break
        except Exception: pass

    async def transcript_loop():
        while True:
            try:
                text = await get_final_transcript(timeout=10)
                if not text: continue
                if is_speaking:
                    if is_initial_greeting: continue
                    if len(text.split()) >= 2:
                        interrupt_event.set()
                        while is_speaking: await asyncio.sleep(0.01)
                    else: continue
                
                asyncio.create_task(_play_filler())
                result = await _process_text(text, target_lang=tts_language)
                if result == "TERMINATE": break
            except Exception: pass

    f_task = asyncio.create_task(audio_forwarder())
    t_task = asyncio.create_task(transcript_loop())
    await asyncio.wait([f_task, t_task], return_when=asyncio.FIRST_COMPLETED)
    
    if call_id:
        update_call(call_id, status="completed", ended_at=datetime.utcnow().isoformat()+"Z",
                   duration_sec=int(time.time()-start_connect), metadata=json.dumps({"stock":last_stock}))
    await stt_disconnect()
    await tts_ctx.close()
    await session.close()
