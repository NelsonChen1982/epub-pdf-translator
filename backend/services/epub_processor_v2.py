import os
import logging
from typing import Dict, List, Optional, Tuple, Callable
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
from .translator import TranslationService
from .validators import EPUBValidator

logger = logging.getLogger(__name__)


class EPUBProcessor:
    def __init__(self):
        self.translator = TranslationService()
        self.validator = EPUBValidator()
        # Tags to skip completely
        self.skip_tags = {'script', 'style', 'code', 'pre', 'meta', 'link', 'title'}
        # Paragraph-level tags to translate as blocks
        self.paragraph_tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'li', 'td', 'th', 'dt', 'dd'}

    def extract_translatable_texts(self, html_content: str) -> List[str]:
        """Extract translatable text blocks from HTML content."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove scripts, styles, etc.
        for tag in soup(self.skip_tags):
            tag.decompose()
        
        texts = []
        
        # Extract paragraph-level texts
        for tag in soup.find_all(self.paragraph_tags):
            text = tag.get_text(strip=True)
            if text and len(text) > 10:  # Skip very short texts
                texts.append(text)
        
        return texts

    def replace_translatable_texts(self, html_content: str, translations: Dict[str, str]) -> str:
        """Replace translatable texts with translations while preserving HTML structure."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Replace paragraph-level texts
        for tag in soup.find_all(self.paragraph_tags):
            original_text = tag.get_text(strip=True)
            if original_text in translations:
                # Preserve the tag structure but replace text content
                tag.clear()
                tag.string = translations[original_text]
                logger.debug(f"Replaced: '{original_text[:50]}...' -> '{translations[original_text][:50]}...'")
        
        return str(soup)

    async def translate_html_content(self, html_content: str, target_lang: str, progress_callback=None) -> str:
        """Translate HTML content while preserving structure."""
        try:
            # Extract translatable texts
            texts = self.extract_translatable_texts(html_content)
            logger.info(f"Extracted {len(texts)} text blocks for translation")
            
            if not texts:
                logger.warning("No translatable texts found")
                return html_content
            
            # Translate texts
            translations = {}
            for i, text in enumerate(texts):
                if progress_callback:
                    progress_callback(i + 1, len(texts))
                
                try:
                    logger.info(f"Translating text {i+1}/{len(texts)}: '{text[:100]}...'")
                    translated = await self.translator.translate_text(text, target_lang, "epub")
                    translations[text] = translated
                    logger.info(f"Translation result: '{translated[:100]}...'")
                except Exception as e:
                    logger.error(f"Failed to translate text: {e}")
                    translations[text] = text  # Keep original on failure
            
            # Replace texts with translations
            result = self.replace_translatable_texts(html_content, translations)
            logger.info(f"Translation completed, {len(translations)} texts replaced")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to translate HTML content: {e}")
            return html_content

    async def process_epub(
        self,
        input_path: str,
        output_path: str,
        target_lang: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Process EPUB translation using ebooklib."""
        try:
            logger.info(f"Starting EPUB processing: {input_path}")
            
            # Read the EPUB book
            book = epub.read_epub(input_path)
            logger.info(f"Successfully loaded EPUB: {book.get_metadata('DC', 'title')}")
            
            # Get all document items (chapters)
            doc_items = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
            logger.info(f"Found {len(doc_items)} document items to translate")
            
            if not doc_items:
                return {"success": False, "error": "No document items found in EPUB"}
            
            # Preview content
            self.preview_epub_content(doc_items)
            
            # Translate each document item
            for i, item in enumerate(doc_items):
                logger.info(f"Processing item {i+1}/{len(doc_items)}: {item.get_name()}")
                
                if progress_callback:
                    progress_callback("epub", f"Chapter {i+1}/{len(doc_items)}", i+1, len(doc_items))
                
                # Get HTML content
                html_content = item.get_content().decode('utf-8')
                
                # Create progress callback for this item
                def item_progress_callback(current, total):
                    if progress_callback:
                        progress_callback("epub", f"Chapter {i+1}/{len(doc_items)} - Block {current}/{total}", current, total)
                
                # Translate content
                translated_content = await self.translate_html_content(
                    html_content, target_lang, item_progress_callback
                )
                
                # Update item content
                item.set_content(translated_content.encode('utf-8'))
                logger.info(f"Item {i+1} translation completed")
            
            # Save the translated book
            logger.info(f"Saving translated EPUB to: {output_path}")
            epub.write_epub(output_path, book)
            
            # Validate output
            validation_result = self.validator.validate_epub(output_path)
            if not validation_result["valid"]:
                logger.error(f"EPUB validation failed: {validation_result['errors']}")
                return {
                    "success": False,
                    "error": f"EPUB validation failed: {validation_result['errors']}"
                }
            
            logger.info("EPUB processing completed successfully")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"EPUB processing failed: {e}")
            return {"success": False, "error": str(e)}

    def preview_epub_content(self, doc_items: List):
        """Preview EPUB content for debugging."""
        logger.info("=== EPUB CONTENT PREVIEW ===")
        logger.info(f"Found {len(doc_items)} document items:")
        
        for i, item in enumerate(doc_items):
            logger.info(f"\nItem {i+1}: {item.get_name()}")
            
            try:
                html_content = item.get_content().decode('utf-8')
                texts = self.extract_translatable_texts(html_content)
                
                logger.info(f"  Content length: {len(html_content)} chars")
                logger.info(f"  Text blocks found: {len(texts)}")
                
                # Show first 3 text blocks as preview
                preview_texts = texts[:3]
                for j, text in enumerate(preview_texts):
                    # Truncate long texts for preview
                    preview_text = text[:200] + "..." if len(text) > 200 else text
                    logger.info(f"  Block {j+1}: {repr(preview_text)}")
                
                if len(texts) == 0:
                    logger.warning("  No extractable text blocks found!")
                    # Show raw content sample
                    raw_sample = html_content[:500] + "..." if len(html_content) > 500 else html_content
                    logger.info(f"  Raw content sample: {repr(raw_sample)}")
                    
            except Exception as e:
                logger.error(f"  Error reading item: {e}")
        
        logger.info("=== END PREVIEW ===")