import os
import shutil
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from database import create_voice, list_voices, delete_voice, get_voice

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
    # Note: We store the relative path or absolute path. 
    # For now, let's store the absolute path for ease of loading.
    voice = create_voice(name, filepath, ref_text)
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
