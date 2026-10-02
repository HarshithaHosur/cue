# ============================================================
#  HIGH-PRECISION OCR ENGINE
#  Combines EasyOCR (preferred) and Tesseract (fallback) with
#  intelligent text/error extraction for terminals, code & UI.
# ============================================================

import os
import re
import io
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

# ── EasyOCR Import Check ──
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# ── PyTesseract Import Check ──
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


class HighPrecisionOCREngine:
    """
    High-precision OCR Engine.
    Prioritizes EasyOCR for modern deep learning scene text & UI recognition;
    falls back to PyTesseract; gracefully handles environments where OCR libraries
    are pending installation.
    """

    # Regex patterns for terminal / code errors
    ERROR_PATTERNS = [
        re.compile(r'(?:Traceback \(most recent call last\):)', re.IGNORECASE),
        re.compile(r'([A-Za-z0-9_]+Error|Exception|Failed|FATAL|Crash):\s*(.+)', re.IGNORECASE),
        re.compile(r'File "([^"]+)", line (\d+)(?:, in (.+))?', re.IGNORECASE),
        re.compile(r'(?:line (\d+)|at line (\d+))', re.IGNORECASE),
        re.compile(r'(?:SyntaxError|TypeError|ValueError|IndexError|KeyError|NameError|ImportError|ModuleNotFoundError|AttributeError|FileNotFoundError)', re.IGNORECASE),
        re.compile(r'(?:Cannot find module|No module named [\'"]([^\'"]+)[\'"])', re.IGNORECASE),
        re.compile(r'(?:npm ERR!|error TS\d+:|exit code \d+|failed with exit code)', re.IGNORECASE)
    ]

    def __init__(self, languages: Optional[List[str]] = None, use_gpu: bool = False):
        self.languages = languages or ['en']
        self.use_gpu = use_gpu
        self._easyocr_reader = None
        self._reader_init_attempted = False
        self.engine_name = "None"

        if EASYOCR_AVAILABLE:
            self.engine_name = "EasyOCR"
        elif PYTESSERACT_AVAILABLE:
            self.engine_name = "PyTesseract"

    def _get_easyocr_reader(self):
        """Lazy loader for EasyOCR to prevent slow app startup times."""
        if not EASYOCR_AVAILABLE:
            return None
        if not self._reader_init_attempted:
            self._reader_init_attempted = True
            try:
                # Initialize EasyOCR reader with specified languages
                self._easyocr_reader = easyocr.Reader(self.languages, gpu=self.use_gpu)
                print("[OCR] EasyOCR Reader initialized successfully.")
            except Exception as e:
                print(f"[OCR] EasyOCR init warning: {e}. Will fallback to Tesseract or heuristic.")
                self._easyocr_reader = None
        return self._easyocr_reader

    def extract_text(self, image_input: Any) -> Dict[str, Any]:
        """
        Extracts structured text from an image (bytes, PIL Image, or numpy array).
        Returns:
            {
                "engine": str,
                "full_text": str,
                "lines": List[str],
                "blocks": List[Dict[str, Any]], # bbox, text, confidence
                "average_confidence": float,
                "detected_errors": List[Dict[str, Any]],
                "is_terminal_like": bool
            }
        """
        # Convert bytes to PIL Image if needed
        pil_img = None
        if isinstance(image_input, bytes):
            try:
                pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
            except Exception as e:
                print(f"[OCR] Image open error: {e}")
                return self._empty_result()
        elif isinstance(image_input, Image.Image):
            pil_img = image_input.convert("RGB")
        else:
            return self._empty_result()

        # 1. Try EasyOCR first
        easy_reader = self._get_easyocr_reader()
        if easy_reader:
            try:
                import numpy as np
                img_np = np.array(pil_img)
                results = easy_reader.readtext(img_np)
                # results is list of tuple: (bbox, text, prob)
                blocks = []
                lines = []
                total_conf = 0.0

                for bbox, text, prob in results:
                    clean_text = text.strip()
                    if not clean_text:
                        continue
                    # bbox: [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                    blocks.append({
                        "text": clean_text,
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": float(prob)
                    })
                    lines.append(clean_text)
                    total_conf += float(prob)

                avg_conf = total_conf / max(1, len(blocks))
                full_text = "\n".join(lines)
                errors = self._parse_errors(full_text)

                return {
                    "engine": "EasyOCR",
                    "full_text": full_text,
                    "lines": lines,
                    "blocks": blocks,
                    "average_confidence": round(avg_conf, 3),
                    "detected_errors": errors,
                    "is_terminal_like": len(errors) > 0 or "traceback" in full_text.lower()
                }
            except Exception as e:
                print(f"[OCR] EasyOCR readtext error: {e}. Trying PyTesseract fallback...")

        # 2. Try PyTesseract fallback
        if PYTESSERACT_AVAILABLE:
            try:
                data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
                blocks = []
                lines = []
                total_conf = 0.0
                conf_count = 0

                n_boxes = len(data['text'])
                current_line = []
                last_line_num = -1

                for i in range(n_boxes):
                    t = data['text'][i].strip()
                    conf = float(data['conf'][i])
                    if conf > 0 and t:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        blocks.append({
                            "text": t,
                            "bbox": [x, y, x + w, y + h],
                            "confidence": round(conf / 100.0, 3)
                        })
                        total_conf += (conf / 100.0)
                        conf_count += 1
                        
                        line_num = data['line_num'][i]
                        if line_num != last_line_num and current_line:
                            lines.append(" ".join(current_line))
                            current_line = []
                        current_line.append(t)
                        last_line_num = line_num

                if current_line:
                    lines.append(" ".join(current_line))

                avg_conf = total_conf / max(1, conf_count)
                full_text = "\n".join(lines)
                errors = self._parse_errors(full_text)

                return {
                    "engine": "PyTesseract",
                    "full_text": full_text,
                    "lines": lines,
                    "blocks": blocks,
                    "average_confidence": round(avg_conf, 3),
                    "detected_errors": errors,
                    "is_terminal_like": len(errors) > 0 or "traceback" in full_text.lower()
                }
            except Exception as e:
                print(f"[OCR] PyTesseract execution error: {e}")

        # 3. Fallback when OCR packages are not yet installed
        return {
            "engine": "Fallback Heuristic",
            "full_text": "",
            "lines": [],
            "blocks": [],
            "average_confidence": 0.0,
            "detected_errors": [],
            "is_terminal_like": False
        }

    def _parse_errors(self, text: str) -> List[Dict[str, Any]]:
        """Parses error lines, exception types, file paths, and line numbers."""
        errors = []
        if not text:
            return errors

        lines = text.splitlines()
        for idx, line in enumerate(lines):
            line_str = line.strip()
            for pattern in self.ERROR_PATTERNS:
                m = pattern.search(line_str)
                if m:
                    errors.append({
                        "line_index": idx,
                        "raw_line": line_str,
                        "matched": m.group(0)
                    })
                    break
        return errors

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "engine": "None",
            "full_text": "",
            "lines": [],
            "blocks": [],
            "average_confidence": 0.0,
            "detected_errors": [],
            "is_terminal_like": False
        }
