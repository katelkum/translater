import streamlit as st
import os
import io
from pathlib import Path
from datetime import datetime
from pdf_utils import get_pdf_info, chunk_text
from translation import initialize_gemini_api, translate_chunks, translate_text, translate_image, translate_pdf_pages
from pdf2image import convert_from_bytes
import fitz  # PyMuPDF
from PIL import Image  # Add this import

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
if "translated_text" not in st.session_state:
    st.session_state.translated_text = ""
if "translation_completed" not in st.session_state:
    st.session_state.translation_completed = False
if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = False
if "selected_pages" not in st.session_state:
    st.session_state.selected_pages = []
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
    value=os.getenv("GOOGLE_API_KEY", ""),
    type="password"
)

# Add after API Key input and before file uploader
col1, col2 = st.columns(2)
with col1:
    source_lang = st.selectbox(
        "Select source language:",
        ["Arabic", "English", "French", "German", "Spanish", "Italian"],
        index=0
    )
with col2:
    target_lang = st.selectbox(
        "Select target language:",
        ["Arabic", "English", "French", "German", "Spanish", "Italian"],
        index=5  # Italian
    )

if source_lang == target_lang:
    st.warning("Source and target languages must be different.")

# Function to validate API key
def validate_api_key():
    if api_key:
        try:
            if not api_key:
                st.error("Please enter a valid API key")
                return
            else:
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
                        
                        # Open PDF with PyMuPDF
                        pdf_bytes = st.session_state.uploaded_file.getvalue()
                        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        selected_images = []
                        for page_num in st.session_state.selected_pages:
                            # Get page
                            page = pdf_document[page_num]
                            # Convert page to image
                            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                            selected_images.append((page_num, img))
                        
                        # Close PDF document
                        pdf_document.close()
                        
                        # Clear PDF from memory
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
