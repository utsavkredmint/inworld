import os
import shutil
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from database import create_voice, list_voices, delete_voice, get_voice
from services.tts import _get_model, _resolve_audio_path, tensor_to_wav, DEFAULT_REF_TEXT
import asyncio

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voices", tags=["voices"])

VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voices")
os.makedirs(VOICES_DIR, exist_ok=True)

@router.get("")
async def fetch_voices():
    """List all available cloned voices."""
    return list_voices()

@router.post("/clone")
async def clone_voice(
    name: str = Form(...),
    ref_text: Optional[str] = Form(""),
    language: Optional[str] = Form("hindi"),
    file: UploadFile = File(...)
):
    """
    Upload a reference audio file and save it as a new voice.
    Expected formats: .wav, .mp3
    """
    # 1. Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".wav", ".mp3"]:
        raise HTTPException(status_code=400, detail="Only .wav and .mp3 files are supported.")

    # 2. Save file locally
    voice_id = uuid.uuid4().hex[:12]
    filename = f"{voice_id}{ext}"
    filepath = os.path.join(VOICES_DIR, filename)
    
    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        log.error(f"[VOICES] Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save audio file.")

    # 3. Save to database
    voice = create_voice(name, filepath, ref_text, language)
    log.info(f"[VOICES] Cloned new voice: {name} ({voice_id})")
    return voice

@router.delete("/{voice_id}")
async def remove_voice(voice_id: str):
    """Delete a cloned voice and its associated file."""
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    # 1. Delete file
    if os.path.exists(voice["ref_audio_path"]):
        try:
            os.remove(voice["ref_audio_path"])
        except Exception as e:
            log.warning(f"[VOICES] Failed to delete file {voice['ref_audio_path']}: {e}")

    # 2. Delete from database
    delete_voice(voice_id)
    log.info(f"[VOICES] Deleted voice: {voice_id}")
    return {"status": "success"}

@router.get("/{voice_id}/test")
async def test_voice(voice_id: str, text: Optional[str] = None, language: Optional[str] = "hindi"):
    """Generate a test audio clip for a voice and return it as WAV."""
    voice = get_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    model = await _get_model()
    if not model:
        raise HTTPException(status_code=500, detail="TTS model not available")

    # Use provided text or default
    sample_text = text or f"Hello! This is a test of the {voice['name']} voice. I hope you like how I sound!"
    ref_audio = _resolve_audio_path(voice["ref_audio_path"])
    ref_text = voice["ref_text"] or DEFAULT_REF_TEXT

    try:
        log.info(f"[VOICES] Generating test clip for {voice_id} in {language}...")
        loop = asyncio.get_event_loop()
        audio_list = await loop.run_in_executor(None, lambda: model.generate(
            text=sample_text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            language=language or "hindi"
        ))
        
        if not audio_list or len(audio_list) == 0:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
            
        wav_bytes = tensor_to_wav(audio_list[0])
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        log.error(f"[VOICES] Test generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
