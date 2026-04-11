import asyncio
import audioop
import base64
import io
import json
import logging
import os
import sys
import time
import torch
import torchaudio

# Add local OmniVoice path
# Add parent directory to path to find local packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gpu_utils import get_device, get_dtype, log_device_info
from database import list_voices

log = logging.getLogger(__name__)

# Try to import from local package
try:
    from omnivoice import OmniVoice
except ImportError:
    log.error("[TTS] Failed to import OmniVoice from local 'omnivoice' package")
    OmniVoice = None

# Cache for generated audio
TTS_CACHE = {}

# Global model instance
_model = None
_model_lock = asyncio.Lock()

# Reference audio and text defaults
DEFAULT_REF_AUDIO = os.getenv("DEFAULT_REF_AUDIO", os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices", "default_ref.mp3"))
DEFAULT_REF_TEXT = os.getenv("DEFAULT_REF_TEXT", "नमस्ते, मैं आपकी सहायता के लिए तैयार हूँ।")

async def init_tts():
    """Warms up the model at server startup."""
    log.info("[TTS] Warming up OmniVoice model...")
    await _get_model()
    log.info("[TTS] Warm-up complete.")

async def _get_model():
    """Lazy load the OmniVoice model."""
    global _model
    if _model is not None:
        return _model
        
    async with _model_lock:
        if _model is not None:
            return _model
        
        if OmniVoice is None:
            log.error("[TTS] OmniVoice library not available.")
            return None

        log.info("[TTS] Initializing OmniVoice model on GPU...")
        try:
            device = get_device()
            dtype = get_dtype()
            
            _model = OmniVoice.from_pretrained(
                "k2-fsa/OmniVoice",
                device_map=device,
                torch_dtype=dtype
            )
            log.info(f"[TTS] OmniVoice model loaded successfully on {device}")
            return _model
        except Exception as e:
            log.error(f"[TTS] Failed to load OmniVoice: {e}")
            return None

def resample_and_to_mulaw(audio_tensor, orig_sr=24000, target_sr=8000):
    """Convert OmniVoice output (Tensor) to Plivo-ready mu-law (bytes)."""
    # 1. Ensure it's on CPU and 1D
    audio = audio_tensor.detach().cpu()
    if audio.dim() > 1:
        audio = audio.squeeze(0)
    
    # 2. Resample using torchaudio
    if orig_sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        audio = resampler(audio)
    
    # 3. Convert to PCM 16-bit
    pcm16 = (audio * 32767).to(torch.int16).numpy().tobytes()
    
    # 4. Convert PCM to mu-law 8kHz
    mulaw = audioop.lin2ulaw(pcm16, 2)
    return mulaw

def tensor_to_wav(audio_tensor, sr=24000):
    """Convert OmniVoice output (Tensor) to WAV bytes for browser playback."""
    import scipy.io.wavfile
    import io
    
    audio = audio_tensor.detach().cpu()
    if audio.dim() > 1:
        audio = audio.squeeze(0)
    
    # Ensure range is [-1, 1]
    audio = torch.clamp(audio, -1, 1)
    
    buffer = io.BytesIO()
    scipy.io.wavfile.write(buffer, sr, audio.numpy())
    return buffer.getvalue()

def _resolve_audio_path(path):
    """Helper to handle absolute paths from different machines."""
    if not path:
        return path
    if os.path.exists(path):
        return path
    
    # Try to find the file in the local voices directory
    filename = os.path.basename(path)
    local_voices_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices")
    local_path = os.path.join(local_voices_dir, filename)
    
    if os.path.exists(local_path):
        log.info(f"[TTS] Resolved path {path} to local {local_path}")
        return local_path
    
    return path

async def omnivoice_tts(text, voice_id=None, language="hindi"):
    """Generate audio using OmniVoice."""
    model = await _get_model()
    if not model:
        log.error("[TTS] Model not loaded.")
        return None

    # Determine reference audio and text
    ref_audio = _resolve_audio_path(DEFAULT_REF_AUDIO)
    ref_text = DEFAULT_REF_TEXT
    
    if voice_id:
        # Fetch voice from database
        from database import get_voice
        voice = get_voice(voice_id)
        if voice:
            ref_audio = _resolve_audio_path(voice["ref_audio_path"])
            ref_text = voice["ref_text"] or DEFAULT_REF_TEXT

    # Optimization: Automatically trim reference audio if it's too long
    # This is the biggest latency killer. 5s is plenty for quality.
    # We ALSO trim the text proportionally to prevent 'mixing' or repetition.
    try:
        from pydub import AudioSegment
        trimmed_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices", "trimmed")
        if not os.path.exists(trimmed_dir):
            os.makedirs(trimmed_dir)
            
        base_name = os.path.basename(ref_audio)
        trimmed_path = os.path.join(trimmed_dir, f"v2_t5_{base_name}")
        
        if not os.path.exists(trimmed_path):
            audio = AudioSegment.from_file(ref_audio)
            original_duration_ms = len(audio)
            
            if original_duration_ms > 5000: # If longer than 5s
                log.info(f"[TTS] Trimming reference audio {base_name} to 5s and aligning text.")
                trimmed = audio[:5000]
                trimmed.export(trimmed_path, format="wav")
                
                # Align text: if we take 5s out of 22s, we take ~23% of text
                # We ensure we cut at a 'space' so we don't have partial words
                ratio = 5000 / original_duration_ms
                words = ref_text.split()
                num_words = max(1, int(len(words) * ratio))
                ref_text = " ".join(words[:num_words])
                log.info(f"[TTS] Aligned ref_text ({num_words} words): {ref_text[:40]}...")
            else:
                trimmed_path = ref_audio
        
        ref_audio = trimmed_path
    except Exception as e:
        log.warning(f"[TTS] Could not align audio: {e}. Using original.")

    # 🛠️ Text Normalization for better Pronunciation
    # Normalize common Hinglish terms to Hindi script for smoother TTS flow
    replacements = {
        "packs": "पैक्स", "pack": "पैक", "pouches": "पाउचेस", "pouch": "पाउच",
        "units": "यूनिट्स", "unit": "यूनिट", "stock": "स्टॉक", "count": "काउंट",
        "service": "सर्विस", "center": "सेंटर", "car": "कार", "booking": "बुकिंग"
    }
    for eng, hin in replacements.items():
        text = text.replace(f" {eng}", f" {hin}").replace(f"{eng} ", f"{hin} ")

    log.info(f"[TTS] Synthesizing with voice: {voice_id or 'default'} in language: {language}")
    
    start = time.time()
    try:
        # OmniVoice generate is usually blocking, we run in executor
        loop = asyncio.get_event_loop()
        audio_list = await loop.run_in_executor(None, lambda: model.generate(
            text=text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            language=language or "hindi",
            num_inference_steps=35 # Increased for better pronunciation clarity
        ))
        
        if not audio_list or len(audio_list) == 0:
            return None
            
        mulaw = resample_and_to_mulaw(audio_list[0])
        ms = int((time.time() - start) * 1000)
        log.info(f"[TTS] Generated {len(mulaw)} bytes in {ms}ms")
        return mulaw
    except Exception as e:
        log.error(f"[TTS] Generation error: {e}")
        return None

class TTSContext:
    """Mock context to keep compatibility with existing code."""
    def __init__(self):
        self.ready = True
    async def open(self): return True
    async def close(self): pass

async def stream_tts_to_plivo(text, tts_ctx, plivo_ws, voice_id=None, language="hindi"):
    """
    Simulated streaming: generate whole sentence and send in chunks to Plivo.
    """
    # Use a combined key for cache
    cache_key = f"{text}_{voice_id}_{language}"
    
    if cache_key in TTS_CACHE:
        mulaw = TTS_CACHE[cache_key]
    else:
        mulaw = await omnivoice_tts(text, voice_id, language)
        if mulaw:
             TTS_CACHE[cache_key] = mulaw

    if not mulaw:
        return None

    # Send in small chunks to simulate streaming feel
    chunk_size = 320 # 20ms of audio
    for i in range(0, len(mulaw), chunk_size):
        chunk = mulaw[i:i+chunk_size]
        await plivo_ws.send_text(json.dumps({
            "event": "playAudio",
            "media": {
                "contentType": "audio/x-mulaw",
                "sampleRate": "8000",
                "payload": base64.b64encode(chunk).decode()
            }
        }))
        # Small sleep to pace the "stream"
        await asyncio.sleep(0.015) 
        
    return mulaw

async def pre_connect():
    """Pre-load the model."""
    await _get_model()

def prepare_for_tts(text):
    """Legacy helper for text cleaning."""
    return text.strip()
