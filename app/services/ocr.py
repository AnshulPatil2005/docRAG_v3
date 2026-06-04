import fitz  # PyMuPDF
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
import torch
import os
import structlog

logger = structlog.get_logger()

# Initialize predictor once if possible?
# But Celery forks, so it should be initialized per process or lazily.
# We'll initialize lazily inside the function for now, or use a global that is initialized on first use.

_predictor = None

def get_predictor():
    global _predictor
    if _predictor is None:
        # Check for GPU
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading Doctr model on {device}")
        try:
            _predictor = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True).to(device)
        except Exception as e:
             logger.error(f"Failed to load Doctr model: {e}")
             raise e
    return _predictor

def extract_text_from_pdf(file_path: str):
    """
    Extracts text from PDF using Doctr for OCR.
    Fallback to pymupdf text extraction if needed?
    Requirement says: "Extract pages using pdfminer or pymupdf" -> "Run doctr for OCR"
    It implies we might want to convert PDF pages to images first using pymupdf, then run doctr.
    Doctr's `DocumentFile.from_pdf` uses pymupdf (fitz) or pdfminer under the hood.
    """
    
    try:
        # We can try PyMuPDF to get text directly first (faster)
        # But requirement says "PDF-only async OCR ... Run doctr for OCR".
        # It seems OCR is mandatory or preferred.
        # "OCR: doctr (preferred) or pytesseract as fallback"
        
        # Let's use Doctr.
        # Loading large PDFs into Doctr at once might consume too much memory.
        # "Handle large PDFs efficiently via streaming or chunked OCR"
        
        # We should iterate pages using PyMuPDF, render to image, then OCR each image.
        
        doc = fitz.open(file_path)
        results = []
        predictor = get_predictor()
        
        for page_num, page in enumerate(doc):
            # Render page to image
            # Zoom = 2 for better resolution
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            # Convert to numpy array? Doctr expects list of numpy arrays or file paths.
            # We can save to temp file or convert in memory.
            # To avoid temp files, we can use bytes -> numpy.
            
            # fitz pixmap to bytes
            img_bytes = pix.tobytes("png")
            
            # Doctr from_images expects list of numpy arrays or paths.
            # DocumentFile.from_images accepts bytes? No.
            # But we can decode bytes to numpy using cv2 or similar if available, or just save temp.
            # Saving temp is safer for memory sometimes if we process one by one.
            
            # Actually, `DocumentFile.from_pdf` handles this, but does it handle large files well?
            # It loads the whole doc.
            # Better to do page by page.
            
            # Let's stick to a simple flow:
            # DocumentFile.from_pdf might be fine if we pass one page at a time?
            # No, it takes the file.
            
            # Correct approach for large PDFs:
            # Open with fitz, extract pages as images, pass images to Doctr.
            
            # Optimization: Doctr can process batches.
            
            import numpy as np
            import cv2
            
            # Convert bytes to numpy
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            # img is BGR, Doctr expects RGB? 
            # Doctr docs say: "Images are expected to be in channels_last format (H, W, C) and RGB."
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Run OCR
            # We can accumulate a batch of pages if we want, but simple loop is safer for memory.
            result = predictor([img])
            
            # Extract text
            page_text = ""
            for block in result.pages[0].blocks:
                for line in block.lines:
                    for word in line.words:
                         page_text += word.value + " "
                    page_text += "\n"
            
            results.append((page_num + 1, page_text.strip()))
            
        doc.close()
        return results

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        # Fallback? Pytesseract?
        # Or just raise.
        raise e
