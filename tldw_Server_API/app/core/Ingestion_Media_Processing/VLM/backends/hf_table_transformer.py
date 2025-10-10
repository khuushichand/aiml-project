from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from ..base import VLMBackend, VLMDetection, VLMResult


class HFTableTransformerBackend(VLMBackend):
    """
    Hugging Face Table Transformer detector backend.

    Uses microsoft/table-transformer-detection (DETR) via transformers to detect tables.

    Environment variables:
      - VLM_TABLE_MODEL_NAME: HF model id or local path (default: 'microsoft/table-transformer-detection')
      - VLM_TABLE_REVISION: Optional git revision/sha
    """

    name = "hf_table_transformer"

    def __init__(self, model_name: Optional[str] = None, revision: Optional[str] = None):
        self._loaded = False
        self._model_name = model_name or (  # default model
            __import__("os").getenv("VLM_TABLE_MODEL_NAME", "microsoft/table-transformer-detection")
        )
        self._revision = revision or __import__("os").getenv("VLM_TABLE_REVISION")
        self._processor = None
        self._model = None

    @classmethod
    def available(cls) -> bool:
        try:
            import transformers  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception:
            return False
        return True

    def _lazy_load(self):
        if self._loaded:
            return
        from transformers import AutoImageProcessor, AutoModelForObjectDetection
        self._processor = AutoImageProcessor.from_pretrained(self._model_name, revision=self._revision)
        self._model = AutoModelForObjectDetection.from_pretrained(self._model_name, revision=self._revision)
        self._loaded = True

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model": self._model_name,
            "revision": self._revision,
            "available": self.available(),
        }

    def process_image(
        self,
        image_bytes: bytes,
        *,
        mime_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VLMResult:
        self._lazy_load()

        # Load PIL image
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        outputs = self._model(**inputs)

        # Post-process
        target_sizes = [image.size[::-1]]  # (height, width)
        results = self._processor.post_process_object_detection(outputs, threshold=0.5, target_sizes=target_sizes)[0]

        detections: List[VLMDetection] = []
        for score, label_id, box in zip(results["scores"], results["labels"], results["boxes"]):
            # Convert tensors
            s = float(score.detach().cpu().item())
            lbl = int(label_id.detach().cpu().item())
            bbox = [float(x) for x in box.detach().cpu().tolist()]  # [x0,y0,x1,y1]

            # Most table-transformer models use a single class (table) with id 0; keep label text generic
            label_text = "table" if lbl == 0 else str(lbl)

            md = {"page": (context or {}).get("page"), "label_id": lbl}
            detections.append(VLMDetection(label=label_text, score=s, bbox=bbox, metadata=md))

        return VLMResult(detections=detections, texts=None, extra={"page": (context or {}).get("page")})

