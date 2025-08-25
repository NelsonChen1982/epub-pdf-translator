import os
import zipfile
import tempfile
import shutil
import logging
from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path
from lxml import etree, html
from bs4 import BeautifulSoup
from .translator import TranslationService
from .validators import EPUBValidator
from .utils import normalize_zip_path


logger = logging.getLogger(__name__)


class EPUBProcessor:
    def __init__(self):
        self.translator = TranslationService()
        self.validator = EPUBValidator()
        self.skip_tags = {'script', 'style', 'code', 'pre', 'meta', 'link', 'title', 'head'}
        self.skip_containers = {'head'}  # Skip entire containers
    
    def extract_safe_texts(self, element) -> List[Tuple[str, str]]:
        """Safely extract text blocks with their container info."""
        texts = []
        
        # Skip non-translatable containers entirely
        if element.tag.lower() in self.skip_containers:
            return texts
            
        # Skip non-translatable elements
        if element.tag.lower() in self.skip_tags:
            return texts
            
        # Only extract from body content, avoid head area
        if element.tag.lower() == 'html':
            body = element.find('.//body')
            if body is not None:
                return self.extract_safe_texts(body)
            else:
                # If no body tag, process all children except head
                for child in element:
                    if child.tag.lower() != 'head':
                        texts.extend(self.extract_safe_texts(child))
            return texts
        
        # For paragraph-level elements, get complete text content
        paragraph_tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'li', 'td', 'th', 'dt', 'dd'}
        
        if element.tag.lower() in paragraph_tags:
            # Get all text content from this paragraph element
            text_content = element.text_content().strip()
            if text_content and len(text_content) > 10:  # Skip very short texts
                # Store text with element info for safe replacement
                element_info = f"{element.tag}_{id(element)}"
                texts.append((text_content, element_info))
        else:
            # For other elements, recursively process children
            for child in element:
                texts.extend(self.extract_safe_texts(child))
        
        return texts
    
    def replace_safe_texts(self, element, translations: Dict[str, str], element_map: Dict[str, any]):
        """Safely replace text blocks while preserving HTML structure."""
        # Skip non-translatable containers entirely
        if element.tag.lower() in self.skip_containers:
            return
            
        # Skip non-translatable elements
        if element.tag.lower() in self.skip_tags:
            return
            
        # Only process body content, avoid head area
        if element.tag.lower() == 'html':
            body = element.find('.//body')
            if body is not None:
                self.replace_safe_texts(body, translations, element_map)
            else:
                # If no body tag, process all children except head
                for child in element:
                    if child.tag.lower() != 'head':
                        self.replace_safe_texts(child, translations, element_map)
            return
            
        paragraph_tags = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'li', 'td', 'th', 'dt', 'dd'}
        
        if element.tag.lower() in paragraph_tags:
            element_info = f"{element.tag}_{id(element)}"
            if element_info in element_map:
                original_text = element_map[element_info]
                if original_text in translations:
                    # Replace the entire text content of the paragraph
                    translated_text = translations[original_text]
                    logger.debug(f"Replacing paragraph: '{original_text[:50]}...' -> '{translated_text[:50]}...'")
                    
                    # Clear all children and set new text
                    element.clear()
                    element.text = translated_text
        else:
            # For other elements, recursively process children
            for child in element:
                self.replace_safe_texts(child, translations, element_map)
    
    def parse_container_xml(self, epub_path: str) -> Optional[str]:
        """Parse container.xml to get OPF path."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                container_xml = zf.read('META-INF/container.xml')
                root = etree.fromstring(container_xml)
                
                ns = {'container': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//container:rootfile', ns)
                
                if rootfile is not None:
                    return rootfile.get('full-path')
        except Exception as e:
            logger.error(f"Failed to parse container.xml: {e}")
        
        return None
    
    def parse_opf(self, epub_path: str, opf_path: str) -> Tuple[List[Tuple[str, str]], List[str]]:
        """Parse OPF file to get manifest items and spine order."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                opf_content = zf.read(opf_path)
                root = etree.fromstring(opf_content)
                
                ns = {'opf': 'http://www.idpf.org/2007/opf'}
                
                # Parse manifest
                manifest_items = []
                manifest = root.find('.//opf:manifest', ns)
                if manifest is not None:
                    for item in manifest.findall('opf:item', ns):
                        item_id = item.get('id')
                        href = item.get('href')
                        media_type = item.get('media-type')
                        if item_id and href:
                            manifest_items.append((item_id, href, media_type))
                
                # Parse spine
                spine_order = []
                spine = root.find('.//opf:spine', ns)
                if spine is not None:
                    for itemref in spine.findall('opf:itemref', ns):
                        idref = itemref.get('idref')
                        if idref:
                            spine_order.append(idref)
                
                return manifest_items, spine_order
        except Exception as e:
            logger.error(f"Failed to parse OPF: {e}")
            return [], []
    
    def get_chapter_files(self, manifest_items: List[Tuple], spine_order: List[str]) -> List[Tuple[str, str]]:
        """Get chapter files in spine order."""
        manifest_dict = {item[0]: item[1] for item in manifest_items}
        
        chapter_files = []
        for idref in spine_order:
            if idref in manifest_dict:
                href = manifest_dict[idref]
                # Only process XHTML/HTML files
                if href.lower().endswith(('.xhtml', '.html', '.htm')):
                    chapter_files.append((idref, href))
        
        return chapter_files
    
    async def translate_chapter(self, chapter_content: str, target_lang: str) -> str:
        """Translate a single chapter while preserving HTML structure."""
        try:
            logger.info(f"Starting chapter translation to {target_lang}")
            # Parse HTML with encoding handling
            try:
                doc = html.fromstring(chapter_content)
            except ValueError:
                # If there's an encoding declaration, parse as bytes
                doc = html.fromstring(chapter_content.encode('utf-8'))
            
            # Extract paragraph-level text blocks
            text_blocks = self.extract_paragraph_texts(doc)
            logger.info(f"Extracted {len(text_blocks)} text blocks from chapter")
            
            if not text_blocks:
                logger.warning("No text blocks found in chapter")
                return chapter_content
            
            # Filter out empty or whitespace-only texts
            texts_to_translate = [text for text in text_blocks if text.strip()]
            logger.info(f"Found {len(texts_to_translate)} non-empty text blocks to translate")
            
            if not texts_to_translate:
                logger.warning("No non-empty texts to translate")
                return chapter_content
            
            # Translate texts
            translations = {}
            for i, text in enumerate(texts_to_translate):
                try:
                    logger.info(f"Translating text {i+1}/{len(texts_to_translate)}: '{text[:100]}...{text[-20:] if len(text) > 100 else ''}'") 
                    translated = await self.translator.translate_text(text, target_lang, "epub")
                    logger.info(f"Translation result: '{translated[:100]}...{translated[-20:] if len(translated) > 100 else ''}'") 
                    translations[text] = translated
                except Exception as e:
                    logger.error(f"Failed to translate text '{text[:50]}...': {e}")
                    translations[text] = text  # Keep original on failure
            
            # Replace text blocks with translations
            logger.info(f"Replacing text blocks with {len(translations)} translations")
            self.replace_paragraph_texts(doc, translations)
            
            # Return updated HTML
            result = html.tostring(doc, encoding='unicode', method='html')
            logger.info(f"Chapter translation completed, result length: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to translate chapter: {e}")
            return chapter_content
    
    async def translate_chapter_with_progress(self, chapter_content: str, target_lang: str, progress_callback: Callable = None) -> str:
        """Translate a single chapter with detailed progress tracking."""
        try:
            logger.info(f"Starting chapter translation to {target_lang}")
            # Parse HTML with encoding handling
            try:
                doc = html.fromstring(chapter_content)
            except ValueError:
                # If there's an encoding declaration, parse as bytes
                doc = html.fromstring(chapter_content.encode('utf-8'))
            
            # Extract paragraph-level text blocks
            text_blocks = self.extract_paragraph_texts(doc)
            logger.info(f"Extracted {len(text_blocks)} text blocks from chapter")
            
            if not text_blocks:
                logger.warning("No text blocks found in chapter")
                return chapter_content
            
            # Filter out empty or whitespace-only texts
            texts_to_translate = [text for text in text_blocks if text.strip()]
            logger.info(f"Found {len(texts_to_translate)} non-empty text blocks to translate")
            
            if not texts_to_translate:
                logger.warning("No non-empty texts to translate")
                return chapter_content
            
            # Translate texts with progress tracking
            translations = {}
            for i, text in enumerate(texts_to_translate):
                try:
                    if progress_callback:
                        progress_callback(i + 1, len(texts_to_translate))
                    
                    logger.info(f"Translating text block {i+1}/{len(texts_to_translate)}: '{text[:100]}...{text[-20:] if len(text) > 100 else ''}'") 
                    translated = await self.translator.translate_text(text, target_lang, "epub")
                    logger.info(f"Translation result: '{translated[:100]}...{translated[-20:] if len(translated) > 100 else ''}'") 
                    translations[text] = translated
                except Exception as e:
                    logger.error(f"Failed to translate text '{text[:50]}...': {e}")
                    translations[text] = text  # Keep original on failure
            
            # Replace text blocks with translations
            logger.info(f"Replacing text blocks with {len(translations)} translations")
            self.replace_paragraph_texts(doc, translations)
            
            # Return updated HTML
            result = html.tostring(doc, encoding='unicode', method='html')
            logger.info(f"Chapter translation completed, result length: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to translate chapter: {e}")
            return chapter_content
    
    async def translate_toc_ncx(self, toc_content: str, target_lang: str) -> str:
        """Translate EPUB2 TOC (toc.ncx) navigation labels."""
        try:
            root = etree.fromstring(toc_content.encode('utf-8'))
            ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
            
            # Find all navLabel text elements
            nav_labels = root.findall('.//ncx:navLabel/ncx:text', ns)
            
            for text_elem in nav_labels:
                if text_elem.text and text_elem.text.strip():
                    try:
                        translated = await self.translator.translate_text(
                            text_elem.text.strip(), 
                            target_lang, 
                            "epub"
                        )
                        text_elem.text = translated
                    except Exception as e:
                        logger.warning(f"Failed to translate TOC text '{text_elem.text}': {e}")
            
            return etree.tostring(root, encoding='unicode', xml_declaration=True)
            
        except Exception as e:
            logger.error(f"Failed to translate toc.ncx: {e}")
            return toc_content
    
    async def translate_nav_xhtml(self, nav_content: str, target_lang: str) -> str:
        """Translate EPUB3 navigation (nav.xhtml) links."""
        try:
            try:
                doc = html.fromstring(nav_content)
            except ValueError:
                # If there's an encoding declaration, parse as bytes
                doc = html.fromstring(nav_content.encode('utf-8'))
            
            # Find all navigation links
            nav_links = doc.xpath('//nav[@epub:type="toc"]//a', 
                                namespaces={'epub': 'http://www.idpf.org/2007/ops'})
            
            for link in nav_links:
                if link.text and link.text.strip():
                    try:
                        translated = await self.translator.translate_text(
                            link.text.strip(), 
                            target_lang, 
                            "epub"
                        )
                        link.text = translated
                    except Exception as e:
                        logger.warning(f"Failed to translate nav link '{link.text}': {e}")
            
            return html.tostring(doc, encoding='unicode', method='html')
            
        except Exception as e:
            logger.error(f"Failed to translate nav.xhtml: {e}")
            return nav_content
    
    async def process_epub(
        self, 
        input_path: str, 
        output_path: str, 
        target_lang: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Process EPUB translation from input to output."""
        temp_dir = None
        try:
            # Step 1: Parse EPUB structure
            opf_path = self.parse_container_xml(input_path)
            if not opf_path:
                return {"success": False, "error": "Failed to parse container.xml"}
            
            manifest_items, spine_order = self.parse_opf(input_path, opf_path)
            if not manifest_items or not spine_order:
                return {"success": False, "error": "Failed to parse OPF file"}
            
            chapter_files = self.get_chapter_files(manifest_items, spine_order)
            logger.info(f"Found {len(chapter_files)} chapter files: {[f[1] for f in chapter_files]}")
            if not chapter_files:
                return {"success": False, "error": "No chapter files found"}
            
            # Step 2: Create temp directory and extract EPUB
            temp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(input_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            opf_base = str(Path(opf_path).parent) if opf_path != "." else "."
            
            # Preview EPUB content before translation
            self.preview_epub_content(temp_dir, chapter_files, opf_base)
            
            # Step 3: Translate chapters
            total_chapters = len(chapter_files)
            logger.info(f"Starting translation of {total_chapters} chapters")
            
            # Count total text blocks for better progress tracking
            total_text_blocks = 0
            processed_text_blocks = 0
            
            for i, (_, href) in enumerate(chapter_files):
                logger.info(f"Processing chapter {i+1}/{total_chapters}: {href}")
                
                # Get normalized file path
                chapter_path = normalize_zip_path(opf_base, href)
                full_path = os.path.join(temp_dir, chapter_path)
                logger.debug(f"Chapter file path: {full_path}")
                
                if os.path.exists(full_path):
                    # Read chapter content
                    with open(full_path, 'r', encoding='utf-8') as f:
                        chapter_content = f.read()
                    logger.info(f"Read chapter content, length: {len(chapter_content)}")
                    
                    # Create a progress callback for this chapter
                    def chapter_progress_callback(current_block, total_blocks):
                        nonlocal processed_text_blocks, total_text_blocks
                        if total_text_blocks == 0:  # First time, estimate total
                            total_text_blocks = total_blocks * total_chapters
                        
                        processed_text_blocks = (i * total_blocks) + current_block
                        if progress_callback:
                            progress_callback(
                                "epub", 
                                f"Chapter {i+1}/{total_chapters} - Block {current_block}/{total_blocks}", 
                                processed_text_blocks, 
                                total_text_blocks
                            )
                    
                    # Translate chapter with detailed progress
                    translated_content = await self.translate_chapter_with_progress(
                        chapter_content, target_lang, chapter_progress_callback
                    )
                    
                    # Write back translated content
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(translated_content)
                    logger.info(f"Chapter {i+1} translation completed")
                else:
                    logger.error(f"Chapter file not found: {full_path}")
            
            # Step 4: Translate TOC files
            logger.info("Starting TOC translation")
            toc_files = ['toc.ncx', 'nav.xhtml']
            for toc_file in toc_files:
                toc_path = os.path.join(temp_dir, toc_file)
                if os.path.exists(toc_path):
                    logger.info(f"Translating TOC file: {toc_file}")
                    with open(toc_path, 'r', encoding='utf-8') as f:
                        toc_content = f.read()
                    
                    if toc_file == 'toc.ncx':
                        translated_toc = await self.translate_toc_ncx(toc_content, target_lang)
                    else:
                        translated_toc = await self.translate_nav_xhtml(toc_content, target_lang)
                    
                    with open(toc_path, 'w', encoding='utf-8') as f:
                        f.write(translated_toc)
                    logger.info(f"TOC file {toc_file} translation completed")
                else:
                    logger.debug(f"TOC file not found: {toc_file}")
            
            # Step 5: Rebuild EPUB with proper structure
            logger.info(f"Rebuilding EPUB to {output_path}")
            self.rebuild_epub(temp_dir, output_path)
            
            # Step 6: Validate output
            logger.info("Validating output EPUB")
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
        
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def preview_epub_content(self, temp_dir: str, chapter_files: List[Tuple[str, str]], opf_base: str):
        """Preview EPUB content for debugging."""
        logger.info("=== EPUB CONTENT PREVIEW ===")
        logger.info(f"Found {len(chapter_files)} chapters:")
        
        for i, (_, href) in enumerate(chapter_files):
            logger.info(f"\nChapter {i+1}: {href}")
            
            # Get normalized file path
            chapter_path = normalize_zip_path(opf_base, href)
            full_path = os.path.join(temp_dir, chapter_path)
            
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        chapter_content = f.read()
                    
                    # Parse HTML and extract text for preview
                    # Handle encoding declaration in HTML
                    try:
                        doc = html.fromstring(chapter_content)
                    except ValueError:
                        # If there's an encoding declaration, parse as bytes
                        doc = html.fromstring(chapter_content.encode('utf-8'))
                    text_blocks = self.extract_paragraph_texts(doc)
                    
                    # Show first few text blocks
                    logger.info(f"  Content length: {len(chapter_content)} chars")
                    logger.info(f"  Text blocks found: {len(text_blocks)}")
                    
                    # Show first 3 text blocks as preview
                    preview_texts = [text.strip() for text in text_blocks if text.strip()][:3]
                    for j, text in enumerate(preview_texts):
                        # Truncate long texts for preview
                        preview_text = text[:200] + "..." if len(text) > 200 else text
                        logger.info(f"  Block {j+1}: {repr(preview_text)}")
                    
                    if len(preview_texts) == 0:
                        logger.warning("  No extractable text blocks found!")
                        # Show raw content sample
                        raw_sample = chapter_content[:500] + "..." if len(chapter_content) > 500 else chapter_content
                        logger.info(f"  Raw content sample: {repr(raw_sample)}")
                        
                except Exception as e:
                    logger.error(f"  Error reading chapter: {e}")
            else:
                logger.error(f"  Chapter file not found: {full_path}")
        
        logger.info("=== END PREVIEW ===")
    
    def rebuild_epub(self, temp_dir: str, output_path: str):
        """Rebuild EPUB ZIP file with proper structure."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # First, add mimetype (uncompressed, must be first)
            mimetype_path = os.path.join(temp_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                zf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            
            # Add all other files
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file == 'mimetype':
                        continue  # Already added
                    
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, temp_dir).replace('\\', '/')
                    zf.write(file_path, arc_name)