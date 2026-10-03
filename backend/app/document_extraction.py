"""In-memory validation and text extraction for supported uploaded files."""
import re
import ntpath

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 12_000
MAX_PDF_PAGES = 20

SIGNATURES = {
    'image/png': lambda data: data.startswith(b'\x89PNG\r\n\x1a\n'),
    'image/jpeg': lambda data: data.startswith(b'\xff\xd8\xff'),
    'image/webp': lambda data: len(data) >= 12 and data.startswith(b'RIFF') and data[8:12] == b'WEBP',
    'application/pdf': lambda data: data.startswith(b'%PDF-'),
}

def sanitize_filename(filename: str | None) -> str:
    """Return a display-only basename; never use client filenames as paths."""
    base = ntpath.basename((filename or 'upload').replace('/', '\\'))
    safe = re.sub(r'[^A-Za-z0-9._-]+', '_', base).strip('._')[:120]
    return safe or 'upload'

def validate_upload(data: bytes, content_type: str, filename: str | None) -> tuple[str, str]:
    if content_type not in SIGNATURES:
        raise ValueError('Supported files are PNG, JPG, JPEG, WEBP, and PDF.')
    limit = MAX_IMAGE_BYTES if content_type.startswith('image/') else MAX_FILE_BYTES
    if not data:
        raise ValueError('The uploaded file is empty.')
    if len(data) > limit:
        raise OverflowError(f'This file exceeds the {limit // (1024 * 1024)} MB size limit.')
    if not SIGNATURES[content_type](data):
        raise ValueError('The file contents do not match the selected file type.')
    return content_type, sanitize_filename(filename)

async def extract_document(data: bytes, content_type: str) -> tuple[str, str]:
    """Extract text in memory. Returns (text, method); temporary data is not saved."""
    if content_type.startswith('image/'):
        from app.ocr import configured_ocr
        text = await configured_ocr().extract_text(data, content_type)
        return text[:MAX_TEXT_CHARS], 'OCR'

    import fitz
    try:
        pdf = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        raise ValueError('The PDF could not be opened. It may be damaged or encrypted.') from exc
    try:
        if pdf.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Paste the text manually.')
        if pdf.page_count > MAX_PDF_PAGES:
            raise ValueError(f'PDFs are limited to {MAX_PDF_PAGES} pages.')
        parts = []
        for page in pdf:
            remaining = MAX_TEXT_CHARS - sum(len(part) for part in parts)
            if remaining <= 0:
                break
            parts.append(page.get_text('text')[:remaining])
        text = '\n'.join(parts).strip()
        method = 'PDF text extraction'
        if not text:
            from app.ocr import configured_ocr
            ocr = configured_ocr()
            for page in pdf:
                if page.rect.width * page.rect.height * 2.25 > 24_000_000:
                    raise ValueError('A PDF page is too large for OCR processing.')
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                text += (await ocr.extract_text(pixmap.tobytes('png'), 'image/png')) + '\n'
                if len(text) >= MAX_TEXT_CHARS:
                    break
            text = text[:MAX_TEXT_CHARS].strip()
            method = 'PDF page OCR'
        return text, method
    finally:
        pdf.close()
