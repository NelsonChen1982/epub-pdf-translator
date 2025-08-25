import os
import logging
from typing import List, Dict, Optional, Callable, Tuple
import pdfplumber
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from .translator import TranslationService

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self):
        self.translator = TranslationService()
        self.setup_fonts()
        self.font_name = "Helvetica"  # default; will be switched by select_cjk_font

    def setup_fonts(self):
        """Setup fonts for multi-language support (CJK-safe).
        Preference order:
          1) Env var CJK_FONT (path to .otf/.ttf)
          2) Well-known Noto CJK OTFs per OS
          3) System sans fallbacks
          4) Register CID fallback families (works without local OTF/TTF; covers CJK)
        """
        self.has_unicode_font = False
        try:
            # 1) explicit override
            env_font = os.getenv("CJK_FONT")
            if env_font and os.path.exists(env_font) and env_font.lower().endswith((".otf", ".ttf")):
                try:
                    pdfmetrics.registerFont(TTFont('CJKFont', env_font))
                    self.font_name = 'CJKFont'
                    self.has_unicode_font = True
                    logger.info(f"Registered CJK font from CJK_FONT: {env_font}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to register CJK_FONT '{env_font}': {e}")

            # 2) common Noto CJK OTFs (region-specific)
            noto_candidates = [
                # macOS Homebrew / manual installs
                '/Library/Fonts/NotoSansCJKtc-Regular.otf',
                '/Library/Fonts/NotoSansCJKsc-Regular.otf',
                '/Library/Fonts/NotoSansCJKjp-Regular.otf',
                '/Library/Fonts/NotoSansCJKkr-Regular.otf',
                # Linux
                '/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf',
                '/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf',
                '/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf',
                '/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf',
                # Windows (manual installs)
                'C\\\Windows\\Fonts\\NotoSansCJKtc-Regular.otf',
                'C\\\Windows\\Fonts\\NotoSansCJKsc-Regular.otf',
                'C\\\Windows\\Fonts\\NotoSansCJKjp-Regular.otf',
                'C\\\Windows\\Fonts\\NotoSansCJKkr-Regular.otf',
            ]
            for p in noto_candidates:
                if os.path.exists(p):
                    try:
                        pdfmetrics.registerFont(TTFont('CJKFont', p))
                        self.font_name = 'CJKFont'
                        self.has_unicode_font = True
                        logger.info(f"Registered Noto CJK font: {p}")
                        return
                    except Exception as e:
                        logger.debug(f"Failed to register {p}: {e}")
                        continue

            # 3) generic system fallbacks (not guaranteed for CJK coverage)
            fallback_paths = [
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                '/System/Library/Fonts/Arial.ttf',
                'C\\\Windows\\Fonts\\arial.ttf',
            ]
            for p in fallback_paths:
                if os.path.exists(p):
                    try:
                        pdfmetrics.registerFont(TTFont('FallbackFont', p))
                        logger.info(f"Registered fallback font: {p}")
                        # do not early return; we still want to add CID fonts next
                        break
                    except Exception:
                        continue

            # 4) CID fallback families (works without local .otf/.ttf, covers JP/ZH/KR)
            try:
                # Register a set of CID fonts; we'll pick one per target_lang later
                for cid in ['HeiseiKakuGo-W5', 'HeiseiMin-W3', 'STSong-Light', 'MSung-Light', 'HYSMyeongJo-Medium']:
                    try:
                        pdfmetrics.registerFont(UnicodeCIDFont(cid))
                    except Exception as e:
                        logger.debug(f"CID font {cid} not available: {e}")
                logger.info("Registered CID fallback families for CJK.")
            except Exception as e:
                logger.debug(f"CID registration skipped: {e}")

            logger.warning("No dedicated CJK OTF/TTF registered. Will rely on CID or fallback fonts.")
        except Exception as e:
            logger.warning(f"Font setup failed: {e}. Using defaults; CJK may not render.")

    def select_cjk_font(self, target_lang: str):
        """Pick a font name that supports the target language.
        If a dedicated CJK TrueType font is registered (self.has_unicode_font), use it.
        Otherwise, choose a CID fallback family best matching the language.
        """
        lang = (target_lang or "").lower()
        if self.has_unicode_font:
            # We've registered 'CJKFont' already
            self.font_name = 'CJKFont'
            return
        # Map language to CID font
        if lang.startswith('ja'):
            self.font_name = 'HeiseiKakuGo-W5'  # Japanese Gothic
        elif lang.startswith('zh-tw') or lang.startswith('zh-hk') or lang.startswith('zh-hant'):
            self.font_name = 'MSung-Light'      # Traditional Chinese
        elif lang.startswith('zh') or lang.startswith('zh-cn') or lang.startswith('zh-hans'):
            self.font_name = 'STSong-Light'     # Simplified Chinese
        elif lang.startswith('ko'):
            self.font_name = 'HYSMyeongJo-Medium'  # Korean
        else:
            self.font_name = 'Helvetica'        # fallback
        logger.info(f"Selected font for '{target_lang}': {self.font_name}")

    def extract_content_structure(self, pdf_path: str) -> List[Dict]:
        """Extract structured content from PDF using pdfplumber."""
        pages_content = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Processing PDF with {len(pdf.pages)} pages")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.debug(f"Processing page {page_num}")
                    
                    page_content = {
                        'page': page_num,
                        'text_blocks': [],
                        'tables': [],
                        'width': page.width,
                        'height': page.height
                    }
                    
                    # Extract tables first (they have priority)
                    tables = page.extract_tables()
                    for table in tables or []:
                        if table and any(any(cell for cell in row if cell) for row in table):
                            page_content['tables'].append(table)
                            logger.debug(f"Found table with {len(table)} rows")
                    
                    # Extract text with line-level precision
                    lines = page.extract_text_lines()
                    if lines:
                        paragraphs = self.group_lines_into_paragraphs(lines)
                        page_content['text_blocks'] = paragraphs
                        logger.debug(f"Extracted {len(paragraphs)} paragraphs from page {page_num}")
                    
                    pages_content.append(page_content)
                    
        except Exception as e:
            logger.error(f"Failed to extract PDF content: {e}")
            return []
            
        return pages_content

    def group_lines_into_paragraphs(self, lines: List[Dict]) -> List[str]:
        """Group text lines into logical paragraphs based on layout."""
        if not lines:
            return []
        
        paragraphs = []
        current_paragraph = []
        prev_line = None
        
        for line in lines:
            text = line.get('text', '').strip()
            if not text:
                continue
                
            # Get line position info
            top = line.get('top', 0)
            x0 = line.get('x0', 0)
            
            # Determine if this starts a new paragraph
            is_new_paragraph = False
            
            if prev_line:
                prev_top = prev_line.get('top', 0)
                prev_x0 = prev_line.get('x0', 0)
                
                # Large vertical gap indicates new paragraph
                vertical_gap = prev_top - top
                if vertical_gap > 15:  # Adjust threshold as needed
                    is_new_paragraph = True
                    
                # Significant horizontal indentation change
                horizontal_change = abs(x0 - prev_x0)
                if horizontal_change > 20:  # Adjust threshold as needed
                    is_new_paragraph = True
                    
                # Text that looks like headers (short lines, different positioning)
                if len(text) < 60 and vertical_gap > 10:
                    is_new_paragraph = True
            
            if is_new_paragraph and current_paragraph:
                # Finish current paragraph
                paragraph_text = ' '.join(current_paragraph).strip()
                if len(paragraph_text) > 10:  # Skip very short paragraphs
                    paragraphs.append(paragraph_text)
                current_paragraph = []
            
            current_paragraph.append(text)
            prev_line = line
        
        # Add final paragraph
        if current_paragraph:
            paragraph_text = ' '.join(current_paragraph).strip()
            if len(paragraph_text) > 10:
                paragraphs.append(paragraph_text)
        
        return paragraphs

    def preview_pdf_content(self, pages_content: List[Dict]):
        """Preview PDF content for debugging."""
        logger.info("=== PDF CONTENT PREVIEW ===")
        logger.info(f"Found {len(pages_content)} pages")
        
        total_paragraphs = 0
        total_tables = 0
        
        for page in pages_content[:3]:  # Show first 3 pages
            page_num = page['page']
            text_blocks = page['text_blocks']
            tables = page['tables']
            
            logger.info(f"\nPage {page_num}:")
            logger.info(f"  Text blocks: {len(text_blocks)}")
            logger.info(f"  Tables: {len(tables)}")
            
            # Show first few paragraphs
            for i, block in enumerate(text_blocks[:3]):
                preview_text = block[:100] + "..." if len(block) > 100 else block
                logger.info(f"  Block {i+1}: {repr(preview_text)}")
            
            # Show table info
            for i, table in enumerate(tables[:2]):
                logger.info(f"  Table {i+1}: {len(table)} rows × {len(table[0]) if table else 0} cols")
                if table and table[0]:
                    first_row = [str(cell)[:20] + "..." if cell and len(str(cell)) > 20 else str(cell) 
                                for cell in table[0][:3]]
                    logger.info(f"    Sample: {first_row}")
            
            total_paragraphs += len(text_blocks)
            total_tables += len(tables)
        
        logger.info(f"\nTotal extractable content: {total_paragraphs} paragraphs, {total_tables} tables")
        logger.info("=== END PREVIEW ===")

    async def translate_content(self, pages_content: List[Dict], target_lang: str, progress_callback=None) -> List[Dict]:
        """Translate all content while preserving structure."""
        translated_pages = []
        total_items = sum(len(page['text_blocks']) + len(page['tables']) for page in pages_content)
        current_item = 0
        
        logger.info(f"Starting translation of {total_items} content items")
        
        for page in pages_content:
            translated_page = {
                'page': page['page'],
                'text_blocks': [],
                'tables': [],
                'width': page['width'],
                'height': page['height']
            }
            
            # Translate text blocks
            for i, text_block in enumerate(page['text_blocks']):
                current_item += 1
                if progress_callback:
                    progress_callback("pdf", f"Page {page['page']} - Paragraph {i+1}", current_item, total_items)
                
                try:
                    logger.info(f"Translating paragraph {current_item}/{total_items}: '{text_block[:100]}...'")
                    translated_text = await self.translator.translate_text(text_block, target_lang, "pdf")
                    translated_page['text_blocks'].append(translated_text)
                    logger.debug(f"Translation result: '{translated_text[:100]}...'")
                except Exception as e:
                    logger.error(f"Failed to translate text block: {e}")
                    translated_page['text_blocks'].append(text_block)  # Keep original
            
            # Translate tables
            for i, table in enumerate(page['tables']):
                current_item += 1
                if progress_callback:
                    progress_callback("pdf", f"Page {page['page']} - Table {i+1}", current_item, total_items)
                
                try:
                    translated_table = await self.translate_table(table, target_lang)
                    translated_page['tables'].append(translated_table)
                    logger.info(f"Translated table {i+1} with {len(table)} rows")
                except Exception as e:
                    logger.error(f"Failed to translate table: {e}")
                    translated_page['tables'].append(table)  # Keep original
            
            translated_pages.append(translated_page)
        
        logger.info(f"Translation completed: {len(translated_pages)} pages processed")
        return translated_pages

    async def translate_table(self, table: List[List[str]], target_lang: str) -> List[List[str]]:
        """Translate table content while preserving structure."""
        translated_table = []
        
        for row_idx, row in enumerate(table):
            translated_row = []
            for cell in row:
                if cell and isinstance(cell, str) and cell.strip():
                    # Skip very short cells (likely numbers or codes)
                    if len(cell.strip()) > 3:
                        try:
                            translated_cell = await self.translator.translate_text(cell.strip(), target_lang, "pdf")
                            translated_row.append(translated_cell)
                        except Exception as e:
                            logger.warning(f"Failed to translate table cell '{cell[:30]}...': {e}")
                            translated_row.append(cell)
                    else:
                        translated_row.append(cell)  # Keep short cells as-is
                else:
                    translated_row.append(cell or "")
            translated_table.append(translated_row)
        
        return translated_table

    def prepare_text_for_pdf(self, text: str, strict: bool = False) -> str:
        """Prepare text for PDF generation by handling special characters."""
        if not text:
            return ""
        
        # Basic HTML entity escaping
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        if strict:
            # More aggressive cleaning for problematic characters
            # Remove or replace characters that might cause font issues
            import unicodedata
            
            # Normalize Unicode characters
            text = unicodedata.normalize('NFKC', text)
            
            # Remove or replace problematic characters
            problematic_chars = {
                '\u2018': "'",  # Left single quotation mark
                '\u2019': "'",  # Right single quotation mark
                '\u201c': '"',  # Left double quotation mark
                '\u201d': '"',  # Right double quotation mark
                '\u2013': '-',  # En dash
                '\u2014': '--', # Em dash
                '\u2026': '...', # Horizontal ellipsis
            }
            
            for char, replacement in problematic_chars.items():
                text = text.replace(char, replacement)
            
            # Filter out characters that might not be supported by fonts
            # Keep only printable ASCII and common Unicode ranges
            filtered_chars = []
            for char in text:
                code = ord(char)
                # Allow: ASCII printable, Latin, CJK, etc.
                if (32 <= code <= 126 or  # ASCII printable
                    0x00A0 <= code <= 0x017F or  # Latin Extended
                    0x4E00 <= code <= 0x9FFF or  # CJK Unified Ideographs
                    0x3040 <= code <= 0x309F or  # Hiragana
                    0x30A0 <= code <= 0x30FF or  # Katakana
                    0xAC00 <= code <= 0xD7AF or  # Hangul
                    char in '\n\r\t'):  # Whitespace
                    filtered_chars.append(char)
                else:
                    filtered_chars.append(' ')  # Replace unknown chars with space
            
            text = ''.join(filtered_chars)
        
        # Clean up multiple spaces and normalize whitespace
        import re
        text = re.sub(r'\s+', ' ', text.strip())
        
        return text

    def create_pdf_from_content(self, pages_content: List[Dict], output_path: str):
        """Create PDF from translated content with proper formatting."""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            # Setup styles
            styles = getSampleStyleSheet()

            # Create custom style for better international text support
            normal_style = ParagraphStyle(
                'DocNormal',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=12,
                leading=16,
                spaceAfter=12,
                wordWrap='LTR',
                allowWidows=1,
                allowOrphans=1,
            )
            logger.info(f"Using paragraph font: {self.font_name}")

            # Table style
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ])

            story = []

            for page in pages_content:
                # Add text blocks
                for text_block in page['text_blocks']:
                    if text_block.strip():
                        try:
                            # Clean and prepare text for PDF
                            clean_text = self.prepare_text_for_pdf(text_block)
                            para = Paragraph(clean_text, normal_style)
                            story.append(para)
                            story.append(Spacer(1, 6))
                        except Exception as e:
                            logger.warning(f"Failed to create paragraph: {e}")
                            # Fallback: try with even more cleaning
                            try:
                                fallback_text = self.prepare_text_for_pdf(text_block, strict=True)
                                para = Paragraph(fallback_text, normal_style)
                                story.append(para)
                                story.append(Spacer(1, 6))
                            except Exception as e2:
                                logger.error(f"Even fallback failed: {e2}, skipping paragraph")

                # Add tables
                for table in page['tables']:
                    if table:
                        try:
                            # Clean table data with proper text preparation
                            clean_table = []
                            for row in table:
                                clean_row = [self.prepare_text_for_pdf(str(cell or "")) for cell in row]
                                clean_table.append(clean_row)

                            table_obj = Table(clean_table)
                            table_obj.setStyle(table_style)
                            story.append(table_obj)
                            story.append(Spacer(1, 12))
                        except Exception as e:
                            logger.warning(f"Failed to create table: {e}")

                # Add page break except for last page
                if page != pages_content[-1]:
                    story.append(PageBreak())

            # Build PDF
            doc.build(story)
            logger.info(f"PDF created successfully: {output_path}")

        except Exception as e:
            logger.error(f"Failed to create PDF: {e}")
            raise

    async def process_pdf(
        self,
        input_path: str,
        output_path: str,
        target_lang: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Process PDF translation using pdfplumber."""
        try:
            logger.info(f"Starting PDF processing: {input_path}")

            # Step 1: Extract content structure
            if progress_callback:
                progress_callback("pdf", "Analyzing PDF structure", 1, 100)

            pages_content = self.extract_content_structure(input_path)
            if not pages_content:
                return {"success": False, "error": "Failed to extract content from PDF"}

            logger.info(f"Extracted content from {len(pages_content)} pages")

            # Preview content
            self.preview_pdf_content(pages_content)

            # Step 2: Translate content
            if progress_callback:
                progress_callback("pdf", "Starting translation", 10, 100)

            def translation_progress(file_type, current_item, current, total):
                # Map translation progress to 10-90% of total
                progress = 10 + int((current / total) * 80)
                if progress_callback:
                    progress_callback("pdf", current_item, progress, 100)

            translated_content = await self.translate_content(
                pages_content, target_lang, translation_progress
            )

            # Select a font that matches the target language (CJK safe)
            self.select_cjk_font(target_lang)

            # Step 3: Create output PDF
            if progress_callback:
                progress_callback("pdf", "Creating translated PDF", 95, 100)

            self.create_pdf_from_content(translated_content, output_path)

            if progress_callback:
                progress_callback("pdf", "PDF processing completed", 100, 100)

            logger.info("PDF processing completed successfully")
            return {"success": True}

        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return {"success": False, "error": str(e)}