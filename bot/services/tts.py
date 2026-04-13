import asyncio
import audioop
import base64
from concurrent.futures import ThreadPoolExecutor
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
_resampler = None # 🚀 LATENCY WIN: Pre-instantiated resampler
_resampler_lock = asyncio.Lock()
_TRIMMED_VOICE_CACHE = {} # 🚀 LATENCY WIN: Cache trimmed voice paths
_tts_executor = ThreadPoolExecutor(max_workers=1) # 🚀 LATENCY WIN: Serial execution

# Reference audio and text defaults
DEFAULT_REF_AUDIO_NAME = os.getenv("DEFAULT_REF_AUDIO_NAME", "default_ref.mp3")
DEFAULT_REF_TEXT = os.getenv("DEFAULT_REF_TEXT", "नमस्ते, मैं आपकी सहायता के लिए तैयार हूँ।")

def _get_default_ref_path():
    """Return the configured default ref or a smart fallback if missing."""
    voices_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices")
    primary_path = os.path.join(voices_dir, DEFAULT_REF_AUDIO_NAME)
    
    if os.path.exists(primary_path):
        return primary_path
        
    # Smart Fallback: Use the first mp3 found in the voices directory
    import glob
    existing_voices = glob.glob(os.path.join(voices_dir, "*.mp3"))
    if existing_voices:
        fallback = existing_voices[0]
        log.info(f"[TTS] Default ref missing. Using smart fallback: {os.path.basename(fallback)}")
        return fallback
        
    log.warning(f"[TTS] No reference voices found in {voices_dir}. Generation may fail.")
    return primary_path

DEFAULT_REF_AUDIO = _get_default_ref_path()

async def init_tts():
    """Warms up the model and PRE-CACHES all fillers for the default voice."""
    log.info("[TTS] Warming up OmniVoice model...")
    model = await _get_model()
    if model:
        try:
            log.info("[TTS] Performing warmup and filler pre-caching...")
            ref_audio = _resolve_audio_path(DEFAULT_REF_AUDIO)
            
            # Pre-cache fillers and a common greeting
            fillers = ["नमस्ते", "जी", "जी बताइए", "जी देख रही हूँ"]
            for f in fillers:
                audio = await omnivoice_tts(f, num_inference_steps=10)
                if audio:
                    update_tts_cache(f, audio)
            
            # 🚀 LATENCY WIN: Warm up CUDA kernels with a dummy 1-word generation
            # This ensures the FIRST live response doesn't have a 1.6s jitter
            log.info("[TTS] Performing dummy synthesis warmup...")
            await omnivoice_tts("चेक")
                    
            log.info(f"[TTS] Warmup successful. {len(fillers)} items cached.")
        except Exception as e:
            log.error(f"[TTS] Warmup failed: {e}")
    log.info("[TTS] Warmup complete.")

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
            # 🚀 LATENCY WIN: DISABLE torch.compile for now. 
            # It can cause 1-2s latency spikes on every new text shape/length.
            # try:
            #     if hasattr(torch, "compile"):
            #         log.info("[TTS] Compiling model for faster inference...")
            #         _model = torch.compile(_model)
            # except Exception as e:
            #     log.warning(f"[TTS] Model compilation skipped: {e}")
                
            log.info(f"[TTS] OmniVoice model loaded successfully on {device}")
            return _model
        except Exception as e:
            log.error(f"[TTS] Failed to load OmniVoice: {e}")
            return None

