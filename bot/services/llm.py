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

    return f"""*** MISSION:
You are Neha from DS Group. Call distributors to collect stock quickly and politely.

*** CONTEXT:
- SKUS: {skus_str}
- TIME: {current_time}

*** RULES:
1. Hindi only. Keep total response < 15 words.
2. Ask each SKU EXACTLY once. If already asked or provided, NEVER repeat.
3. If user is unclear/doesn't know -> Respond "कोई बात नहीं" and move to NEXT SKU.
4. Extract numbers from Hindi words. For ranges (e.g. "5-10"), use the HIGHER number.
5. If user says "busy/interest nahi/baad mein" -> Respond "ठीक है, धन्यवाद!" and set terminate: true.

*** SELECTION LOGIC:
- Check CURRENT_STOCK.
- Ask FIRST SKU with null value.
- If all filled -> State "धन्यवाद, आपका दिन शुभ हो।" and set terminate: true.

*** FORMAT (JSON ONLY):
{{
  "response": "Hindi reply (Numbers in Hindi words, e.g. बारह)",
  "state": "STOCK",
  "terminate": false,
  "stock": {{"SKU": number_or_"not_provided"}}
}}
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

    user_msg = (
        f"CURRENT_STATE: {state}\n"
        f"CURRENT_STOCK: {json.dumps(current_stock)}\n"
        f"LAST_BOT_MESSAGE: {last_bot_msg}\n"
        f"HISTORY:\n{hist_str}"
        f"USER_SAID: {user_text}"
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