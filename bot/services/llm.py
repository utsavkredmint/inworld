import json
import logging
import asyncio
from typing import AsyncGenerator
import google.generativeai as genai
from config import GOOGLE_API_KEY
from datetime import datetime

log = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)
# We use Gemini 1.5 Flash for the fastest voice turnaround
gen_model = genai.GenerativeModel('gemini-1.5-flash')

# Default fallback prompt if an agent has NO custom prompt in DB
DEFAULT_SYSTEM_PROMPT = """You are a helpful Hindi voice assistant.
Rules: Hindi only. < 15 words. Natural flow.
Do NOT restart greetings if the user says "Hello" mid-conversation; acknowledge and continue.
If ending, set terminate: true."""

async def get_agent_response(
    state,
    last_bot_msg,
    history,
    user_text,
    call_data,
    current_stock,
    system_prompt_override=None,
    is_generic=False
) -> AsyncGenerator:
    """
    STREAMS the Gemini response. 
    Yields: (text_chunk, is_final, metadata_if_final)
    """
    try:
        # 1. Base System Prompt
        base_prompt = system_prompt_override if system_prompt_override and system_prompt_override.strip() else DEFAULT_SYSTEM_PROMPT
        
        # 2. Add Session Context (Lean)
        context_block = f'Context: State={state}, Stock={json.dumps(current_stock)}, LastMsg="{last_bot_msg}"'
        
        # 🚀 VOICE GUARDRAILS: Integrated strictly for adherence
        time_str = datetime.now().strftime("%I:%M %p")
        guardrails = f"""
### OPERATIONAL RULES:
- TIME: {time_str}
- NEVER repeat intro/नमस्कार.
- IGNORE contextless "Hello/Ji" - stick to the current question.
- Max 20 words. One question at a time.
- FLOW: Date -> Time -> KM -> Confirm.
- Output MUST be valid JSON.
"""
        full_system_prompt = f"{base_prompt}\n{guardrails}\n{context_block}\nReturn JSON: {{\"response\": \"...\", \"state\": \"...\", \"terminate\": false}}"

        # 3. Format History for Gemini (Last 3 turns)
        messages = [{"role": "user", "parts": [full_system_prompt]}] # System instructions as first user turn for Flash
        for h in history[-3:]:
            role = "model" if h["role"] == "assistant" else "user"
            messages.append({"role": role, "parts": [h["content"]]})
        
        messages.append({"role": "user", "parts": [user_text]})

        # 🚀 STREAM from Gemini 1.5 Flash
        # Gemini Flash is extremely fast, comparable to Groq
        chat = gen_model.start_chat(history=messages[:-1])
        stream = await chat.send_message_async(
            messages[-1]["parts"][0],
            stream=True,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=150
            )
        )

        full_raw = ""
        yielded_index = 0
        
        async for chunk in stream:
            delta = chunk.text or ""
            full_raw += delta
            
            if '"response": "' in full_raw:
                start_marker = '"response": "'
                start_idx = full_raw.find(start_marker) + len(start_marker)
                current_content = full_raw[start_idx:]
                
                end_idx = current_content.find('"')
                text_so_far = current_content if end_idx == -1 else current_content[:end_idx]
                
                new_text = text_so_far[yielded_index:]
                
                # 🚀 BALANCE: Yield FIRST chunk (12 words) for natural speech flow
                words = new_text.strip().split()
                if yielded_index == 0 and len(words) >= 12:
                     chunk_to_yield = " ".join(words[:12])
                     if any('\u0900'<=c<='\u097f' or 'a'<=c.lower()<='z' for c in chunk_to_yield):
                         yield (chunk_to_yield + " ", False, None)
                     yielded_index += len(chunk_to_yield) + 1
                     continue

                # Yield at sentence boundaries (full stop, question mark, etc.)
                if any(char in new_text for char in ["।", ".", "?", "!", "\n"]):
                    last_p = -1
                    for i, char in enumerate(new_text):
                        if char in ["।", ".", "?", "!", "\n"]:
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
                updated_stock[k] = v

        yield (None, True, (response, next_state, terminate, updated_stock))

    except Exception as e:
        log.error(f"LLM error: {e}")
        yield ("जी, समझ नहीं आया।", True, ("जी, समझ नहीं आया।", state, False, current_stock))