def resample_and_to_mulaw(audio_tensor, orig_sr=24000, target_sr=8000):
    """Convert OmniVoice output (Tensor) to Plivo-ready mu-law (bytes) with high fidelity."""
    # 1. Ensure it's on CPU and 1D
    audio = audio_tensor.detach().cpu()
    if audio.dim() > 1:
        audio = audio.squeeze(0)
    
    # 2. Peak Normalization: Ensure max volume is at -1dB (0.9 amplitude)
    if audio.numel() == 0:
        return b""
        
    max_val = torch.abs(audio).max()
    if max_val > 0:
        audio = (audio / max_val) * 0.9
    
    # 3. High-Quality Resampling (Pre-instantiated for 50ms Win)
    if orig_sr != target_sr:
        global _resampler
        if _resampler is None:
            # Note: Since this might be called from an executor, we use a simple check.
            # For strict safety in async, we'd need more, but here it's usually one generation at a time per session.
            _resampler = torchaudio.transforms.Resample(
                orig_sr, target_sr, 
                lowpass_filter_width=64, # 🚀 Improved Anti-Aliasing (Fixes metallic noise)
                resampling_method='sinc_interp_hann' 
            )
        audio = _resampler(audio)

    # 🚀 Boundary Smoothing: Apply small 2ms fades to avoid clicks between chunks
    fade_len = int(target_sr * 0.002) # 16 samples @ 8kHz
    if audio.shape[0] > fade_len * 2:
        fade_in = torch.linspace(0.0, 1.0, steps=fade_len)
        fade_out = torch.linspace(1.0, 0.0, steps=fade_len)
        audio[:fade_len] *= fade_in
        audio[-fade_len:] *= fade_out
    
    # 4. Add subtle dithering to prevent Mu-law quantization noise (hiss)
    dither = (torch.rand_like(audio) - 0.5) / 32768.0
    audio = audio + dither
    
    # 5. Convert to PCM 16-bit
    pcm16 = (audio * 32767).to(torch.int16).numpy().tobytes()
    
    # 6. Convert PCM to mu-law 8kHz
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

