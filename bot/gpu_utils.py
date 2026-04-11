import torch
import logging

log = logging.getLogger(__name__)

def get_device():
    """Detect and return the best available device."""
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        # Intel Macs with specific GPUs might support MPS, 
        # but it's most stable on Apple Silicon.
        return "mps"
    return "cpu"

def get_dtype():
    """Return appropriate dtype based on device."""
    device = get_device()
    if device == "cuda":
        return torch.float16
    # CPU and MPS on older hardware work best with float32
    return torch.float32

def log_device_info():
    """Log details about the current hardware acceleration."""
    device = get_device()
    dtype = get_dtype()
    log.info(f"[GPU-UTILS] Device: {device} | Dtype: {dtype}")
    
    if device == "mps":
        log.info("[GPU-UTILS] Using Apple Metal Performance Shaders (MPS) for acceleration.")
    elif device == "cuda":
        log.info("[GPU-UTILS] Using NVIDIA CUDA for acceleration.")
    else:
        log.info("[GPU-UTILS] Using CPU. Performance may be limited.")
