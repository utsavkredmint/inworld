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
    log.info(f"[STREAM] Params: uuid={call_uuid}, id={call_id}, num={to_number}")
    log.info(f"[STREAM] Starting session for call_uuid={call_uuid} and call_id={call_id}")
    
    start_connect = time.time()
    try:
        await websocket.accept()
        log.info(f"[STREAM] WebSocket ACCEPTED for {call_uuid}")
    except Exception as e:
        log.error(f"[STREAM] Failed to accept WebSocket: {e}")
        return

    log.info(f"Socket Active for {call_uuid} (call_id={call_id})")

    # 1. Load User Data First (to get per-caller SKUs and Time)
    user_data = None
    user_name = None
    try:
        from pathlib import Path
        dummy_path = Path(__file__).parent.parent / "dummy_data.json"
        with open(dummy_path, "r", encoding="utf-8") as f:
            users_list = json.load(f)
            target_number = to_number if to_number.startswith("+") else "+" + to_number
            for u in users_list:
                if u.get("phone") and target_number.endswith(u["phone"]):
                    user_data = u
                    user_name = u.get("name")
                    break
    except Exception as e:
        log.warning(f"[DUMMY DATA] Error reading user list: {e}")

    # Build local call data
    from config import CALL_DATA as GLOBAL_CALL_DATA
    local_call_data = GLOBAL_CALL_DATA.copy()
    if user_data:
        local_call_data["skus"] = user_data.get("skus", GLOBAL_CALL_DATA["skus"])
        local_call_data["current_time"] = user_data.get("current_time", GLOBAL_CALL_DATA["current_time"])
        log.info(f"[DUMMY] Matched {to_number} to user: {user_name}")

    if user_name and any('a' <= char.lower() <= 'z' for char in user_name):
        try:
            async with aiohttp.ClientSession() as translate_session:
                async with translate_session.get(f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q={user_name}', timeout=2) as res:
                    if res.status == 200:
                        data = await res.json()
                        translated = data[0][0][0]
                        user_name = translated
        except Exception as e:
            log.warning(f"[TRANSLATE] Failed to transliterate name '{user_name}': {e}")

    # 2. Load Agent Config from DB
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
                
                # Enforce Strict Dashboard Primacy
                log.info(f"[SESSION] Active Agent ID: {db_call['agent_id']} | Name: {agent.get('name', 'Unknown')}")
                
                # Mode Detection: Only inject SKUs if it's an 'Inventory' specific agent
                # (We check if the prompt actually mentions SKUs or if we are in a campaign)
                skus = local_call_data.get("skus", [])
                if skus and system_prompt_override and ("SKU" in system_prompt_override or "inventory" in system_prompt_override.lower()):
                    skus_str = ", ".join(skus)
                    current_time_str = local_call_data.get("current_time", "")
                    sku_info = f"\n*** DATA FOR THIS CALL:\n- SKUS: {skus_str}\n- TIME: {current_time_str}\n"
                    system_prompt_override = sku_info + system_prompt_override
                    log.info(f"[AGENT] SKU Injection active for Inventory context.")
                else:
                    log.info(f"[AGENT] Strict Mode: Using raw Dashboard prompt for persona.")
                
                update_call(call_id, status="in-progress", started_at=datetime.utcnow().isoformat() + "Z")

                try:
                    from config import SERVER_URL
                    plivo_client.calls.record(
                        call_uuid=call_uuid, file_format="mp3",
                        callback_url=f"{SERVER_URL}/api/plivo/record_callback?call_id={call_id}",
                        callback_method="POST",
                    )
                except Exception:
                    pass

    # 3. Dynamic Name Injection into Prompt & Greeting
    if user_name:
        if "नमस्ते, O2R से" in greeting:
            greeting = greeting.replace("नमस्ते, O2R से", f"नमस्ते {user_name}, O2R से")
        elif "नमस्ते" in greeting:
            greeting = greeting.replace("नमस्ते", f"नमस्ते {user_name}")

        name_injection = f"The person you are calling is {user_name}. Use their name naturally if appropriate."
        if system_prompt_override:
            system_prompt_override += f"\n\n*** DATA: Caller Name is {user_name}."
        else:
            from services.llm import build_agent_prompt
            system_prompt_override = build_agent_prompt(local_call_data) + f"\n\n*** DATA: Caller Name is {user_name}."

    # 🌍 Voice & Language Identity
    agent_language = agent.get("language", "hindi") if agent else "hindi"
    voice_id = agent.get("voice") if agent else None
    
    history = []
    is_speaking = False
    filler_cache = {}
    stream_sid = None
    
    # 🔗 Pick up pre-cached greeting and agent data
    from call_sessions import get_session
    pre_session = get_session(call_id) if call_id else None
    
    agent = pre_session["agent"] if pre_session else agent
    greeting = agent.get("greeting", GREETING) if agent else GREETING
    greeting_task = pre_session["greeting_task"] if pre_session else greeting_task
    
    last_bot_response = greeting
    is_generic_agent = len(local_call_data.get("skus", [])) == 0
    call_state = INTRO
    interrupt_event = asyncio.Event()
    session = aiohttp.ClientSession()
    first_chunk_ts = None
    vad = SileroVAD()
    speak_start_ts = 0
    stream_ready = asyncio.Event() # 🔥 NEW: Sync event for Plivo connection
    tts_ctx = pre_session["tts_ctx"] if pre_session else TTSContext()
    stt_pre_connected = bool(pre_session and pre_session.get("stt_ready"))
    last_stock = {}
    
    # 🌍 Voice & Language Identity
    agent_language = agent.get("language", "hindi") if agent else "hindi"
    # Alias 'hinglish' to 'hi' for the TTS engine
    tts_language = "hi" if agent_language.lower() == "hinglish" else agent_language
    voice_id = agent.get("voice") if agent else None
    log.info(f"[TTS] Synthesizing with voice: {voice_id or 'default'} in language: {agent_language} (target: {tts_language})")

    # ── Internal Helpers ──
    async def _play_filler():
        try:
            if not filler_cache: return
            import random
            choice = random.choice(list(filler_cache.keys()))
            audio = filler_cache[choice]
            log.info(f"[FILLER] Injecting instant filler: '{choice}'")
            payload = base64.b64encode(audio).decode("utf-8")
            msg = {
                "event": "media",
                "media": {"payload": payload}
            }
            if stream_sid: msg["streamSid"] = stream_sid
            await websocket.send_text(json.dumps(msg))
        except Exception as e:
            log.error(f"[FILLER] Injection failed: {e}")

    async def speak(text, is_filler=False, language=None, steps=35):
        nonlocal is_speaking, speak_start_ts
        tts_start = time.time()
        is_speaking = True
        speak_start_ts = time.time()
        interrupt_event.clear()

        # Target language mapping
        target_tts_lang = language or tts_language or agent_language
        prepared = prepare_for_tts(text)
        cache_key = f"{prepared}_{voice_id}_{target_tts_lang}"
        audio = None

        # 1. OPTIMIZATION: Wait for Plivo Link before doing ANYTHING
        await stream_ready.wait()

        # 2. CACHE HIT
        if cache_key in TTS_CACHE:
            audio = TTS_CACHE[cache_key]
            log.info(f"[SPEAK] Cache HIT for: {text[:40]}")
            try:
                msg = {
                    "event": "media",
                    "media": {"payload": base64.b64encode(audio).decode()}
                }
                if stream_sid: msg["streamSid"] = stream_sid
                await websocket.send_text(json.dumps(msg))
            except Exception as e:
                log.error(f"[SPEAK] Cache playback failed: {e}")
        else:
            # 3. GENERATION
            log.info(f"[SPEAK] Streaming TTS for: {text[:40]}... (steps={steps})")
            audio = await omnivoice_tts(text, voice_id=voice_id, language=target_tts_lang, steps=steps)
            if audio:
                try:
                    msg = {
                        "event": "media",
                        "media": {"payload": base64.b64encode(audio).decode()}
                    }
                    if stream_sid: msg["streamSid"] = stream_sid
                    await websocket.send_text(json.dumps(msg))
                except Exception as e:
                    log.error(f"[SPEAK] Generated playback failed: {e}")

        tts_ms = int((time.time() - tts_start) * 1000)
        if not audio:
            log.error(f"[SPEAK] TTS failed after {tts_ms}ms!")
            is_speaking = False
            return

        duration = len(audio) / 8000
        log.info(f"[TTS] {tts_ms}ms | audio={len(audio)}bytes | playback={int(duration*1000)}ms")

        try:
            await asyncio.wait_for(interrupt_event.wait(), timeout=duration)
        except asyncio.TimeoutError:
            pass
            
        if interrupt_event.is_set():
            try:
                await websocket.send_text(json.dumps({"event": "clearAudio"}))
                log.info("[INTERRUPT] clearAudio sent")
            except:
                pass
        is_speaking = False
        vad.reset()

    async def _process_text(text, target_lang=None):
        """Process a transcript: LLM → TTS SENTENCE-BY-SENTENCE."""
        nonlocal call_state, last_bot_response, last_stock

        if not target_lang:
            target_lang = tts_language

        history.append({"role": "user", "content": text})
        
        # 🚀 STREAMING ENGINE: LLM → TTS SENTENCE BY SENTENCE
        llm_start = time.time()
        from services.llm import get_streaming_agent_response
        
        full_resp = ""
        current_sentence_index = 0
        
        async for msg_type, content in get_streaming_agent_response(
            call_state, last_bot_response, history, text, local_call_data, last_stock,
            system_prompt_override=system_prompt_override,
            is_generic=is_generic_agent
        ):
            if msg_type == "sentence":
                log.info(f"[STREAM-LLM] Sentence {current_sentence_index+1} ready: {content[:30]}...")
                # Start TTS for this sentence immediately!
                # Fast-Start: We use a lower step count for the first sentence to start FAST
                # Note: We'll pass steps=22 to omnivoice_tts via speak()
                asyncio.create_task(speak(content, language=target_lang, steps=(22 if current_sentence_index == 0 else 35)))
                full_resp += " " + content
                current_sentence_index += 1
            
            elif msg_type == "json":
                # Final state/stock updates
                next_state = content.get("state", call_state)
                terminate_call = content.get("terminate", False)
                stock = content.get("stock", {})
                if stock:
                    last_stock.update(stock)
                
                # State guard
                cur_order = STATE_ORDER.get(call_state, 0)
                new_order = STATE_ORDER.get(next_state, 0)
                if new_order >= cur_order:
                    call_state = next_state
                
                llm_ms = int((time.time() - llm_start) * 1000)
                log.info(f"[STREAM-DONE] LLM finished in {llm_ms}ms. Next State: {call_state}")
                
                # FALLBACK: If we haven't spoken anything during the stream, speak the full response now
                final_resp_from_json = content.get("response", "")
                if current_sentence_index == 0 and final_resp_from_json:
                    log.info("[FALLBACK] Stream gave no sentences. Speaking full response from JSON.")
                    asyncio.create_task(speak(final_resp_from_json, language=target_lang))
                    full_resp = final_resp_from_json

                if terminate_call:
                    log.info(f"[TERMINATE] Call will end after speech.")
                    # Hang up after a safety buffer
                    asyncio.create_task(asyncio.sleep(8)).add_done_callback(lambda _: plivo_client.calls.group_hangup(call_uuid))

        last_bot_response = full_resp.strip()
        if call_id:
            add_message(call_id, "user", text)
            add_message(call_id, "assistant", last_bot_response)

        history.append({"role": "assistant", "content": last_bot_response})

    async def _pre_cache_skus():
        """Pre-generate TTS for all SKU questions in parallel — so first response is instant."""
        skus = local_call_data.get("skus", [])
        templates = []
        for sku in skus:
            # Map SKU to Hindi name + unit for question
            if "Khajoor Pouch" in sku:
                hindi = f"खजूर पाउच के कितने pouches बचे हैं"
            elif "Khajoor Dispenser" in sku:
                hindi = f"खजूर डिस्पेंसर के कितने dispensers बचे हैं"
            elif "Rajnigandha" in sku:
                parts = sku.replace("Rajnigandha", "रजनीगंधा")
                hindi = f"{parts} के कितने packs बचे हैं"
            else:
                hindi = f"{sku} का stock क्या है"
            templates.append(f"ठीक है, {hindi}?")
        # Also cache common short responses
        templates += [
            "ठीक है",
            "अच्छा",
            "धन्यवाद"
        ]
        log.info(f"[CACHE] Pre-generating TTS for {len(templates)} phrases SEQUENTIALLY...")
        # Sequential pre-caching to avoid GPU overloading
        for t in templates:
            try:
                # Add a small delay between tasks to prioritize real-time replies
                await asyncio.sleep(0.5)
                await omnivoice_tts(t, voice_id=voice_id, language=tts_language)
            except Exception as e:
                log.warning(f"[CACHE] Pre-cache failed for '{t}': {e}")
        log.info("[CACHE] Background pre-caching complete.")

    async def _init_and_greet():
        # 🔗 Start setup (ONLY if not already pre-connected)
        setup_tasks = []
        if not stt_pre_connected:
            setup_tasks.append(stt_connect())
        if not (pre_session and pre_session.get("tts_ctx")):
            setup_tasks.append(tts_ctx.open())
            
        setup_future = asyncio.gather(*setup_tasks) if setup_tasks else asyncio.sleep(0)
        
        # 🚀 Start speaking the greeting as soon as it's ready
        try:
            # We already started greeting_task at the top of websocket_endpoint
            greeting_audio = await asyncio.wait_for(greeting_task, timeout=5.0)
            if greeting_audio:
                log.info("[GREET] OmniVoice Greeting ready, speaking now.")
                await speak(greeting)
            else:
                log.warning("[GREET] Greeting generation failed, speaking fallback.")
                await speak(greeting)
        except Exception as e:
            log.error(f"[GREET] Greeting error: {e}")
            await speak(greeting)

        if call_id:
            add_message(call_id, "assistant", greeting)
        
        # Ensure any remaining setup finishes
        await setup_future
        log.info("[SETUP] Call identity and streaming ready.")
        
        async def delayed_caching():
            # Wait 8 seconds so the first real user interaction gets 100% GPU priority
            await asyncio.sleep(8.0)
            log.info("[CACHE] Starting background pre-generation task...")
            
            # Pre-cache in background while session is active
            asyncio.create_task(_pre_cache_skus())
            
            # Pre-generate Fillers for 100ms latency
            fillers = ["जी", "जी बताइए", "जी देख रही हूँ"]
            for f in fillers:
                try:
                    audio = await omnivoice_tts(f, voice_id=voice_id, language=tts_language)
                    if audio: filler_cache[f] = audio
                except: pass
            log.info(f"[CACHE] Ready with {len(filler_cache)} instant fillers")

        asyncio.create_task(delayed_caching())

    asyncio.create_task(_init_and_greet())


    async def audio_forwarder():
        nonlocal first_chunk_ts
        # Wait until STT is connected before forwarding audio
        from services import stt as stt_module
        wait_count = 0
        while stt_module._dg_ws is None or stt_module._dg_ws.closed:
            await asyncio.sleep(0.05)
            wait_count += 1
            if wait_count > 60:  # 3 second timeout
                log.warning("[AUDIO] STT not ready after 3s, proceeding anyway")
                break
        if wait_count > 0:
            log.info(f"[AUDIO] Waited {wait_count*50}ms for STT to be ready")

        try:
            while True:
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                if msg.get("event") == "start":
                    nonlocal stream_sid
                    start_data = msg.get("start", {})
                    log.info(f"[PLIVO] Start Event Data: {start_data}")
                    # Try both Twilio style (streamSid) and potential Plivo Snake Case (stream_sid/stream_id)
                    stream_sid = start_data.get("streamSid") or start_data.get("stream_sid") or start_data.get("streamId") or start_data.get("stream_id")
                    
                    if not stream_sid:
                        # Fallback to call_uuid if no stream_id is found
                        stream_sid = start_data.get("callUuid") or start_data.get("call_uuid")
                    
                    log.info(f"[PLIVO] Stream ID locked: {stream_sid}")
                    stream_ready.set()
                
                if msg.get("event") == "media":
                    payload = msg.get("media", {}).get("payload", "")
                    if payload:
                        if first_chunk_ts is None:
                            first_chunk_ts = time.time()
                            log.info(f"[PLIVO] First chunk: {int((first_chunk_ts - start_connect) * 1000)}ms after WS connect")

                        chunk = base64.b64decode(payload)
                        await send_audio_chunk(chunk)

                        # No VAD interrupt — Deepgram handles it via transcript_loop

                elif msg.get("event") == "stop":
                    log.info("[PLIVO] Stop event received")
                    break
        except WebSocketDisconnect:
            log.info("[PLIVO] WebSocket disconnected")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"[AUDIO] Forwarder error: {type(e).__name__}: {e}")

    async def transcript_loop():
        while True:
            try:
                # Wait for transcript (even while bot is speaking — Deepgram filters echo)
                start_wait = time.time()
                text = await get_final_transcript(timeout=10)
                stt_ms = int((time.time() - start_wait) * 1000)

                if not text:
                    if stt_ms > 1000:
                        log.info(f"[STT] No speech after {stt_ms}ms")
                    continue

                # If bot is speaking and user said something substantial → interrupt
                # Ignore short acknowledgments ("हां", "हैं", "ok") — not real interrupts
                if is_speaking:
                    # Patient Interruption: Only stop the bot if the user says something substantial (>= 4 words)
                    # This prevents background noise or 'umm/hmm' from interrupting the flow.
                    word_count = len(text.split())
                    if word_count >= 4:
                        interrupt_event.set()
                        log.info(f"[INTERRUPT] Substantial user speech: '{text}' (words={word_count})")
                        while is_speaking:
                            await asyncio.sleep(0.05)
                    else:
                        log.info(f"[SKIP] Short snippet while bot speaking: '{text}' — ignoring.")
                        continue 

                # 🚀 Instant Filler Logic
                # Play filler immediately if we have text and user stopped talking
                if text and not is_speaking:
                    asyncio.create_task(_play_filler())

                # Process the transcript
                result = await _process_text(text, target_lang=tts_language)
                if result == "TERMINATE":
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[TRANSCRIPT] Loop error: {e}")

    forwarder_task = asyncio.create_task(audio_forwarder())
    transcript_task = asyncio.create_task(transcript_loop())

    try:
        done, pending = await asyncio.wait(
            [forwarder_task, transcript_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except Exception as e:
        log.error(f"Main loop error: {e}")
    finally:
        # Save call completion to DB
        if call_id:
            duration = int(time.time() - start_connect)
            metadata = json.dumps({"stock": last_stock}) if last_stock else "{}"
            update_call(call_id, status="completed", ended_at=datetime.utcnow().isoformat() + "Z",
                       duration_sec=duration, metadata=metadata)
            log.info(f"[DB] Call {call_id} saved (duration={duration}s)")

        await stt_disconnect()
        await tts_ctx.close()
        await session.close()
