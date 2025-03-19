import google.generativeai as genai
import os
from typing import List, Dict, Any, Optional, Literal
from PIL import Image
from io import BytesIO

# Supported translation providers
TranslationProvider = Literal["gemini"]

def initialize_gemini_api(api_key: str) -> None:
    """
    Initialize the Gemini API with the provided key.
    
    Args:
        api_key: The API key for Gemini
    """
    genai.configure(api_key=api_key)

def get_translation_prompt(source_lang: str, target_lang: str) -> str:
    """Get the appropriate translation prompt based on source language."""
    
    if source_lang.lower() == "arabic":
        return f"""You are an expert translator specializing in {source_lang} to {target_lang} translations, with extensive knowledge of Islamic texts and cultural context.

        IMPORTANT CONTEXT HANDLING:
        1. When encountering unclear or partially extracted words:
           - Analyze the surrounding context carefully
           - Use your knowledge of common {source_lang} phrases and expressions
           - Infer the most likely word based on context and religious terminology
           
        2. For Religious Terminology:
           - Keep religious terms in Arabic with translations
           - Use traditional translations for Islamic concepts
           
        3. OUTPUT FORMAT:
           - Maintain paragraph structure
           - Only provide the translation
           - Keep religious terms in Arabic with translations in parentheses
        """
    else:
        return f"""You are an expert translator specializing in {source_lang} to {target_lang} translations.

        TRANSLATION GUIDELINES:
        1. Maintain the original meaning and tone
        2. Use natural {target_lang} expressions
        3. Preserve technical terms with translations if needed
        4. Keep formatting and structure
        5. Handle cultural references appropriately
        
        OUTPUT FORMAT:
        - Provide only the translation
        - Maintain paragraph structure
        - Keep original formatting
        """

def translate_text(text: str, provider: TranslationProvider = "gemini", 
                  source_lang: str = "Arabic", target_lang: str = "Italian") -> Optional[str]:
    """
    Translate text using the selected provider.
    
    Args:
        text: The text to translate
        provider: The translation provider to use ("gemini")
        source_lang: The source language
        target_lang: The target language
    """
    if not text.strip():
        return ""
    
    try:
        if provider == "gemini":
            try:
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
            except Exception:
                model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = get_translation_prompt(source_lang, target_lang) + f"\n\nText to translate:\n{text}"
            response = model.generate_content(prompt)
            
            if response and hasattr(response, 'text'):
                return response.text.strip()
            else:
                return None
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return f"Errore durante la traduzione: {str(e)}"

def translate_chunks(chunks: List[str], provider: TranslationProvider = "gemini",
                    source_lang: str = "Arabic", target_lang: str = "Italian", 
                    callback=None) -> List[str]:
    """
    Translate multiple chunks of text using the selected provider.
    
    Args:
        chunks: List of text chunks to translate
        provider: The translation provider to use ("gemini")
        source_lang: The source language (default: Arabic)
        target_lang: The target language (default: Italian)
        callback: Optional callback function to update progress
    
    Returns:
        List of translated text chunks
    """
    translated_chunks = []
    
    for i, chunk in enumerate(chunks):
        translated_text = translate_text(chunk, provider, source_lang, target_lang)
        translated_chunks.append(translated_text)
        
        if callback:
            callback(i + 1, len(chunks))
    
    return translated_chunks

def translate_image(image: Image.Image, provider: TranslationProvider = "gemini",
                   source_lang: str = "Arabic", target_lang: str = "English") -> Optional[str]:
    """
    Translate text from an image using the selected provider.
    """
    try:
        model_configs = [
            ('gemini-2.0-flash-exp', True),
        ]
        
        img_byte_arr = BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        last_error = None
        for model_name, is_vision_model in model_configs:
            try:
                model = genai.GenerativeModel(model_name)
                
                prompt = f"""You are an expert translator analyzing a PDF page from {source_lang} to {target_lang}. 
                        Act as a professional translator.
                        
                        TRANSLATION REQUIREMENTS:
                        1. Translate the text from {source_lang} to {target_lang}
                        2. Preserve formatting and structure
                        3. Keep religious/technical terms with translations in parentheses
                        4. Ensure natural flow in {target_lang}

                        OUTPUT FORMAT:
                        - Provide ONLY the {target_lang} translation
                        - Maintain paragraph structure
                        - Use proper {target_lang} punctuation
                        - Do not include the original text
                        """
                
                if is_vision_model:
                    response = model.generate_content([prompt, {"mime_type": "image/png", "data": img_byte_arr}])
                else:
                    import pytesseract
                    extracted_text = pytesseract.image_to_string(Image.open(BytesIO(img_byte_arr)), lang='ara+ita')
                    response = model.generate_content(f"{prompt}\n\nText to translate:\n{extracted_text}")
                
                if response and hasattr(response, 'text'):
                    return response.text.strip()
                
            except Exception as e:
                last_error = str(e)
                continue
        
        if last_error:
            raise Exception(f"All translation models failed. Last error: {last_error}")
        
        return "Translation failed. Please try a different API key or contact support."
        
    except Exception as e:
        print(f"Image translation error: {str(e)}")
        return f"Translation error. Please try again with a different model or API key. Error details: {str(e)}"

def translate_pdf_pages(images: List[Image.Image], provider: TranslationProvider = "gemini",
                       source_lang: str = "Arabic", target_lang: str = "Italian",
                       callback=None) -> List[str]:
    """
    Translate multiple PDF pages using the selected provider.
    
    Args:
        images: List of PIL Image objects (one per PDF page)
        provider: The translation provider to use ("gemini")
        source_lang: The source language (default: Arabic)
        target_lang: The target language (default: Italian)
        callback: Optional callback function to update progress
    
    Returns:
    Returns:
        List of translated text for each page
    """
    translated_pages = []
    
    for i, image in enumerate(images):
        try:
            translated_text = translate_image(image, provider, source_lang, target_lang)
            translated_pages.append(translated_text)
            
            if callback:
                callback(i + 1, len(images))
        except Exception as e:
            error_message = f"Error translating page {i+1}: {str(e)}"
            print(error_message)
            translated_pages.append(error_message)
            
            if callback:
                callback(i + 1, len(images))
    
    return translated_pages
