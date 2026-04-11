import audioop


def linear16_to_mulaw_8k(l16_bytes):
    if not l16_bytes:
        return None
    resampled, _ = audioop.ratecv(l16_bytes, 2, 1, 16000, 8000, None)
    return audioop.lin2ulaw(resampled, 2)
