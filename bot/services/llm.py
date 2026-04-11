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
    system_prompt_override=None
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

        # 🔥 ADDITIONAL STRICT RULES (runtime safety)
        prompt += """

*** CRITICAL RUNTIME RULES:
1. NEVER repeat last bot message.
2. NEVER ask same SKU again.
3. If all SKUs filled → terminate true.
4. If user exit intent → terminate true.
5. Always return valid JSON.
"""

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

        # merge stock safely
        updated_stock = current_stock.copy()
        
        # Ensure all expected SKUs exist in the stock dict with at least None values
        expected_skus = call_data.get("skus", [])
        for sku in expected_skus:
            if sku not in updated_stock:
                updated_stock[sku] = None

        for k, v in stock.items():
            if updated_stock.get(k) is None:
                updated_stock[k] = v

        # 🚨 HARD GUARD 4: auto close if all filled
        if expected_skus and all(updated_stock.get(sku) is not None for sku in expected_skus):
            return ("धन्यवाद, आपका दिन शुभ हो।", state, True, updated_stock)

        return (response, next_state, terminate, updated_stock)

    except Exception as e:
        log.error(f"LLM error: {e} | raw: {raw if raw else 'None'}")

        # fallback safe response - DON'T terminate on single error
        return ("जी, समझ नहीं आया। क्या आप फिर से बता सकते हैं?", state, False, current_stock)