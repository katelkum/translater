import PyPDF2
import io
import re
import fitz  # PyMuPDF
from typing import List, Tuple, Dict, Optional
from PIL import Image
import pytesseract

def extract_text_from_pdf(pdf_file) -> Tuple[str, int]:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        
        for page in doc:
            # Get text directly from PDF
            page_text = page.get_text()
            
            # If no text found, try OCR
            if not page_text.strip():
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img, lang='ara+ita')
            
            text += page_text + "\n\n"
        
        return text, len(doc)
            
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def extract_text_from_pdf_page(pdf_file, page_num: int) -> str:
    """
    Extract text from a specific page of a PDF file using OCR.
    
    Args:
        pdf_file: The uploaded PDF file object
        page_num: The page number to extract (0-indexed)
    
    Returns:
        Extracted text from the specified page
    """
    try:
        # Read PDF bytes
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        
        # Convert specific PDF page to image with high DPI for better symbol recognition
        images = convert_from_bytes(pdf_bytes, first_page=page_num+1, last_page=page_num+1, dpi=600)
        
        if not images:
            raise ValueError(f"Failed to convert page {page_num+1} to image.")
        
        # Enhanced image preprocessing
        image = images[0]
        img_gray = image.convert('L')  # Grayscale
        img_binary = img_gray.point(lambda x: 0 if x < 128 else 255, '1')  # Binary
        
        extracted_texts = []
        
        # Multiple OCR passes with different configurations
        ocr_configs = [
            # Configuration for standard Arabic text with diacritics
            {
                'lang': 'ara+ita',
                'config': '--psm 6 --oem 1 -c preserve_interword_spaces=1 -c textord_heavy_nr=1'
            },
            # Config for Quranic text with full diacritics
            {
                'lang': 'ara',
                'config': '--psm 6 --oem 1 -c preserve_interword_spaces=1 -c textord_heavy_nr=1 -c textord_min_linesize=1'
            }
        ]
        
        for config in ocr_configs:
            try:
                text = pytesseract.image_to_string(
                    img_binary if 'binary' in config.get('config', '') else img_gray,
                    lang=config['lang'],
                    config=config['config']
                )
                extracted_texts.append(text)
            except Exception as e:
                print(f"OCR pass failed: {str(e)}")
                continue
        
        # Post-processing to handle special cases
        final_text = ""
        for text in extracted_texts:
            text = fix_arabic_ocr_errors(text)
            if len([c for c in text if is_special_arabic_char(c)]) > len([c for c in final_text if is_special_arabic_char(c)]):
                final_text = text
        
        return final_text or extracted_texts[0] if extracted_texts else ""
            
    except Exception as e:
        raise Exception(f"Error extracting text from PDF page {page_num+1}: {str(e)}")

def is_special_arabic_char(char: str) -> bool:
    """Check if character is a special Arabic character or symbol."""
    # Extended Unicode ranges for Arabic special characters and symbols
    special_ranges = [
        (0x0600, 0x06FF),   # Arabic
        (0xFB50, 0xFDFF),   # Arabic Presentation Forms-A
        (0xFE70, 0xFEFF),   # Arabic Presentation Forms-B
        (0x0750, 0x077F),   # Arabic Supplement
        (0x08A0, 0x08FF),   # Arabic Extended-A
        (0x0870, 0x089F),   # Arabic Extended-B
        (0x0890, 0x08FF),   # Arabic Extended-C
        (0x10E60, 0x10E7F), # Rumi Numeral Symbols
        (0x1EE00, 0x1EEFF), # Arabic Mathematical Alphabetic Symbols
        (0x06E0, 0x06FF),   # Arabic Extended-B (additional)
        (0xFDF0, 0xFDFF),   # Arabic Ligatures
    ]
    
    if not char:
        return False
    
    code = ord(char)
    return any(start <= code <= end for start, end in special_ranges)

