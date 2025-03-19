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
        return f"Translation error: {str(e)}. Please check your input and try again."


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
    """Translate text from an image using the selected provider."""
    max_retries = 3
    
    # Preprocess image to improve quality
    img = image.convert('RGB')
    # Resize if image is too large (max 4096x4096)
    if img.size[0] > 4096 or img.size[1] > 4096:
        img.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    
    for attempt in range(max_retries):
        try:
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format='PNG', optimize=True, quality=95)
            img_byte_arr = img_byte_arr.getvalue()
            
            try:
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                
                prompt = f"""You are an expert translator analyzing this page from {source_lang} to {target_lang}.
                        Your task is to provide a clear and accurate translation.
                        
                        REQUIREMENTS:
                        1. Translate ALL visible text from {source_lang} to {target_lang}
                        2. Maintain the original formatting and structure
                        3. For Arabic religious terms: keep them in Arabic followed by translation in parentheses
                        4. If text is unclear, make educated guesses based on context
                        
                        OUTPUT FORMAT:
                        - Only provide the {target_lang} translation
                        - Preserve paragraph breaks and structure
                        - Use appropriate {target_lang} punctuation

                        IMPORTANT: If you see any text in the image, you must translate it. 
                        If the image appears blank or unreadable, explicitly state that.
                        """
                
                response = model.generate_content([
                    prompt, 
                    {"mime_type": "image/png", "data": img_byte_arr}
                ], generation_config={
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "top_k": 40
                })
                
                if response and hasattr(response, 'text'):
                    translated_text = response.text.strip()
                    if translated_text:
                        return translated_text
                    else:
                        raise Exception("Empty response from model")
                        
            except Exception as e:
                print(f"Vision model error (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    raise e
                continue
            
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                print(f"Image translation error after {max_retries} attempts: {str(e)}")
                return "No readable text could be found on this page. Please check the image quality and try again."
    
    return "Translation failed after multiple attempts. Please try again."

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
