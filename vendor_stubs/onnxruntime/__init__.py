"""Lightweight stub for onnxruntime to allow imports during tests without ONNX installed.
This stub only satisfies module import and basic attribute access; it does not perform inference.
"""

class InferenceSession:
    def __init__(self, *args, **kwargs):
        pass

    def get_inputs(self):
        return []

    def run(self, *args, **kwargs):
        raise RuntimeError("onnxruntime stub: no inference available")

def get_available_providers():
    return ["CPUExecutionProvider"]
