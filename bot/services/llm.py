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
    is_generic=False
):
    """
    STREAMS the LLM response. 
    Yields: (text_chunk, is_final, metadata_if_final)
    """
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
        prompt += '\n*** FORMAT: JSON ONLY. Put "response" field FIRST.\n{"response": "reply", "state": "current_state", "terminate": false, "stock": {}}\n'

        user_msg = (
            f"CURRENT_STATE: {state}\n"
            f"CURRENT_STOCK: {json.dumps(current_stock)}\n"
            f"LAST_BOT_MESSAGE: {last_bot_msg}\n"
            f"USER_SAID: {user_text}"
        )

        messages = [{"role": "system", "content": prompt}]
        # Add history (last 5 messages)
        for h in history[-5:]:
            messages.append({"role": h["role"], "content": h["content"]})
        
        # Current User Interaction
        messages.append({"role": "user", "content": user_msg})

        # Groq Stream
        stream = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=250,
            temperature=0,
            stream=True,
            response_format={"type": "json_object"}
        )

        full_raw = ""
        yielded_index = 0
        
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            full_raw += delta
            
            # Simple extraction logic for the "response" field as it streams
            if '"response": "' in full_raw:
                start_idx = full_raw.find('"response": "') + 13
                current_content = full_raw[start_idx:]
                new_text = current_content[yielded_index:]
                
                # We yield whenever we see space or punctuation to keep audio delivery smooth
                if any(char in new_text for char in [" ", "।", ".", "?", "!", "\n"]):
                    last_p = -1
                    for i, char in enumerate(new_text):
                        if char in [" ", "।", ".", "?", "!", "\n"]:
                            last_p = i
                    
                    if last_p != -1:
                        chunk_to_yield = new_text[:last_p+1].strip()
                        # Only yield if it contains Hnd or Eng characters
                        if any('a'<=c.lower()<='z' or '\u0900'<=c<='\u097f' for c in chunk_to_yield):
                            yield (chunk_to_yield, False, None)
                        yielded_index += last_p + 1

        # End of stream: Finalize extraction and return metadata
        if '"response": "' in full_raw:
            start_idx = full_raw.find('"response": "') + 13
            end_idx = full_raw.find('"', start_idx)
            if end_idx != -1:
                final_text = full_raw[start_idx:end_idx]
                residual = final_text[yielded_index:].strip()
                if residual and any('a'<=c.lower()<='z' or '\u0900'<=c<='\u097f' for c in residual):
                    yield (residual, False, None)

        data = json.loads(full_raw)
        response = data.get("response", "")
        next_state = data.get("state", state)
        terminate = data.get("terminate", False)
        stock = data.get("stock", {})

        # merge stock safely (Only for inventory agents)
        updated_stock = current_stock.copy()
        if not is_generic:
            for k, v in stock.items():
                if updated_stock.get(k) is None:
                    updated_stock[k] = v

        yield (None, True, (response, next_state, terminate, updated_stock))

    except Exception as e:
        log.error(f"LLM error: {e}")
        yield ("जी, समझ नहीं आया।", True, ("जी, समझ नहीं आया।", state, False, current_stock))