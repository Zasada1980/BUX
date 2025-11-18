"""OCR module with Tesseract integration for receipt processing."""
from __future__ import annotations
import re
import json
import time
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image
import pytesseract

AMOUNT_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[ ,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})(?!\d)")
DATE_RE = re.compile(r"(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[-/.]\d{2}[-/.]\d{4})")


def _norm_amount(s: str) -> Optional[Decimal]:
    """Normalize amount string to Decimal."""
    s = s.replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None


def _best_conf(candidates: List[Tuple[str, int]]) -> Tuple[Optional[str], int]:
    """Return candidate with highest confidence."""
    if not candidates:
        return (None, -1)
    return max(candidates, key=lambda x: x[1])


def run_ocr(path: str, langs: str, min_conf: int, tesseract_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run Tesseract OCR on receipt image.
    
    Args:
        path: Path to image file
        langs: Tesseract language string (e.g., 'eng+rus')
        min_conf: Minimum confidence threshold (0-100)
        tesseract_path: Optional path to tesseract executable
        
    Returns:
        Dict with extracted fields: amount, date, merchant, confidence scores
    """
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    t0 = time.time()
    img = Image.open(path)
    data = pytesseract.image_to_data(img, lang=langs, output_type=pytesseract.Output.DICT)

    amounts: List[Tuple[str, int]] = []
    dates: List[Tuple[str, int]] = []
    merchant: Optional[str] = None
    merchant_conf: int = -1

    n = len(data["text"])
    for i in range(n):
        word = data["text"][i].strip()
        if not word:
            continue
        conf = int(float(data["conf"][i])) if data["conf"][i] not in ("", "-1") else -1
        
        if AMOUNT_RE.fullmatch(word):
            amounts.append((word, conf))
        if DATE_RE.fullmatch(word):
            dates.append((word, conf))
    
    # Merchant heuristic: longest top line with conf >= min_conf
    lines = {}
    for i in range(n):
        lno = data["line_num"][i]
        if lno not in lines:
            lines[lno] = []
        lines[lno].append((data["text"][i].strip(), int(float(data["conf"][i])) if data["conf"][i] not in ("", "-1") else -1))
    
    if lines:
        first_line = max(lines.get(1, []), key=lambda x: len(x[0]) if x[0] else 0) if lines.get(1) else None
        if first_line and first_line[1] >= min_conf and len(first_line[0]) >= 3:
            merchant, merchant_conf = first_line

    best_amount_str, amount_conf = _best_conf(amounts)
    best_date_str, date_conf = _best_conf(dates)
    amount = _norm_amount(best_amount_str) if best_amount_str else None

    confs = [c for _, c in amounts + dates if c >= 0] + ([merchant_conf] if merchant_conf >= 0 else [])
    overall_conf = int(sum(confs) / len(confs)) if confs else -1

    # Unified status: disabled | abstain | ok
    if overall_conf < 0:
        status = "disabled"
    elif overall_conf < min_conf:
        status = "abstain"
    else:
        status = "ok"

    result = {
        "status": status,
        "confidence": overall_conf if overall_conf >= 0 else None,
        "fields": {
            "amount": str(amount) if amount is not None else None,
            "date": best_date_str,
            "merchant": merchant,
        },
        "detail": {
            "amount_conf": amount_conf,
            "date_conf": date_conf,
            "merchant_conf": merchant_conf,
        },
        "duration_ms": int((time.time() - t0) * 1000),
    }
    
    # Deprecated fields for backward compat
    result["abstain"] = (status == "abstain")
    result["amount"] = result["fields"]["amount"]
    result["date"] = result["fields"]["date"]
    result["merchant"] = result["fields"]["merchant"]
    
    return result


# --- OCR Health Detection ---
from dataclasses import dataclass
import subprocess
import shutil


@dataclass
class OCRInfo:
    """Tesseract installation info."""
    ok: bool
    version: str | None
    langs: list[str]


def _detect_tesseract() -> OCRInfo:
    """
    Detect tesseract installation and available languages.
    
    Returns:
        OCRInfo with ok flag, version string, and list of languages
    """
    exe = shutil.which("tesseract")
    if not exe:
        return OCRInfo(False, None, [])
    
    try:
        # Get version
        version_output = subprocess.check_output(
            [exe, "--version"],
            text=True,
            stderr=subprocess.STDOUT
        )
        # Parse first line: "tesseract X.Y.Z"
        version = version_output.splitlines()[0].split()[-1]
        
        # Get languages
        langs_output = subprocess.check_output(
            [exe, "--list-langs"],
            text=True,
            stderr=subprocess.STDOUT
        )
        # Skip first line (header), rest are language codes
        langs = [line.strip() for line in langs_output.splitlines()[1:] if line.strip()]
        
        return OCRInfo(True, version, langs)
    except (subprocess.CalledProcessError, IndexError, OSError):
        return OCRInfo(False, None, [])
