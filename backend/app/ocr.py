"""OCR provider boundary; the optional local Tesseract provider is opt-in."""
import os
from typing import Protocol
class OCRProvider(Protocol):
    async def extract_text(self, image: bytes, content_type: str) -> str: ...
class DisabledOCR:
    async def extract_text(self, image: bytes, content_type: str) -> str:
        raise RuntimeError('OCR provider is not configured')

class TesseractOCR:
    async def extract_text(self, image: bytes, content_type: str) -> str:
        # Imports stay lazy so installations without OCR retain the default behavior.
        from io import BytesIO
        from PIL import Image
        import pytesseract
        command = os.getenv('TESSERACT_CMD')
        if command:
            pytesseract.pytesseract.tesseract_cmd = command
        with Image.open(BytesIO(image)) as opened:
            if opened.width * opened.height > 24_000_000:
                raise ValueError('Image dimensions are too large for OCR')
            opened.load()
            try:
                return pytesseract.image_to_string(opened, lang=os.getenv('TESSERACT_LANG','eng')).strip()
            except pytesseract.TesseractNotFoundError as exc:
                raise RuntimeError('Tesseract executable is not installed or configured') from exc

def configured_ocr() -> OCRProvider:
    if os.getenv('OCR_PROVIDER', '').lower() == 'tesseract':
        return TesseractOCR()
    return DisabledOCR()
