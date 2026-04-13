import json
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY

log = logging.getLogger(__name__)
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

TTS_RESPONSE_CACHE = {}


def build_agent_prompt(call_data):
    skus_str = ", ".join(call_data["skus"])
    current_time = call_data["current_time"]

    return f"""*** OBJECTIVE:
You are a female assistant named Neha from DS Group. Call distributors and collect stock quickly.

*** SKUS LIST: {skus_str}
*** CURRENT TIME: {current_time}

*** HARD RULES (CRITICAL):
- NEVER repeat the same SKU question.
- Once asked, NEVER ask again.
- If unclear → mark "not_provided" and move on.
- Keep responses SHORT (max 15 words preferred).
- If user provides a range (e.g. "एक दो", "5-10"), ALWAYS take the HIGHER number (e.g. 2, 10).

*** ALWAYS ACCEPT:
- Any answer = final answer.
- "याद नहीं", "नहीं है", "पता नहीं", "ध्यान नहीं" → REQUIRED ACTION: State "कोई बात नहीं" → Move to NEXT SKU immediately → Return "not_provided" for current SKU in JSON.
- NEVER ask the same SKU twice even if user says they don't know. Just move on.
- Extract numbers from Hindi words.

*** SKU SELECTION LOGIC:
Before every response:
1. Check CURRENT_STOCK
2. Pick FIRST SKU with null value
3. Ask ONLY that SKU
4. If none left → CLOSE

*** USER EXIT:
If user says:
"busy", "baad mein", "phone kaat do", "interest nahi"
→ Reply: "ठीक है, धन्यवाद!" and terminate = true

*** FLOW:
1. Greeting
2. Ask each SKU once
3. Close: "धन्यवाद, आपका दिन शुभ हो।"

*** LANGUAGE:
- Hindi only
- No repetition
- No long sentences

*** FORMAT: JSON ONLY
{{
  "response": "Hindi reply (Write numbers in Hindi words, e.g. बारह instead of 12)",
  "state": "STOCK",
  "terminate": false,
  "stock": {{"SKU": number_or_"not_provided"}}
}}

*** NATURAL CONVERSATION:
- If user says "ठीक है", "जी", or "हाँ" without a number, ACKNOWLEDGE and rephrase the question naturally (e.g. "जी, तो खजूर के कितने पैक्स हैं?").
- DO NOT repeat the exact same sentence twice.
- Always be polite and sound like a person, not a robot.
"""


async def get_agent_response(
    state,
    last_bot_msg,
    history,
    user_text,
    call_data,
    current_stock,
    system_prompt_override=None,
    is_generic=False # New flag to bypass inventory logic
):
    hist_str = ""
    for h in history[-5:]:
        role = "Bot" if h["role"] == "assistant" else "User"
        hist_str += f"{role}: {h['content']}\n"

    if not is_generic:
        user_msg = (
            f"CURRENT_STATE: {state}\n"
            f"CURRENT_STOCK: {json.dumps(current_stock)}\n"
            f"LAST_BOT_MESSAGE: {last_bot_msg}\n"
            f"HISTORY:\n{hist_str}"
            f"USER_SAID: {user_text}"
        )
    else:
        # 🔥 GENERIC PERSONA MODE: No stock/state clutter to distract the AI
        user_msg = (
            f"CONVERSATION_HISTORY:\n{hist_str}"
            f"USER_LATEST_MESSAGE: {user_text}"
        )

    raw = ""

    try:
        prompt = system_prompt_override if system_prompt_override else build_agent_prompt(call_data)

        if not is_generic:
            # 🔥 INVENTORY SPECIFIC RULES
            prompt += """
*** CRITICAL RUNTIME RULES:
1. NEVER repeat last bot message.
2. NEVER ask same SKU again.
3. If all SKUs filled → terminate true.
4. If user exit intent → terminate true.
"""
        else:
            # 🔥 GENERIC AGENT RULES (Optimized for Kia/Sales)
            prompt += """
*** RUNTIME RULES:
1. Follow the OBJECTIVE strictly.
2. Keep responses natural and conversational.
3. If user wants to end → set "terminate": true.
4. Extract provided information (date, time, KM) and store it in your internal state.
5. ANTI-HALLUCINATION: If user input is very short (1-2 words) or ambiguous (e.g., "I", "But", "Wait"), DO NOT jump to the next step. Instead, acknowledge and wait for them to finish their sentence.
"""

        # ALWAYS required for either type
        prompt += '\n*** FORMAT: JSON ONLY\n{"response": "reply", "state": "current_state", "terminate": false, "stock": {}}\n'

        comp = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=250,
            temperature=0,
            stream=False,
            response_format={"type": "json_object"}
        )

        raw = comp.choices[0].message.content.strip()

        # साफ JSON parsing
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        response = data.get("response", "")
        next_state = data.get("state", state)
        terminate = data.get("terminate", False)
        stock = data.get("stock", {})

        # 🚨 HARD GUARD 1: prevent repetition loop
        if response.strip() == last_bot_msg.strip():
            log.warning("Repeat detected → forcing termination")
            return ("धन्यवाद, आपका दिन शुभ हो।", state, True, current_stock)

        # 🚨 HARD GUARD 2: user exit detection (code level)
        exit_keywords = ["busy", "baad", "बाद", "फोन काट", "मत कॉल", "नहीं बात"]
        if any(k in user_text.lower() for k in exit_keywords):
            return ("ठीक है, धन्यवाद!", state, True, current_stock)

        # 🚨 HARD GUARD 3: prevent asking already filled SKU
        for sku, val in current_stock.items():
            if val is not None and sku in response:
                log.warning("Asking already filled SKU → fixing")
                return ("धन्यवाद, आपका दिन शुभ हो।", state, True, current_stock)

        # merge stock safely (Only for inventory agents)
        if not is_generic:
            updated_stock = current_stock.copy()
            expected_skus = call_data.get("skus", [])
            for sku in expected_skus:
                if sku not in updated_stock:
                    updated_stock[sku] = None

            for k, v in stock.items():
                if updated_stock.get(k) is None:
                    updated_stock[k] = v

            # 🚨 AUTO CLOSE: only for inventory bots
            if expected_skus and all(updated_stock.get(sku) is not None for sku in expected_skus):
                return ("धन्यवाद, आपका दिन शुभ हो।", state, True, updated_stock)
            
            return (response, next_state, terminate, updated_stock)
        
        # For Generic Agents, just return the raw response
        return (response, next_state, terminate, {})

    except Exception as e:
        log.error(f"LLM error: {e} | raw: {raw if raw else 'None'}")

        # fallback safe response - DON'T terminate on single error
        return ("जी, समझ नहीं आया। क्या आप फिर से बता सकते हैं?", state, False, current_stock)


