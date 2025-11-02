"""Lightweight stub for 'resemble-perth' package used by NeuTTS Air.

This stub prevents import errors when the optional dependency is not
installed. The watermarker here is a no-op.
"""

class PerthImplicitWatermarker:
    def __init__(self, *_, **__):
        pass

    def apply_watermark(self, audio, sample_rate=24000):
        # No-op watermark application
        return audio
