import asyncio
import base64
import json
import logging
import time
import random
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
                    # 🚀 Background record - fire and forget
                    asyncio.create_task(asyncio.to_thread(plivo_client.calls.record, 
                        call_uuid=call_uuid, file_format="mp3", time_limit=3600,
                        callback_url=f"{SERVER_URL}/api/plivo/record_callback?call_id={call_id}"))
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
    
    # 🚀 SEQUENCE TRACKING: Ensures audio chunks play in order
    current_turn_id = 0
    playback_index = 0
    playback_cond = asyncio.Condition()
    turn_in_progress = False

    # Fillers & TTS Prep
    from services.tts import get_tts_cache_key, TTS_CACHE, update_tts_cache

    async def speak(text, index=0, turn_id=0, language=None):
        nonlocal is_speaking, playback_index, current_turn_id
        try:
            if turn_id != current_turn_id: return
            
            if not stream_sid:
                log.info(f"[SPEAK] Waiting for SID to speak: {text[:20]}...")
                try:
                    await asyncio.wait_for(stream_ready_event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    log.warning("[SPEAK] Timeout waiting for SID. Proceeding anyway.")
                
            is_speaking = True
            target_tts_lang = language or tts_language
            prepared = prepare_for_tts(text)
            cache_key = get_tts_cache_key(prepared, voice_id, target_tts_lang)
            
            audio = None
            if cache_key in TTS_CACHE:
                audio = TTS_CACHE[cache_key]
                log.info(f"[SPEAK] Cache HIT: {text[:40]} | Bytes: {len(audio)}")
            else:
                if turn_id != current_turn_id: return
                log.info(f"[SPEAK] Generating TTS: {text[:40]}")
                audio = await omnivoice_tts(text, voice_id=voice_id, language=target_tts_lang)
                if audio:
                    update_tts_cache(text, audio, voice_id=voice_id, language=target_tts_lang)

            if turn_id != current_turn_id: return

            if not audio:
                log.warning(f"[SPEAK] No audio generated for: {text[:40]}")
                # Still need to increment index to not block the chain
                async with playback_cond:
                    playback_index += 1
                    playback_cond.notify_all()
                return

            # 🚀 SEQUENCE SYNC: Wait for our turn within the current Turn ID
            async with playback_cond:
                log.info(f"[SPEAK] T[{turn_id}] Chunk {index} ready. Waiting (Current: {playback_index})")
                while playback_index < index and turn_id == current_turn_id:
                    await playback_cond.wait()
                
                if turn_id != current_turn_id:
                    return

                chunk_size = 320 # 40ms
                try:
                    for i in range(0, len(audio), chunk_size):
                        if turn_id != current_turn_id: break
                        if websocket.client_state == WebSocketDisconnect: break 
                        
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
                        await asyncio.sleep(0.04) # 40ms buffer sleep
                except Exception as e:
                    log.error(f"[STREAM] WS Send Error: {e}")

            # 🚀 FINAL SYNC: Increment index only if turn matches
            async with playback_cond:
                if turn_id == current_turn_id:
                    playback_index += 1
                    playback_cond.notify_all()
        finally:
            is_speaking = False

    async def _process_text(text, target_lang=None, start_index=0):
        nonlocal call_state, last_bot_response, last_stock, playback_index, current_turn_id, turn_in_progress
        turn_in_progress = True
        try:
            full_text = ""
            last_metadata = None
            
            # Log to DB/History
            if call_id: asyncio.create_task(asyncio.to_thread(add_message, call_id, "user", text))
            history.append({"role": "user", "content": text})

            chunk_idx = start_index 
            t_id = current_turn_id

            async for chunk, is_final, metadata in get_agent_response(
                state=call_state,
                last_bot_msg=last_bot_response,
                history=history,
                user_text=text,
                call_data=local_call_data,
                current_stock=last_stock,
                system_prompt_override=system_prompt_override,
                is_generic=is_generic_agent
            ):
                if t_id != current_turn_id: break
                if chunk:
                    full_text += chunk
                    # 🚀 PARALLEL GPU: Fire and forget each chunk
                    asyncio.create_task(speak(chunk, index=chunk_idx, turn_id=t_id, language=target_lang))
                    chunk_idx += 1
                
                if is_final: last_metadata = metadata

            if last_metadata:
                response, next_state, terminate, updated_stock = last_metadata
                last_bot_response = response
                call_state = next_state
                if updated_stock: last_stock.update(updated_stock)
                history.append({"role": "assistant", "content": response})
                if call_id: asyncio.create_task(asyncio.to_thread(add_message, call_id, "assistant", response))
                
                if terminate: return "TERMINATE"
            return "CONTINUE"
        finally:
            turn_in_progress = False

    async def _init_and_greet():
        nonlocal is_initial_greeting
        log.info("[GREET] Session init started...")
        await stt_connect()

        # 🚀 BACKGROUND WARMUP: Pre-cache greeting for THIS specific agent voice
        g_key = get_tts_cache_key(greeting, voice_id, agent_language)
        if g_key not in TTS_CACHE:
            log.info("[GREET] Pre-generating greeting...")
            audio = await omnivoice_tts(greeting, voice_id=voice_id, language=agent_language)
            if audio: update_tts_cache(greeting, audio, voice_id=voice_id, language=agent_language)
        
        is_initial_greeting = True
        await speak(greeting, index=0)
        is_initial_greeting = False
        
        history.append({"role": "assistant", "content": greeting})
        nonlocal last_bot_response
        last_bot_response = greeting
        if call_id: asyncio.create_task(asyncio.to_thread(add_message, call_id, "assistant", greeting))

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
        nonlocal current_turn_id, playback_index
        while True:
            try:
                text = await get_final_transcript(timeout=5)
                if not text: continue
                
                if is_speaking:
                    # Allow user to interrupt the greeting specifically
                    if len(text.split()) >= 2:
                        log.info(f"[INTERRUPT] User said: {text}")
                        interrupt_event.set()
                        # 🚀 CLEAR QUEUE: Wake up all waiting speak tasks so they can exit
                        async with playback_cond:
                            playback_cond.notify_all()
                    else: continue
                
                log.info(f"[USER] {text}")
                
                # 🚀 HELLO/JI FILTER: Ignore contextless interjections mid-call to prevent LLM confusion
                clean_text = text.lower().strip().replace(".", "").replace("।", "").replace("!", "").replace("?", "")
                if clean_text in ["hello", "जी", "हां जी", "सुनिए", "suniye", "hello?", "hello hello"] and len(history) > 1:
                    log.info(f"[FILTER] Ignoring repetitive '{text}' to keep flow stable.")
                    continue

                # 🚀 NEW TURN: Increment turn_id and reset index
                async with playback_cond:
                    current_turn_id += 1
                    playback_index = 0
                    interrupt_event.set() # Stop any active speaker loops
                    playback_cond.notify_all()
                
                # Allow a small gap for old tasks to detect current_turn_id change
                await asyncio.sleep(0.05) 
                interrupt_event.clear()

                # Actual response starts at index 0
                result = await _process_text(text, target_lang=tts_language, start_index=0)
                if result == "TERMINATE": break
            except Exception: pass

    try:
        await asyncio.wait([asyncio.create_task(audio_forwarder()), asyncio.create_task(transcript_loop())], return_when=asyncio.FIRST_COMPLETED)
    except: pass
    
    if call_id:
        asyncio.create_task(asyncio.to_thread(update_call, call_id, status="completed", 
                   ended_at=datetime.utcnow().isoformat()+"Z",
                   duration_sec=int(time.time()-start_connect), 
                   metadata=json.dumps({"stock":last_stock})))
    
    # 🚀 GRACEFUL TERMINATION: Wait for LLM thought AND audio playback to finish
    # Otherwise the call cuts off during gaps between sentences
    while turn_in_progress or is_speaking:
        await asyncio.sleep(0.1)
        
    await stt_disconnect()
    try:
        # Check if websocket state is suitable for closing
        if websocket.client_state != WebSocketDisconnect:
            await websocket.close()
    except: pass
