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


async def get_agent_response_stream(
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
    Streaming version of get_agent_response.
    Yields: (sentence_text, is_final, data_dict)
    """
    hist_str = ""
    for h in history[-5:]:
        role = "Bot" if h["role"] == "assistant" else "User"
        hist_str += f"{role}: {h['content']}\n"

    user_msg = user_text
    
    # 2. Get prompt
    prompt = system_prompt_override if system_prompt_override else build_agent_prompt(call_data)
    if not is_generic:
        prompt += "\n*** CRITICAL RUNTIME RULES:\n1. NEVER repeat last bot message.\n2. NEVER ask same SKU again.\n3. If all SKUs filled → terminate true.\n4. If user exit intent → terminate true.\n"
    else:
        prompt += "\n*** RUNTIME RULES:\n1. Follow the OBJECTIVE strictly.\n2. Keep responses natural.\n3. If user wants to end → set \"terminate\": true.\n"
    
    prompt += '\n*** FORMAT: JSON ONLY\n{"response": "reply", "state": "current_state", "terminate": false, "stock": {}}\n'

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
            response_format={"type": "json_object"} # Re-enforce JSON mode
        )

        full_content = ""
        sent_sentences = set()
        import re
        
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if not content:
                continue
            full_content += content
            
            # --- Robust Streaming Extraction ---
            # Try to extract the "response" field if it exists
            match = re.search(r'"response":\s*"([^"]*)', full_content)
            extracted_text = ""
            if match:
                extracted_text = match.group(1)
            elif not full_content.strip().startswith("{"):
                # Fallback: If LLM is not outputting JSON at all, treat whole thing as text
                extracted_text = full_content.strip()

            if extracted_text:
                # Split and yield sentences as they complete
                sentences = re.split(r'([।\.?!\n])', extracted_text)
                for i in range(0, len(sentences)-1, 2):
                    s = (sentences[i] + sentences[i+1]).strip()
                    # Only yield if sentence contains actual words (prevent TTS crashes on dots)
                    if s and s not in sent_sentences and re.search(r'[\w\u0900-\u097F]', s):
                        # Clean special characters out of the sentence before yielding
                        s = re.sub(r'["\-_*]', ' ', s).strip()
                        if s:
                            yield (s, False, None)
                            sent_sentences.add(s)

        # --- Final Cleanup ---
        raw = full_content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
            # Filter out text that is only punctuation or empty to prevent TTS crashes
            clean = re.sub(r'[^\w\s]', '', raw).strip()
            if not clean or len(clean) == 0:
                raw = "{}"
        
        try:
            data = json.loads(raw)
            resp = data.get("response", "")
            for s in re.split(r'(?<=[।\.?!\n])', resp):
                s = s.strip()
                if s and s not in sent_sentences:
                    yield (s, False, None)
                    sent_sentences.add(s)
            
            yield (None, True, data)
        except:
            log.error(f"[LLM] Final JSON parse failed: {raw}")
            yield (None, True, {"response": "जी, समझ नहीं आया।", "state": state, "terminate": False})

    except Exception as e:
        log.error(f"[LLM] Stream error: {e}")
        yield ("जी, समझ नहीं आया।", True, {"response": "error", "state": state, "terminate": False})

async def get_agent_response(
    state, last_bot_msg, history, user_text, call_data, current_stock,
    system_prompt_override=None, is_generic=False
):
    """Fallback legacy wrapper for non-streaming usage."""
    async for text, is_final, data in get_agent_response_stream(
        state, last_bot_msg, history, user_text, call_data, current_stock,
        system_prompt_override, is_generic
    ):
        if is_final:
            return data.get("response", ""), data.get("state", state), data.get("terminate", False), data.get("stock", {})
    return "जी, समझ नहीं आया।", state, False, {}