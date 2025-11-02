from __future__ import annotations

import shutil
import subprocess
import tempfile
from typing import Optional

from tldw_Server_API.app.core.Ingestion_Media_Processing.OCR.base import OCRBackend


class TesseractCLIBackend(OCRBackend):
    """
    OCR backend that shells out to the `tesseract` CLI if installed.

    Pros: no heavy Python deps; uses system-installed Tesseract.
    Cons: requires `tesseract` binary to be present on PATH.
    """

    name = "tesseract"

    @classmethod
    def available(cls) -> bool:
        return shutil.which("tesseract") is not None

    def ocr_image(self, image_bytes: bytes, lang: Optional[str] = None) -> str:
        lang = lang or "eng"
        # Write bytes to a temp PNG and call: tesseract input.png stdout -l <lang>
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as img_tmp:
            img_tmp.write(image_bytes)
            img_tmp.flush()

            cmd = ["tesseract", img_tmp.name, "stdout", "-l", lang]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return proc.stdout or ""
            except subprocess.CalledProcessError as e:
                # Return stderr content as hint; ingestion layer will treat as empty text
                return e.stdout or ""
