import audioop
import struct
import logging
import torch

log = logging.getLogger(__name__)

# Load model via torch.hub (no silero-vad pip package needed)
_model, _utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False,
    trust_repo=True
)

SAMPLE_RATE = 8000
CHUNK_SAMPLES = 256  # 32ms at 8kHz — required by Silero for 8kHz
SPEECH_THRESHOLD = 0.5
INTERRUPT_THRESHOLD = 0.75  # Telephony interrupt — above echo but below real speech


class SileroVAD:
    """Streaming Silero VAD for 8kHz mu-law telephony audio."""

    def __init__(self):
        self.model = _model
        self._reset_model_state()

    def _reset_model_state(self):
        self.model.reset_states()

    def _get_prob(self, mulaw_chunk: bytes) -> float:
        """Get speech probability for a mu-law audio chunk."""
        pcm = audioop.ulaw2lin(mulaw_chunk, 2)
        num_samples = len(pcm) // 2
        int16_samples = struct.unpack(f'<{num_samples}h', pcm)
        float_samples = [s / 32768.0 for s in int16_samples]

        if len(float_samples) < CHUNK_SAMPLES:
            float_samples += [0.0] * (CHUNK_SAMPLES - len(float_samples))
        elif len(float_samples) > CHUNK_SAMPLES:
            float_samples = float_samples[:CHUNK_SAMPLES]

        tensor = torch.FloatTensor(float_samples)
        return self.model(tensor, SAMPLE_RATE).item()

    def is_speech(self, mulaw_chunk: bytes) -> bool:
        """Normal speech detection (threshold 0.5)."""
        return self._get_prob(mulaw_chunk) >= SPEECH_THRESHOLD

    def is_interrupt(self, mulaw_chunk: bytes) -> bool:
        """High-confidence speech detection for interrupts (threshold 0.85)."""
        return self._get_prob(mulaw_chunk) >= INTERRUPT_THRESHOLD

    def reset(self):
        self._reset_model_state()