async def get_streaming_agent_response(
    state,
    last_bot_msg,
    history,
    user_text,
    call_data,
    current_stock,
    system_prompt_override=None,
    is_generic=False
):
    """
    Streams the Groq response and yields sentences as they are generated.
    Yields: ('sentence', text) OR ('json', parsed_data)
    """
    prompt = system_prompt_override if system_prompt_override else build_agent_prompt(call_data)
    
    # Context cleaning (same as non-streaming)
    hist_str = ""
    for h in history[-5:]:
        role = "Bot" if h["role"] == "assistant" else "User"
        hist_str += f"{role}: {h['content']}\n"

    if not is_generic:
        user_msg = (
            f"CURRENT_STATE: {state}\n"
            f"CURRENT_STOCK: {json.dumps(current_stock)}\n"
            f"LAST_BOT_MESSAGE: {last_bot_msg}\n"
            f"HISTORY:\n{hist_str}"
            f"USER_SAID: {user_text}"
        )
        prompt += "\n*** CRITICAL RUNTIME RULES:\n1. NEVER repeat last bot message.\n2. NEVER ask same SKU again.\n3. If all SKUs filled -> terminate true."
    else:
        user_msg = (
            f"CONVERSATION_HISTORY:\n{hist_str}"
            f"USER_LATEST_MESSAGE: {user_text}"
        )
        prompt += "\n*** RUNTIME RULES:\n1. Follow the OBJECTIVE strictly.\n2. Keep responses natural.\n3. ANTI-HALLUCINATION: If user input is ambiguous, ask for clarification."

    prompt += '\n*** FORMAT: JSON ONLY\n{"response": "reply", "state": "current_state", "terminate": false, "stock": {}}\n'

    full_raw = ""
    sentence_buffer = ""
    sentence_endings = ["।", ".", "?", "!", "\n"]
    response_started = False
    quote_open = False
    escaped = False

    try:
        stream = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=250,
            temperature=0,
            stream=True,
            response_format={"type": "json_object"}
        )

        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if not token: continue
            full_raw += token

            # We try to extract the content of the "response" field while streaming.
            if not response_started:
                # Be more flexible with whitespace/case
                resp_marker = '"response":'
                if resp_marker in full_raw.replace(" ", ""):
                    response_started = True
                    # Find where the actual content starts (after "response": and its opening quote)
                    start_pos = full_raw.find('"response"') + 10
                    after_marker = full_raw[start_pos:]
                    q_start = after_marker.find('"')
                    if q_start != -1:
                        quote_open = True
                        sentence_buffer = after_marker[q_start+1:]
                continue
            
            # If we are inside the "response" quote:
            if quote_open:
                # Optimization: process the whole token at once for speed
                for char in token:
                    if char == "\\" and not escaped:
                        escaped = True
                        continue
                    if char == '"' and not escaped:
                        quote_open = False
                        break
                    
                    sentence_buffer += char
                    escaped = False

                    # If we hit a sentence ending, yield it!
                    if any(sentence_buffer.endswith(end) for end in sentence_endings):
                        clean_sentence = sentence_buffer.strip().replace('\\"', '"').replace('\\n', '\n')
                        if clean_sentence:
                            yield ("sentence", clean_sentence)
                        sentence_buffer = ""

        # 🔥 CRITICAL: Flush remaining sentence_buffer if any
        final_text = sentence_buffer.strip().replace('\\"', '"').replace('\\n', '\n')
        if final_text:
            yield ("sentence", final_text)

        # Finally, parse the full raw text as JSON for meta-data
        try:
            data = json.loads(full_raw)
            yield ("json", data)
        except Exception as e:
            log.warning(f"Failed to parse final streamed JSON: {e}")
            yield ("json", {"response": full_raw, "state": state, "terminate": False})
            yield ("json", {"response": sentence_buffer, "state": state, "terminate": False})

    except Exception as e:
        log.error(f"Streaming LLM error: {e}")
        yield ("sentence", "जी, मैं सुन रही हूँ।")
        yield ("json", {"response": "जी, मैं सुन रही हूँ।", "state": state})