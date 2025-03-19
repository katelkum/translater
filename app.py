import streamlit as st
import os
import io
from pathlib import Path
from datetime import datetime
from pdf_utils import extract_text_from_pdf, extract_text_from_pdf_page, get_pdf_info, is_arabic_text, chunk_text
from translation import initialize_gemini_api, translate_chunks, translate_text, translate_image, translate_pdf_pages
from pdf2image import convert_from_bytes

# Set page config
st.set_page_config(
    page_title="Multi-Language PDF Translator",
    page_icon="📚",
    layout="wide"
)

# Initialize session state variables if not already initialized
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "pdf_info" not in st.session_state:
    st.session_state.pdf_info = None
if "extracted_text" not in st.session_state:
    st.session_state.extracted_text = ""
if "translated_text" not in st.session_state:
    st.session_state.translated_text = ""
if "translation_completed" not in st.session_state:
    st.session_state.translation_completed = False
if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = False
if "extraction_method" not in st.session_state:
    st.session_state.extraction_method = "standard"
if "selected_pages" not in st.session_state:
    st.session_state.selected_pages = []
if "page_texts" not in st.session_state:
    st.session_state.page_texts = {}
if "page_translations" not in st.session_state:
    st.session_state.page_translations = {}
if "page_images" not in st.session_state:
    st.session_state.page_images = {}

# Application title and introduction
st.title("📚 Multi-Language PDF Translator")
st.write("Upload a PDF document and translate it between multiple languages using Google's Gemini API.")

# API Key input (with a default value for convenience)
api_key = st.text_input(
    "Enter your Gemini API Key:", 
    value="AIzaSyC-Z19b7ea3XIsjXwecO0s195f7GeWiwCw",
    type="password"
)

# Add after API Key input and before file uploader
col1, col2 = st.columns(2)
with col1:
    source_lang = st.selectbox(
        "Select source language:",
        ["Arabic", "English", "French", "German", "Spanish", "Chinese", "Japanese", "Korean", "Italian", "Portuguese", "Russian", "Hindi", "Bengali", "Urdu", "Turkish", "Persian", "Swahili", "Dutch", "Greek", "Hebrew", "Thai", "Vietnamese"],
        index=0
    )
with col2:
    target_lang = st.selectbox(
        "Select target language:",
        ["Arabic", "English", "French", "German", "Spanish", "Chinese", "Japanese", "Korean", "Italian", "Portuguese", "Russian", "Hindi", "Bengali", "Urdu", "Turkish", "Persian", "Swahili", "Dutch", "Greek", "Hebrew", "Thai", "Vietnamese"],
        index=0
    )

if source_lang == target_lang:
    st.warning("Source and target languages must be different.")

# Function to validate API key
def validate_api_key():
    if api_key:
        try:
            initialize_gemini_api(api_key)
            st.session_state.api_key_valid = True
            return True
        except Exception as e:
            st.error(f"Invalid API key: {str(e)}")
            st.session_state.api_key_valid = False
            return False
    else:
        st.error("Please enter an API key")
        st.session_state.api_key_valid = False
        return False

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# Update session state when a new file is uploaded
if uploaded_file is not None and (st.session_state.uploaded_file is None or st.session_state.uploaded_file.name != uploaded_file.name):
    st.session_state.uploaded_file = uploaded_file
    st.session_state.extracted_text = ""
    st.session_state.translated_text = ""
    st.session_state.translation_completed = False
    st.session_state.selected_pages = []
    st.session_state.page_texts = {}
    st.session_state.page_translations = {}
    
    # Get PDF information
    try:
        st.session_state.pdf_info = get_pdf_info(uploaded_file)
    except Exception as e:
        st.error(f"Error getting PDF information: {str(e)}")
        st.session_state.pdf_info = None

