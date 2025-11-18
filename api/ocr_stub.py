"""OCR stub for photo description extraction."""


def ocr_extract_description(photo_ref: str | None) -> str | None:
    """
    Extract text description from photo (stub implementation).
    
    Args:
        photo_ref: Photo file reference/path
        
    Returns:
        Extracted text or None if no photo
        
    Note:
        This is a stub. Real implementation would use tesseract/pytesseract.
        For now, returns a mock reference to the filename.
    """
    if not photo_ref:
        return None
    return f"ocr_stub:{photo_ref.split('/')[-1]}"
