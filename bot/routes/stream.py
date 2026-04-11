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
                
                # Mode Detection: Only inject SKUs if they exist
                skus = local_call_data.get("skus", [])
                if skus:
                    skus_str = ", ".join(skus)
                    current_time_str = local_call_data["current_time"]
                    # Only replace if the marker exists, otherwise just append
                    marker = "*** OBJECTIVE:"
                    sku_info = f"*** SKUS FOR THIS CALL (ASK EXACTLY THESE): {skus_str}\n*** CURRENT TIME: {current_time_str}\n\n"
                    if marker in system_prompt_override:
                        system_prompt_override = system_prompt_override.replace(marker, f"{sku_info}{marker}")
                    else:
                        system_prompt_override = f"{sku_info}{system_prompt_override}"
                    log.info(f"[AGENT] Inventory Mode: Injected SKUs: {skus_str}")
                else:
                    log.info(f"[AGENT] Generic Mode: Using raw Dashboard prompt.")
                
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
            system_prompt_override += f"\n\n*** IMPORTANT: {name_injection}"
        else:
            from services.llm import build_agent_prompt
            system_prompt_override = build_agent_prompt(local_call_data) + f"\n\n*** IMPORTANT: {name_injection}"

    # 🌍 Voice & Language Identity
    agent_language = agent.get("language", "hindi") if agent else "hindi"
    voice_id = agent.get("voice") if agent else None
    
    # 🔥 HOT LATENCY FIX: Start generating greeting TTS IMMEDIATELY
    greeting_task = asyncio.create_task(omnivoice_tts(greeting, voice_id=voice_id, language=agent_language))

    # Check for pre-setup session (STT + TTS already connected)
    from call_sessions import get_session
    pre_session = get_session(call_id) if call_id else None

    history = []
    is_speaking = False
    filler_cache = {}
    stream_sid = None
    last_bot_response = greeting
    is_generic_agent = len(local_call_data.get("skus", [])) == 0
    call_state = INTRO
    interrupt_event = asyncio.Event()
    session = aiohttp.ClientSession()
    first_chunk_ts = None
    vad = SileroVAD()
    speak_start_ts = 0
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

    async def speak(text, is_filler=False, language=None):
        nonlocal is_speaking, speak_start_ts
        tts_start = time.time()
        is_speaking = True
        speak_start_ts = time.time()
        interrupt_event.clear()

        # Use the provided language override (mapped) or fall back to agent default
        target_tts_lang = language or tts_language or agent_language
        prepared = prepare_for_tts(text)
        cache_key = f"{prepared}_{voice_id}_{target_tts_lang}"

        # Check pre-built TTS cache for instant playback (zero TTS latency)
        if cache_key in TTS_CACHE:
            audio = TTS_CACHE[cache_key]
            log.info(f"[SPEAK] Cache HIT for: {text[:40]}")
            # Send cached audio immediately
            try:
                msg = {
                    "event": "media",
                    "media": {"payload": base64.b64encode(audio).decode()}
                }
                if stream_sid: msg["streamSid"] = stream_sid
                await websocket.send_text(json.dumps(msg))
            except:
                pass
        else:
            log.info(f"[SPEAK] Streaming TTS for: {text[:40]}... (ctx_ready={tts_ctx.ready})")
            # This streams directly to Plivo WebSocket internally!
            audio = await stream_tts_to_plivo(text, tts_ctx, websocket, voice_id=voice_id, language=target_tts_lang)
            # Fallback to omnivoice_tts if streaming didn't work
            if not audio:
                log.info(f"[SPEAK] Fallback to direct TTS for: {text[:40]}")
                audio = await omnivoice_tts(text, voice_id=voice_id, language=target_tts_lang)
                if audio:
                    try:
                        msg = {
                            "event": "media",
                            "media": {"payload": base64.b64encode(audio).decode()}
                        }
                        if stream_sid: msg["streamSid"] = stream_sid
                        await websocket.send_text(json.dumps(msg))
                    except:
                        pass

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
        """Process a transcript: LLM → TTS → speak."""
        nonlocal call_state, last_bot_response, last_stock

        start_proc = time.time()

        # LLM
        llm_start = time.time()
        full_resp, next_state, terminate_call, stock = await get_agent_response(
            call_state, last_bot_response, history, text, local_call_data, last_stock,
            system_prompt_override=system_prompt_override,
            is_generic=is_generic_agent
        )
        if stock:
            last_stock.update(stock)  # MERGE — never overwrite previous SKU values
            log.info(f"[STOCK] {last_stock}")
        llm_ms = int((time.time() - llm_start) * 1000)

        # CODE-LEVEL AUTO-TERMINATE: If all SKUs are answered, force terminate immediately
        expected_skus = local_call_data.get("skus", [])
        if expected_skus and all(last_stock.get(sku) is not None for sku in expected_skus):
            farewell = "धन्यवाद, आपका दिन शुभ हो।"
            log.info(f"[AUTO-TERMINATE] All SKUs filled. Terminating call.")
            await speak(farewell, language=target_lang)
            if call_id:
                add_message(call_id, "user", text)
                add_message(call_id, "assistant", farewell)
            try:
                plivo_client.calls.group_hangup(call_uuid)
            except:
                try:
                    plivo_client.calls.hangup(call_uuid)
                except:
                    pass
            return "TERMINATE"

        # State guard: forward only — NEVER go back to INTRO
        cur_order = STATE_ORDER.get(call_state, 0)
        new_order = STATE_ORDER.get(next_state, 0)
        if new_order < cur_order:
            next_state = call_state
        # Extra guard: never allow going back to INTRO once in STOCK
        if call_state != "INTRO" and next_state == "INTRO":
            next_state = call_state

        call_state = next_state

        ms_total = int((time.time() - start_proc) * 1000)
        log.info(
            f"[{call_state}] LATENCY: {ms_total}ms (llm={llm_ms}ms) "
            f"| User: '{text}' | Response: {full_resp}"
        )
        last_bot_response = full_resp

        # Save to DB
        if call_id:
            add_message(call_id, "user", text)
            add_message(call_id, "assistant", full_resp)

        if terminate_call:
            await speak(full_resp, language=target_lang)
            log.info(f"Terminating Call: {call_uuid}")
            try:
                plivo_client.calls.group_hangup(call_uuid)
            except:
                try:
                    plivo_client.calls.hangup(call_uuid)
                except:
                    pass
            return "TERMINATE"
        else:
            asyncio.create_task(speak(full_resp, language=target_lang))

        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": full_resp})

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
        
        # Pre-cache in background while greeting plays
        asyncio.create_task(_pre_cache_skus())
        
        # Pre-generate Fillers for 100ms latency (Wait 2s so Greeting is perfect)
        await asyncio.sleep(2.0)
        fillers = ["जी", "जी बताइए", "जी देख रही हूँ"]
        for f in fillers:
            try:
                audio = await omnivoice_tts(f, voice_id=voice_id, language=tts_language)
                if audio: filler_cache[f] = audio
            except: pass
        log.info(f"[CACHE] Ready with {len(filler_cache)} instant fillers")

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
                    stream_sid = msg.get("start", {}).get("streamSid")
                    log.info(f"[PLIVO] Stream started: {stream_sid}")
                
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
                    word_count = len(text.split())
                    if word_count >= 3:
                        interrupt_event.set()
                        log.info(f"[INTERRUPT] User spoke while bot talking: '{text}'")
                        while is_speaking:
                            await asyncio.sleep(0.05)
                    else:
                        log.info(f"[SKIP] Short utterance while bot speaking: '{text}' — not interrupting")
                        continue  # Don't process short acknowledgments during bot speech

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