async def omnivoice_tts(text, voice_id=None, language="hindi", num_inference_steps=10):
    """Generate audio using OmniVoice with Cache-Awareness. Steps=10 for speed."""
    
    # 🚀 LATENCY WIN: Check cache BEFORE doing anything else
    cache_key = get_tts_cache_key(text, voice_id, language)
    if cache_key in TTS_CACHE:
        log.info(f"[TTS] Cache HIT for: {text[:40]}...")
        return TTS_CACHE[cache_key]

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
    # Use a static cache for trimmed paths to avoid filesystem I/O on every call
    global _TRIMMED_VOICE_CACHE
    if '_TRIMMED_VOICE_CACHE' not in globals():
        _TRIMMED_VOICE_CACHE = {}

    if ref_audio not in _TRIMMED_VOICE_CACHE:
        try:
            from pydub import AudioSegment
            trimmed_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "voices", "trimmed")
            if not os.path.exists(trimmed_dir):
                os.makedirs(trimmed_dir)
                
            base_name = os.path.basename(ref_audio)
            trimmed_path = os.path.join(trimmed_dir, f"v2_t5_{base_name}")
            
            if not os.path.exists(trimmed_path):
                audio = AudioSegment.from_file(ref_audio)
                if len(audio) > 8000: 
                    log.info(f"[TTS] Trimming reference audio {base_name} to 8s.")
                    trimmed = audio[:8000]
                    trimmed.export(trimmed_path, format="wav")
                else:
                    trimmed_path = ref_audio
            _TRIMMED_VOICE_CACHE[ref_audio] = trimmed_path
        except Exception as e:
            log.warning(f"[TTS] Could not align audio: {e}. Using original.")
            _TRIMMED_VOICE_CACHE[ref_audio] = ref_audio
    
    ref_audio = _TRIMMED_VOICE_CACHE[ref_audio]

    # 🛠️ Text Normalization for better Pronunciation
    # Normalize common Hinglish terms to Hindi script for smoother TTS flow
    replacements = {
        "packs": "पैक्स", "pack": "पैक", "pouches": "पाउचेस", "pouch": "पाउच",
        "units": "यूनिट्स", "unit": "यूनिट", "stock": "स्टॉक", "count": "काउंट",
        "service": "सर्विस", "center": "सेंटर", "car": "कार", "booking": "बुकिंग",
        "check": "चेक", "confirm": "कंफर्म", "kilometers": "किलोमीटर", "kilometer": "किलोमीटर",
        "km": "किलोमीटर", "okay": "ओके", "ok": "ओके", "sir": "सर", "ma'am": "मैम"
    }
    import re
    for eng, hin in replacements.items():
        # Use regex to match whole words only, handling punctuation and boundaries
        text = re.sub(rf'\b{eng}\b', hin, text, flags=re.IGNORECASE)

    # SAFETY CHECK: Prevent 'zero element' tensor error if text is empty or too short
    clean_text = text.strip()
    if not clean_text or len(clean_text) < 1:
        log.warning("[TTS] Avoiding generation for empty/short text to prevent model crash.")
        return None

    log.info(f"[TTS] Synthesizing with voice: {voice_id or 'default'} in language: {language}")
    
    start = time.time()
    try:
        # 🚀 LATENCY WIN: Serialize GPU access. 
        # Parallel generation causes CUDA contention (1.8s spikes). 
        # Serial access ensures Chunk 0 finishes in ~600ms.
        async with _model_lock:
            loop = asyncio.get_event_loop()
            audio_list = await loop.run_in_executor(_tts_executor, lambda: model.generate(
                text=text,
                ref_audio=ref_audio,
                ref_text=ref_text,
                language=language or "hindi",
                num_inference_steps=num_inference_steps
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

async def stream_tts_to_plivo(text, tts_ctx, plivo_ws, voice_id=None, language="hindi", stream_sid=None):
    """
    Real Streaming: splits text into sentences and plays each as soon as its audio is ready.
    Generates all chunks concurrently to minimize playback gaps.
    """
    import re
    sentences = [s.strip() for s in re.split(r'([।\.?!\n])', text) if s.strip()]
    
    # Re-combine punctuation
    final_chunks = []
    current = ""
    for s in sentences:
        if s in ["।", ".", "?", "!", "\n"]:
            if final_chunks: final_chunks[-1] += s
            else: current += s
        else:
            if current: final_chunks.append(current + s)
            else: final_chunks.append(s)
            current = ""
            
    if not final_chunks:
        return None

    log.info(f"[STREAM] Parallel processing {len(final_chunks)} chunks for SID: {stream_sid}")
    
    # Start all generations concurrently
    async def get_audio(index, sentence):
        # 🚀 QUALITY WIN: Minimum 10 steps for clarity
        steps = 10 if index == 0 else 12 
        key = get_tts_cache_key(sentence, voice_id, language)
        if key in TTS_CACHE:
            return TTS_CACHE[key]
        audio = await omnivoice_tts(sentence, voice_id, language, num_inference_steps=steps)
        if audio: TTS_CACHE[key] = audio
        return audio

    audio_tasks = [get_audio(i, s) for i, s in enumerate(final_chunks)]
    total_mulaw = b""

    # Stream in order
    for task in audio_tasks:
        mulaw = await task
        if not mulaw: continue
        total_mulaw += mulaw

        # Send in chunks to Plivo via the "playAudio" event (Required for Plivo outbound)
        chunk_size = 320 # 40ms (8000hz * 0.04s = 320 samples)
        for j in range(0, len(mulaw), chunk_size):
            chunk = mulaw[j:j+chunk_size]
            try:
                msg = {
                    "event": "playAudio",
                    "media": {
                        "payload": base64.b64encode(chunk).decode(),
                        "contentType": "audio/x-mulaw",
                        "sampleRate": 8000
                    }
                }
                if stream_sid: msg["streamSid"] = stream_sid
                await plivo_ws.send_text(json.dumps(msg))
            except Exception as e:
                log.error(f"[STREAM] WS Send Error: {e}")
                break
            # Buffer management: sleep precisely 40ms to match real-time playback
            await asyncio.sleep(0.04) 

    return total_mulaw

async def pre_connect():
    """Pre-load the model."""
    await _get_model()

def prepare_for_tts(text):
    """Legacy helper for text cleaning."""
    return text.strip()

def get_tts_cache_key(text, voice_id=None, language="hindi"):
    """Helper to generate a consistent cache key."""
    prepared = prepare_for_tts(text)
    return f"{prepared}_{voice_id}_{language}"

def update_tts_cache(text, audio, voice_id=None, language="hindi"):
    """Manually update the TTS cache with audio data."""
    key = get_tts_cache_key(text, voice_id, language)
    TTS_CACHE[key] = audio
    log.info(f"[TTS] Manually updated cache for key: {key[:50]}...")