# Process the PDF file
if st.session_state.uploaded_file is not None and st.session_state.pdf_info is not None:
    st.write("---")
    st.subheader("📄 Document Information")
    
    # Display PDF information
    pdf_info = st.session_state.pdf_info
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**File name:** {st.session_state.uploaded_file.name}")
        st.write(f"**Number of pages:** {pdf_info['num_pages']}")
    with col2:
        st.write(f"**File size:** {pdf_info['file_size']:.2f} KB")
    
    # Text extraction options
    st.write("---")
    st.subheader("📝 Text Extraction and Translation Options")
    
    # Processing method
    processing_method = st.radio(
        "Select processing method:",
        ["Extract & Translate Text", "Direct Image Translation (Recommended for Arabic)"],
        index=1,  # Default to Direct Image Translation as it's better for Arabic
        horizontal=True
    )
    
    # Only show text extraction method if using the extract & translate approach
    if processing_method == "Extract & Translate Text":
        # Text extraction method
        extraction_method = st.radio(
            "Select text extraction method:",
            ["Standard (Faster, may have quality issues)", "OCR-based (Slower, better quality)"],
            index=0,
            horizontal=True
        )
        # Set extraction method
        st.session_state.extraction_method = "standard" if extraction_method.startswith("Standard") else "ocr"
    
    else:
        # Default to OCR for Direct Image Translation
        st.session_state.extraction_method = "ocr"
    
    # Page selection options
    page_selection_option = st.radio(
        "Select pages to translate:",
        ["All pages", "Select specific pages"],
        index=0,
        horizontal=True
    )
    
    # If "Select specific pages" is chosen
    if page_selection_option == "Select specific pages":
        # Create a multiselect for selecting pages
        page_options = [f"Page {i+1}" for i in range(pdf_info['num_pages'])]
        selected_pages = st.multiselect(
            "Select pages to translate:",
            page_options,
            default=page_options[0] if page_options else None  # Default to first page if available
        )
        
        # Convert selected pages to page numbers (0-indexed)
        st.session_state.selected_pages = [int(page.split()[-1]) - 1 for page in selected_pages]
    else:
        # All pages
        st.session_state.selected_pages = list(range(pdf_info['num_pages']))
    
    # Buttons for processing the PDF
    if processing_method == "Extract & Translate Text":
        # Extract text button
        if st.button("Extract Text"):
            if validate_api_key():
                if not st.session_state.selected_pages:
                    st.warning("Please select at least one page to extract.")
                else:
                    with st.spinner(f"Extracting text using {st.session_state.extraction_method} method..."):
                        try:
                            # Clear previous extractions
                            st.session_state.page_texts = {}
                            
                            # Extract text for each selected page
                            for page_num in st.session_state.selected_pages:
                                progress_text = st.empty()
                                progress_text.text(f"Processing page {page_num + 1}...")
                                
                                # Extract text from the page
                                page_text = extract_text_from_pdf_page(
                                    st.session_state.uploaded_file,
                                    page_num,
                                    method=st.session_state.extraction_method
                                )
                                
                                # Store the extracted text
                                st.session_state.page_texts[page_num] = page_text
                            
                            # Combine all extracted texts
                            combined_text = "\n\n".join([
                                f"--- Page {page_num + 1} ---\n{text}"
                                for page_num, text in sorted(st.session_state.page_texts.items())
                            ])
                            
                            st.session_state.extracted_text = combined_text
                            
                            if 'progress_text' in locals():
                                progress_text.empty()
                            st.success(f"✅ Text extracted successfully from {len(st.session_state.selected_pages)} page(s).")
                        except Exception as e:
                            st.error(f"❌ Error extracting text: {str(e)}")
    else:
        # Direct Image Translation button
        if st.button("Translate PDF Pages Directly"):
            if validate_api_key():
                if not st.session_state.selected_pages:
                    st.warning("Please select at least one page to translate.")
                else:
                    with st.spinner("Converting PDF pages to images and translating..."):
                        try:
                            # Reset previous translations
                            st.session_state.translated_text = ""
                            st.session_state.page_translations = {}
                            st.session_state.page_images = {}
                            
                            # First, convert PDF pages to images - only the selected pages
                            pdf_bytes = st.session_state.uploaded_file.getvalue()
                            
                            # Convert only selected pages to save memory - use first_page and last_page arguments
                            selected_images = []
                            for page_num in st.session_state.selected_pages:
                                # Convert just this single page to image
                                page_images = convert_from_bytes(
                                    pdf_bytes, 
                                    dpi=300, 
                                    first_page=page_num+1, 
                                    last_page=page_num+1
                                )
                                
                                if page_images and len(page_images) > 0:
                                    selected_images.append((page_num, page_images[0]))
                            
                            # Now we can clear the original PDF from memory 
                            # to optimize memory usage since we only need the selected pages
                            st.session_state.uploaded_file = None
                            pdf_bytes = None
                            
                            # Create a progress bar
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Callback function to update progress
                            def update_progress(current, total):
                                progress = current / total
                                progress_bar.progress(progress)
                                status_text.text(f"Translating page {current} of {total}...")
                            
                            # Prepare the images list for translation
                            img_list = [img for _, img in selected_images]
                            
                            # Translate the images
                            try:
                                # Pass the images directly to Gemini for translation
                                translated_pages = translate_pdf_pages(img_list, callback=update_progress, source_lang=source_lang, target_lang=target_lang)
                                
                                # After translation, we can clear the images to free up memory
                                for i, (page_num, img) in enumerate(selected_images):
                                    if i < len(translated_pages):
                                        # Store translation text in session state
                                        st.session_state.page_translations[page_num] = translated_pages[i]
                                        # We don't need to keep the image in memory, 
                                        # but we'll store a thumbnail for display purposes
                                        thumb_size = (100, int(100 * img.height / img.width))
                                        st.session_state.page_images[page_num] = img.resize(thumb_size)
                                
                                # Now we can clear the original image list
                                selected_images = None
                                img_list = None
                                
                            except Exception as e:
                                st.error(f"Error during translation: {str(e)}")
                                # Create an empty list to avoid errors below
                                translated_pages = ["Error translating page."] * len(img_list)
                                
                                # Store error translations in session state
                                for i, (page_num, _) in enumerate(selected_images):
                                    if i < len(translated_pages):
                                        st.session_state.page_translations[page_num] = translated_pages[i]
                            
                            # Storage of translations is now done during translation in the try block
                            # We now only need to combine them to show the results
                            
                            # Combine all translated texts
                            combined_translation = "\n\n".join([
                                f"--- Page {page_num + 1} ---\n{text}"
                                for page_num, text in sorted(st.session_state.page_translations.items())
                            ])
                            
                            # Update session state
                            st.session_state.translated_text = combined_translation
                            st.session_state.translation_completed = True
                            
                            # Update the progress bar to 100%
                            progress_bar.progress(1.0)
                            status_text.text("Translation completed!")
                            
                            st.success("✅ Translation completed successfully!")
                        except Exception as e:
                            st.error(f"❌ Translation error: {str(e)}")
                            st.error("Make sure you are using the latest version of the Gemini API key.")

    # Display extracted text if available
    if st.session_state.extracted_text:
        st.write("---")
        st.subheader("📄 Extracted Text")
        
        # Display the extracted text for all selected pages
        with st.expander("View Extracted Text", expanded=False):
            st.text_area("Extracted Text", st.session_state.extracted_text, height=300, disabled=True)
        
        # Translate options
        st.write("---")
        st.subheader("🔄 Translation Options")
        
        translation_option = st.radio(
            "Translate:",
            ["All extracted pages together", "Each page individually"],
            index=0,
            horizontal=True
        )
        
        # Translate button
        if st.button("Translate Text"):
            if validate_api_key():
                if translation_option == "All extracted pages together":
                    # Translate all text at once
                    with st.spinner("Translating all pages..."):
                        try:
                            # Split the text into chunks for translation
                            chunks = chunk_text(st.session_state.extracted_text)
                            total_chunks = len(chunks)
                            
                            # Create a progress bar
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            # Callback function to update progress
                            def update_progress(current, total):
                                progress = current / total
                                progress_bar.progress(progress)
                                status_text.text(f"Translating chunk {current} of {total}...")
                            
                            # Translate the chunks
                            translated_chunks = translate_chunks(chunks, callback=update_progress, source_lang=source_lang, target_lang=target_lang)
                            
                            # Combine the translated chunks
                            combined_translation = "\n\n".join([chunk for chunk in translated_chunks if chunk])
                            
                            # Update session state
                            st.session_state.translated_text = combined_translation
                            st.session_state.translation_completed = True
                            
                            # Update the progress bar to 100%
                            progress_bar.progress(1.0)
                            status_text.text("Translation completed!")
                            
                            st.success("✅ Translation completed successfully!")
                        except Exception as e:
                            st.error(f"❌ Translation error: {str(e)}")
                else:
                    # Translate each page individually
                    with st.spinner("Translating pages individually..."):
                        try:
                            # Clear previous translations
                            st.session_state.page_translations = {}
                            
                            # Translate each page
                            total_pages = len(st.session_state.page_texts)
                            progress_bar = st.progress(0)
                            
                            for i, (page_num, text) in enumerate(sorted(st.session_state.page_texts.items())):
                                status_text = st.empty()
                                status_text.text(f"Translating page {page_num + 1}...")
                                
                                # Translate the page text
                                translated_text = translate_text(text, provider="gemini", source_lang=source_lang, target_lang=target_lang)
                                
                                # Store the translated text
                                st.session_state.page_translations[page_num] = translated_text
                                
                                # Update progress
                                progress = (i + 1) / total_pages
                                progress_bar.progress(progress)
                            
                            # Combine all translated texts
                            combined_translation = "\n\n".join([
                                f"--- Page {page_num + 1} ---\n{text}"
                                for page_num, text in sorted(st.session_state.page_translations.items())
                            ])
                            
                            # Update session state
                            st.session_state.translated_text = combined_translation
                            st.session_state.translation_completed = True
                            
                            progress_bar.progress(1.0)
                            st.success("✅ Translation completed successfully!")
                        except Exception as e:
                            st.error(f"❌ Translation error: {str(e)}")
    
    # Display translated text if available
    if st.session_state.translation_completed and st.session_state.translated_text:
        st.write("---")
        st.subheader("🔤 Translation Results")
        
        st.text_area("Translated Text", st.session_state.translated_text, height=400)
        
        # Create a download button for the translated text
        if st.session_state.translated_text:
            # Create a text file with the translated text
            translated_text_bytes = st.session_state.translated_text.encode()
            bio = io.BytesIO(translated_text_bytes)
            
            # Generate a filename for the download
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get original filename if available, otherwise use a generic name
            if st.session_state.uploaded_file and hasattr(st.session_state.uploaded_file, 'name'):
                original_filename = Path(st.session_state.uploaded_file.name).stem
                download_filename = f"{original_filename}_translated_{timestamp}.txt"
            else:
                download_filename = f"translated_document_{timestamp}.txt"
            
            # Display the download button
            st.download_button(
                label="Download Translated Text",
                data=bio,
                file_name=download_filename,
                mime="text/plain"
            )

# Footer
st.write("---")
st.caption("PDF Translator Application | Translates PDF documents from Arabic to Italian using Google's Gemini API")
