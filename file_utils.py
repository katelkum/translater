import fitz
from PIL import Image
import docx2txt
import io
from typing import Dict, Any

def process_pdf_file(file) -> Dict[str, Any]:
    """Process PDF file and return info."""
    pdf_bytes = file.getvalue()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    info = {
        "num_pages": len(doc),
        "metadata": doc.metadata,
        "file_size": len(pdf_bytes) / 1024,  # Size in KB
        "file_type": "pdf"
    }
    
    doc.close()
    return info

def process_image_file(file) -> Dict[str, Any]:
    """Process image file and return info."""
    img_bytes = file.getvalue()
    img = Image.open(io.BytesIO(img_bytes))
    
    info = {
        "num_pages": 1,
        "metadata": {
            "format": img.format,
            "size": img.size,
            "mode": img.mode
        },
        "file_size": len(img_bytes) / 1024,  # Size in KB
        "file_type": "image"
    }
    
    return info

def process_docx_file(file) -> Dict[str, Any]:
    """Process DOCX file and return info."""
    docx_bytes = file.getvalue()
    text = docx2txt.process(io.BytesIO(docx_bytes))
    
    # Estimate pages based on character count (rough estimate)
    char_per_page = 3000
    estimated_pages = max(1, len(text) // char_per_page)
    
    info = {
        "num_pages": estimated_pages,
        "metadata": {
            "content_length": len(text)
        },
        "file_size": len(docx_bytes) / 1024,  # Size in KB
        "file_type": "docx"
    }
    
    return info
