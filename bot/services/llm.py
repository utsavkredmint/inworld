import json
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY

log = logging.getLogger(__name__)
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# Default fallback prompt if an agent has NO custom prompt in DB
DEFAULT_SYSTEM_PROMPT = """*** MISSION:
You are a helpful voice assistant. Be natural, conversational, and polite.

*** RULES:
1. Hindi only. Keep total response < 15 words.
2. Natural flow - avoid repeating yourself.
3. If user wants to end -> Respond politely and set terminate: true.
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
        # 1. Base System Prompt (Truly Dynamic)
        base_prompt = system_prompt_override if system_prompt_override and system_prompt_override.strip() else DEFAULT_SYSTEM_PROMPT
        
        # 2. Add Session Context (Operational only - not for bot to speak)
        context_block = f"""
*** OPERATIONAL_CONTEXT:
- CURRENT_STATE: {state}
- CURRENT_STOCK: {json.dumps(current_stock)}
- LAST_BOT_MSG: {last_bot_msg}

*** OUTPUT_RULES:
1. Response MUST be in JSON.
2. The "response" field should contains ONLY what you want for the text-to-speech. 
3. DO NOT repeat the keys (like "response" or "state") or the operational context labels in your spoken reply.
"""

        full_system_prompt = base_prompt + "\n" + context_block + '\n*** FORMAT: JSON ONLY.\n{"response": "reply", "state": "current_state", "terminate": false, "stock": {}}\n'

        messages = [{"role": "system", "content": full_system_prompt}]
        
        # 3. Add History (Last 5 turns)
        for h in history[-5:]:
            messages.append({"role": h["role"], "content": h["content"]})
        
        # 4. Final User Query (Clean - only the transcript)
        messages.append({"role": "user", "content": user_text})

        # 🚀 STREAM from Groq
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
            
            # Streaming extraction for "response" field
            if '"response": "' in full_raw:
                start_marker = '"response": "'
                start_idx = full_raw.find(start_marker) + len(start_marker)
                current_content = full_raw[start_idx:]
                
                # Check for the closing quote of the "response" field
                end_idx = current_content.find('"')
                text_so_far = current_content if end_idx == -1 else current_content[:end_idx]
                
                new_text = text_so_far[yielded_index:]
                
                # Yield at sentence boundaries or spaces
                if any(char in new_text for char in [" ", "।", ".", "?", "!", "\n"]):
                    last_p = -1
                    for i, char in enumerate(new_text):
                        if char in [" ", "।", ".", "?", "!", "\n"]:
                            last_p = i
                    
                    if last_p != -1:
                        chunk_to_yield = new_text[:last_p+1].strip()
                        # 🔥 FILTER: Ensure it has Hindi or English characters
                        if any('a'<=c.lower()<='z' or '\u0900'<=c<='\u097f' for c in chunk_to_yield):
                            yield (chunk_to_yield, False, None)
                        yielded_index += last_p + 1

        # End of stream: Final residue extraction
        data = json.loads(full_raw)
        response = data.get("response", "")
        
        # Check if we have un-yielded text from the final response
        residual = response[yielded_index:].strip()
        if residual and any('a'<=c.lower()<='z' or '\u0900'<=c<='\u097f' for c in residual):
            yield (residual, False, None)

        next_state = data.get("state", state)
        terminate = data.get("terminate", False)
        stock = data.get("stock", {})

        # Merge stock safely
        updated_stock = current_stock.copy()
        if stock:
            for k, v in stock.items():
                # Allow updating if value is meaningful
                updated_stock[k] = v

        yield (None, True, (response, next_state, terminate, updated_stock))

    except Exception as e:
        log.error(f"LLM error: {e}")
        yield ("जी, समझ नहीं आया।", True, ("जी, समझ नहीं आया।", state, False, current_stock))