import json
import logging
import asyncio
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime

log = logging.getLogger(__name__)

# Ensure .env is loaded directly
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

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
    STREAMS the OpenAI response. 
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

        messages = [{"role": "system", "content": full_system_prompt}]
        for h in history[-3:]:
             messages.append({"role": h["role"], "content": h["content"]})
        
        messages.append({"role": "user", "content": user_text})

        # 🚀 STREAM from OpenAI (GPT-4o-mini)
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            max_tokens=150,
            stream=True,
            response_format={"type": "json_object"}
        )

        full_raw = ""
        yielded_index = 0
        
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            full_raw += delta
            
            if '"response": "' in full_raw:
                start_ptr = full_raw.find('"response": "') + 13
                text_so_far = full_raw[start_ptr:]
                
                if '"' in text_so_far:
                    text_so_far = text_so_far[:text_so_far.find('"')]
                
                new_text = text_so_far[yielded_index:]
                
                # 🚀 BALANCE: Yield FIRST chunk (12 words) for natural speech flow
                words = new_text.strip().split()
                if yielded_index == 0 and len(words) >= 12:
                     chunk_to_yield = " ".join(words[:12])
                     if any('\u0900'<=c<='\u097f' or 'a'<=c.lower()<='z' for c in chunk_to_yield):
                         yield (chunk_to_yield + " ", False, None)
                     yielded_index += len(chunk_to_yield) + 1

                # 🚀 CONTINUITY: Yield after punctuation for later chunks
                elif yielded_index > 0:
                    punct_marks = [".", "?", "!", "।", ",", "\n"]
                    found_mark = -1
                    for mark in punct_marks:
                        idx = new_text.rfind(mark)
                        if idx > found_mark: found_mark = idx
                    
                    if found_mark != -1:
                        chunk_to_yield = new_text[:found_mark+1]
                        if any('\u0900'<=c<='\u097f' or 'a'<=c.lower()<='z' for c in chunk_to_yield):
                            yield (chunk_to_yield, False, None)
                            yielded_index += len(chunk_to_yield)

        # 🚀 FINAL: Clean up and send metadata
        try:
            final_json = json.loads(full_raw)
            clean_response = final_json.get("response", "")
            final_chunk = clean_response[yielded_index:].strip()
            
            if final_chunk:
                yield (final_chunk + " ", True, final_json)
            else:
                yield ("", True, final_json)
        except Exception as e:
            log.error(f"[LLM] Final Parse Error: {e} | Raw: {full_raw}")
            yield ("", True, {"response": "", "state": state, "terminate": False})

    except Exception as e:
        log.error(f"LLM error: {e}")
        yield ("जी, समझ नहीं आया।", True, {"response": "error", "state": state, "terminate": False})