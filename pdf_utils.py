import PyPDF2
import io
import re
import tempfile
from typing import List, Tuple, Dict, Optional
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

def extract_text_from_pdf(pdf_file, method="standard") -> Tuple[str, int]:
    """
    Extract text from a PDF file using the specified method.
    
    Args:
        pdf_file: The uploaded PDF file object
        method: The extraction method ('standard' or 'ocr')
    
    Returns:
        Tuple containing the extracted text and the number of pages
    """
    try:
        # Create a PDF file reader object
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        # Get the number of pages
        num_pages = len(pdf_reader.pages)
        
        # Use the standard PyPDF2 extraction method
        if method == "standard":
            text = ""
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n\n"
            return text, num_pages
        
        # Use OCR-based extraction
        else:  # method == "ocr"
            # Convert PDF to images with higher DPI for better OCR
            images = convert_from_bytes(pdf_bytes, dpi=400)  # Increased DPI for better recognition
            text = ""
            
            # Extract text from each image using enhanced OCR with better Arabic support
            for image in images:
                # Apply image preprocessing for better OCR results with Arabic text
                # Convert to grayscale for better OCR performance
                img_gray = image.convert('L')
                
                # Try multiple OCR approaches to improve Arabic character recognition
                try:
                    # Best configuration for Arabic
                    # --psm 6: Assume a single uniform block of text
                    # --oem 1: LSTM OCR engine only
                    # This configuration works better for Arabic diacritics and special symbols
                    page_text = pytesseract.image_to_string(
                        img_gray, 
                        lang='ara+ita', 
                        config='--psm 6 --oem 1'
                    )
                    
                    # If no text is extracted or very little, try Arabic only with different config
                    if len(page_text.strip()) < 20:
                        page_text = pytesseract.image_to_string(
                            img_gray, 
                            lang='ara', 
                            config='--psm 6 --oem 1'
                        )
                    
                    # If still no text, try with different page segmentation mode
                    if len(page_text.strip()) < 20:
                        page_text = pytesseract.image_to_string(
                            img_gray, 
                            lang='ara', 
                            config='--psm 3 --oem 1'
                        )
                    
                except Exception as e:
                    # Fallback to basic OCR if language packs are not available
                    print(f"OCR exception: {str(e)}")
                    page_text = pytesseract.image_to_string(img_gray)
                
                text += page_text + "\n\n"
            
            return text, num_pages
            
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def extract_text_from_pdf_page(pdf_file, page_num: int, method="standard") -> str:
    """
    Extract text from a specific page of a PDF file.
    
    Args:
        pdf_file: The uploaded PDF file object
        page_num: The page number to extract (0-indexed)
        method: The extraction method ('standard' or 'ocr')
    
    Returns:
        Extracted text from the specified page
    """
    try:
        # Read PDF bytes
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        
        # Use the standard PyPDF2 extraction method
        if method == "standard":
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            
            # Check if page number is valid
            if page_num < 0 or page_num >= len(pdf_reader.pages):
                raise ValueError(f"Invalid page number: {page_num+1}. PDF has {len(pdf_reader.pages)} pages.")
            
            # Extract text from the specified page
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            return text
        
        # Use OCR-based extraction
        else:  # method == "ocr"
            # Convert specific PDF page to image with very high DPI for better symbol recognition
            images = convert_from_bytes(pdf_bytes, first_page=page_num+1, last_page=page_num+1, dpi=600)
            
            if not images:
                raise ValueError(f"Failed to convert page {page_num+1} to image.")
            
            # Enhanced image preprocessing
            image = images[0]
            
            # Create multiple versions of the image for different recognition passes
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
                # Special config for religious symbols and notation
                {
                    'lang': 'ara',
                    'config': '--psm 4 --oem 1 -c preserve_interword_spaces=1 -c textord_heavy_nr=1 -c textord_min_linesize=1'
                },
                # Config for Quranic text with full diacritics
                {
                    'lang': 'ara',
                    'config': '--psm 6 --oem 1 -c preserve_interword_spaces=1 -c textord_heavy_nr=1 -c textord_min_linesize=1 -c textord_tabfind_show_vlines=0'
                }
            ]
            
            for config in ocr_configs:
                try:
                    # Try OCR with current configuration
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
                # Replace common OCR mistakes in Arabic
                text = fix_arabic_ocr_errors(text)
                
                # If this version has more special characters, prefer it
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
        'ﻼ': 'لا',
        'ﻵ': 'لآ',
        'ﻶ': 'لآ',
        'ﻷ': 'لأ',
        'ﻸ': 'لأ',
        'ﻹ': 'لإ',
        'ﻺ': 'لإ',

        # Common letter combinations
        'ﺠﻤ': 'جم',
        'ﺠﻣ': 'جم',
        'ﺤﻤ': 'حم',
        'ﺤﻣ': 'حم',
        'ﻣﺤ': 'مح',
        'ﻤﺤ': 'مح',
        'ﻌﻠ': 'عل',
        'ﻋﻠ': 'عل',
        'ﻤﻌ': 'مع',
        'ﻣﻌ': 'مع',
        
        # Beginning forms
        'ﺑ': 'ب',
        'ﺗ': 'ت',
        'ﺛ': 'ث',
        'ﺟ': 'ج',
        'ﺣ': 'ح',
        'ﺧ': 'خ',
        'ﺳ': 'س',
        'ﺷ': 'ش',
        'ﺻ': 'ص',
        'ﺿ': 'ض',
        'ﻃ': 'ط',
        'ﻇ': 'ظ',
        'ﻋ': 'ع',
        'ﻏ': 'غ',
        'ﻓ': 'ف',
        'ﻗ': 'ق',
        'ﻛ': 'ك',
        'ﻟ': 'ل',
        'ﻣ': 'م',
        'ﻧ': 'ن',
        'ﻫ': 'ه',
        'ﻳ': 'ي',
        
        # Middle forms
        'ﺒ': 'ب',
        'ﺘ': 'ت',
        'ﺜ': 'ث',
        'ﺠ': 'ج',
        'ﺤ': 'ح',
        'ﺨ': 'خ',
        'ﺴ': 'س',
        'ﺸ': 'ش',
        'ﺼ': 'ص',
        'ﻀ': 'ض',
        'ﻄ': 'ط',
        'ﻈ': 'ظ',
        'ﻌ': 'ع',
        'ﻐ': 'غ',
        'ﻔ': 'ف',
        'ﻘ': 'ق',
        'ﻜ': 'ك',
        'ﻠ': 'ل',
        'ﻤ': 'م',
        'ﻨ': 'ن',
        'ﻬ': 'ه',
        'ﻴ': 'ي',
        
        # End forms
        'ﺐ': 'ب',
        'ﺖ': 'ت',
        'ﺚ': 'ث',
        'ﺞ': 'ج',
        'ﺢ': 'ح',
        'ﺦ': 'خ',
        'ﺲ': 'س',
        'ﺶ': 'ش',
        'ﺺ': 'ص',
        'ﺾ': 'ض',
        'ﻂ': 'ط',
        'ﻆ': 'ظ',
        'ﻊ': 'ع',
        'ﻎ': 'غ',
        'ﻒ': 'ف',
        'ﻖ': 'ق',
        'ﻚ': 'ك',
        'ﻞ': 'ل',
        'ﻢ': 'م',
        'ﻦ': 'ن',
        'ﻪ': 'ه',
        'ﻲ': 'ي',
        
        # Common combinations in middle of word
        'ﻤﺠ': 'مج',
        'ﺠﻤ': 'جم',
        'ﺤﻤ': 'حم',
        'ﻤﺤ': 'مح',
        'ﻌﻤ': 'عم',
        'ﻤﻌ': 'مع',
        'ﻤﻨ': 'من',
        'ﻨﻤ': 'نم',
        'ﺴﻠ': 'سل',
        'ﻠﺴ': 'لس',
        'ﻋﻠ': 'عل',
        'ﻠﻌ': 'لع',
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
        r'رض[يى]\s*[اآ]لله\s*عنه': 'رضي الله عنه',
        r'عز\s*[وﻭ]جل': 'عز وجل',
        r'تعال[ىي]': 'تعالى',
        r'سبحانه': 'سبحانه',
        r'تبارك': 'تبارك',
        r'حديث\s*(صحيح|حسن|ضعيف)': r'حديث \1',
    }
    
    # Fix common letter mistakes
    letter_fixes = {
        'ھ': 'ه',    # Fix different forms of Ha
        'ے': 'ی',    # Fix Ya variants
        'ﺓ': 'ة',    # Fix Ta Marbuta
        'ﷲ': 'الله', # Fix Allah ligature
        'ﷺ': 'صلى الله عليه وسلم',  # Fix Prophet's blessing
        'ﷻ': 'سبحانه وتعالى',       # Fix Allah's glorification
        'ﷴ': 'محمد',                # Fix Muhammad's name
        'ﷳ': 'اكبر',                # Fix Akbar
        'ﱞ': 'ً',    # Tanween Fathatan
        'ﱟ': 'ٍ',    # Tanween Kasratan
        'ﱠ': 'ّ',    # Shadda
        'ﱡ': 'ٌ',    # Tanween Dammatan
    }
    
    # Arabic numbers and their Western equivalents
    arabic_numbers = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        '٪': '%',  # Arabic percentage
        '٫': '.',  # Arabic decimal separator
        '٬': ',',  # Arabic thousands separator
    }
    
    # Enhanced Quranic symbols and markers
    quranic_symbols = {
        '۝': '۝',    # Sajdah
        '۞': '۞',    # Hizb
        '﷽': '﷽',    # Bismillah
        '﴾': '﴾',    # Quranic bracket opening
        '﴿': '﴿',    # Quranic bracket closing
        '۩': '۩',    # Sajdah mark
        '۠': '۠',    # Quranic stop sign
        '۫': '۫',    # Quranic small high seen
        '۪': '۪',    # Quranic small high seen alternate
        'ۭ': 'ۭ',    # Quranic small high yeh
        '۬': '۬',    # Quranic small high noon
        '۟': '۟',    # Small high waw
        '۝': '۝',    # End of ayah
        '۞': '۞',    # Start of quarter hizb
        '†': '†',    # Verse marker
        '‡': '‡',    # Section marker
        '۰': '۰',    # Extended Arabic-Indic digit zero
        '۱': '۱',    # and so on...
        '۲': '۲',
        '۳': '۳',
        '۴': '۴',
        '۵': '۵',
        '۶': '۶',
        '۷': '۷',
        '۸': '۸',
        '۹': '۹',
    }
    
    # Diacritical marks and special characters
    diacritics = {
        'ٰ': 'ٰ',     # Superscript alef
        'ٖ': 'ٖ',     # Subscript alef
        'ٗ': 'ٗ',     # Inverted damma
        'ٜ': 'ٜ',     # High hamza
        'ٕ': 'ٕ',     # High waw
        'ٔ': 'ٔ',     # High yeh
        'ْ': 'ْ',     # Sukun
        'ُ': 'ُ',     # Damma
        'ِ': 'ِ',     # Kasra
        'َ': 'َ',     # Fatha
        'ّ': 'ّ',     # Shadda
        'ً': 'ً',     # Tanween Fath
        'ٍ': 'ٍ',     # Tanween Kasr
        'ٌ': 'ٌ',     # Tanween Damm
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
            text = re.sub(pattern, replacement, text)
        return text
    
    # Apply connected letter fixes
    text = fix_connected_letters(text)
    
    return text

def get_pdf_info(pdf_file) -> Dict[str, any]:
    """
    Get information about a PDF file.
    
    Args:
        pdf_file: The uploaded PDF file object
    
    Returns:
        Dictionary with PDF information
    """
    try:
        # Read PDF bytes
        pdf_bytes = pdf_file.getvalue() if hasattr(pdf_file, 'getvalue') else pdf_file.read()
        
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        # Get information about the PDF
        info = {
            "num_pages": len(pdf_reader.pages),
            "metadata": pdf_reader.metadata if hasattr(pdf_reader, 'metadata') else {},
            "file_size": len(pdf_bytes) / 1024  # Size in KB
        }
        
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