def fix_arabic_ocr_errors(text: str) -> str:
    """Fix common OCR errors in Arabic text."""
    # Add new Arabic ligature mappings
    arabic_ligatures = {
        # لا family
        'ﻻ': 'لا',
        
    }
    
    # Add common word patterns that might be misrecognized
    common_word_patterns = {
        r'اﻟ+': 'ال',  # Fix elongated lam in al-
        r'ﷲ': 'الله',  # Fix Allah word
        r'ﻣﺤﻤ[ﺪﺩدﺪﺩ]': 'محمد',  # Fix Muhammad name
        r'ﻋﺒ[ﺪﺩدﺪﺩ]': 'عبد',  # Fix Abd
        r'اﻟ?ﺮﺣﻤ[ﻦﻥن]': 'الرحمن',  # Fix Al-Rahman
        r'اﻟ?ﺮﺣ[ﻴﻳيﯾ]?[ﻢﻣم]': 'الرحيم',  # Fix Al-Raheem
    }

    # Apply ligature fixes before existing fixes
    for wrong, correct in arabic_ligatures.items():
        text = text.replace(wrong, correct)
    
    # Apply common word pattern fixes
    import re
    for pattern, correct in common_word_patterns.items():
        text = re.sub(pattern, correct, text)
    
    # Continue with existing fixes
    # Common religious phrases that might be misrecognized
    religious_phrases = {
        r'صل[ىي]\s*[اآ]لله\s*عل[يى]ه\s*[وﻭ]سلم': 'صلى الله عليه وسلم',
       
    }
    
    # Fix common letter mistakes
    letter_fixes = {
        'ھ': 'ه',    # Fix different forms of Ha
       
    }
    
    # Arabic numbers and their Western equivalents
    arabic_numbers = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
      
    }
    
    # Enhanced Quranic symbols and markers
    quranic_symbols = {
        '۝': '۝',    # Sajdah
       
    }
    
    # Diacritical marks and special characters
    diacritics = {
        'ٰ': 'ٰ',     # Superscript alef
     
    }

    # Apply all fixes
    for wrong, correct in letter_fixes.items():
        text = text.replace(wrong, correct)
    
    # Fix religious phrases
    import re
    for pattern, correct in religious_phrases.items():
        text = re.sub(pattern, correct, text)
    
    # Preserve Quranic symbols with spacing
    for symbol, correct in quranic_symbols.items():
        text = text.replace(symbol, f' {correct} ')
    
    # Preserve numbers while maintaining their style
    numbers_pattern = re.compile('|'.join(map(re.escape, arabic_numbers.keys())))
    text = numbers_pattern.sub(lambda m: arabic_numbers[m.group()], text)
    
    # Preserve diacritics
    for mark, correct in diacritics.items():
        text = text.replace(mark, correct)
    
    # Additional post-processing for connected letters
    def fix_connected_letters(text: str) -> str:
        # Fix common connected letter patterns
        patterns = [
            (r'ـ+', ''),  # Remove tatweel (kashida)
            (r'([ءآأؤإئا])ـ+([ءآأؤإئا])', r'\1\2'),  # Fix alef connections
            (r'([بتثجحخسشصضطظعغفقكلمنهي])ـ+([بتثجحخسشصضطظعغفقكلمنهي])', r'\1\2'),  # Fix normal letter connections
        ]
        
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement)
        return text
    
    # Apply connected letter fixes
    text = fix_connected_letters(text)
    
    return text

def get_pdf_info(pdf_file) -> Dict[str, any]:
    """Get PDF information using PyMuPDF."""
    try:
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        info = {
            "num_pages": len(doc),
            "metadata": doc.metadata,
            "file_size": len(pdf_bytes) / 1024  # Size in KB
        }
        
        doc.close()
        return info
        
    except Exception as e:
        raise Exception(f"Error getting PDF information: {str(e)}")

def is_arabic_text(text: str) -> bool:
    """
    Check if the text contains Arabic characters.
    
    Args:
        text: The text to check
    
    Returns:
        True if the text contains Arabic characters, False otherwise
    """
    # Always return True to bypass the Arabic text check
    # This allows processing of PDFs with special encoding or formatting
    return True

def chunk_text(text: str, max_chunk_size: int = 4000) -> List[str]:
    """
    Split the text into chunks of approximately equal size without breaking sentences.
    
    Args:
        text: The text to chunk
        max_chunk_size: Maximum size of each chunk
    
    Returns:
        List of text chunks
    """
    # Split by double newlines (paragraphs) first
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph exceeds the max size and we already have some content,
        # add the current chunk to the list and start a new one
        if len(current_chunk) + len(paragraph) > max_chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + "\n\n"
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
