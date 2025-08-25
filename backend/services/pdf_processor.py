import os
import logging
from typing import List, Dict, Optional, Callable, Tuple
from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LTTextContainer, LTTextBox, LTTextLine, LTChar
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from .translator import TranslationService


logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self):
        self.translator = TranslationService()
        self.setup_fonts()
    
    def setup_fonts(self):
        """Setup fonts for multi-language support."""
        try:
            # Try to register Noto Sans font for better international support
            # Note: In production, you should include font files or use system fonts
            font_paths = [
                '/System/Library/Fonts/Arial.ttf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                        addMapping('CustomFont', 0, 0, 'CustomFont')
                        break
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Font setup failed: {e}. Using default fonts.")
    
    def extract_text_with_layout(self, pdf_path: str) -> List[Dict]:
        """Extract text with layout information for paragraph detection."""
        pages_content = []
        
        try:
            for page_num, page_layout in enumerate(extract_pages(pdf_path), 1):
                page_text_boxes = []
                
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        # Get bounding box coordinates
                        x0, y0, x1, y1 = element.bbox
                        text = element.get_text().strip()
                        
                        if text:
                            page_text_boxes.append({
                                'text': text,
                                'bbox': (x0, y0, x1, y1),
                                'page': page_num
                            })
                
                # Sort text boxes by position (top to bottom, left to right)
                page_text_boxes.sort(key=lambda x: (-x['bbox'][3], x['bbox'][0]))
                pages_content.append(page_text_boxes)
        
        except Exception as e:
            logger.error(f"Failed to extract PDF layout: {e}")
            # Fallback to simple text extraction
            try:
                text = extract_text(pdf_path)
                pages_content = [
                    [{'text': text, 'bbox': (0, 0, 0, 0), 'page': 1}]
                ]
            except Exception as e2:
                logger.error(f"Fallback text extraction also failed: {e2}")
                return []
        
        return pages_content
    
    def merge_paragraphs(self, text_boxes: List[Dict]) -> List[str]:
        """Merge text boxes into paragraphs based on layout."""
        if not text_boxes:
            return []
        
        paragraphs = []
        current_paragraph = ""
        
        # Calculate average line height for merging criteria
        line_heights = []
        for i in range(len(text_boxes) - 1):
            curr_box = text_boxes[i]
            next_box = text_boxes[i + 1]
            height_diff = abs(curr_box['bbox'][3] - next_box['bbox'][3])
            if height_diff > 0:
                line_heights.append(height_diff)
        
        avg_line_height = sum(line_heights) / len(line_heights) if line_heights else 20
        merge_threshold = 1.5 * avg_line_height
        
        for i, text_box in enumerate(text_boxes):
            text = text_box['text']
            
            # Check if this should start a new paragraph
            if i == 0:
                current_paragraph = text
            else:
                prev_box = text_boxes[i - 1]
                curr_box = text_box
                
                # Calculate spacing criteria
                vertical_gap = abs(prev_box['bbox'][1] - curr_box['bbox'][3])
                horizontal_overlap = self.calculate_horizontal_overlap(
                    prev_box['bbox'], curr_box['bbox']
                )
                
                # Merge conditions based on specification
                should_merge = (
                    vertical_gap < merge_threshold and  # Line spacing threshold
                    horizontal_overlap > 0.7  # 70% horizontal overlap
                )
                
                if should_merge:
                    # Add space if needed
                    if not current_paragraph.endswith(' '):
                        current_paragraph += ' '
                    current_paragraph += text
                else:
                    # Start new paragraph
                    if current_paragraph.strip():
                        paragraphs.append(current_paragraph.strip())
                    current_paragraph = text
        
        # Add the last paragraph
        if current_paragraph.strip():
            paragraphs.append(current_paragraph.strip())
        
        return paragraphs
    
    def calculate_horizontal_overlap(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """Calculate horizontal overlap ratio between two bounding boxes."""
        x1_start, _, x1_end, _ = bbox1
        x2_start, _, x2_end, _ = bbox2
        
        # Calculate overlap
        overlap_start = max(x1_start, x2_start)
        overlap_end = min(x1_end, x2_end)
        overlap_width = max(0, overlap_end - overlap_start)
        
        # Calculate union width
        union_start = min(x1_start, x2_start)
        union_end = max(x1_end, x2_end)
        union_width = union_end - union_start
        
        if union_width == 0:
            return 0
        
        return overlap_width / union_width
    
    async def translate_paragraphs(
        self, 
        paragraphs: List[str], 
        target_lang: str,
        progress_callback: Optional[Callable] = None
    ) -> List[str]:
        """Translate paragraphs using the translation service."""
        translated_paragraphs = []
        
        for i, paragraph in enumerate(paragraphs):
            if progress_callback:
                progress_callback("pdf", f"Paragraph {i+1}/{len(paragraphs)}", i+1, len(paragraphs))
            
            try:
                # Skip very short paragraphs or those that look like page numbers
                if len(paragraph.strip()) < 3 or paragraph.strip().isdigit():
                    translated_paragraphs.append(paragraph)
                    continue
                
                translated = await self.translator.translate_text(
                    paragraph, target_lang, "pdf"
                )
                translated_paragraphs.append(translated)
                
            except Exception as e:
                logger.warning(f"Failed to translate paragraph: {e}")
                translated_paragraphs.append(paragraph)  # Keep original on failure
        
        return translated_paragraphs
    
    def create_pdf_from_paragraphs(self, paragraphs: List[str], output_path: str):
        """Create a new PDF from translated paragraphs."""
        try:
            # Create document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            # Setup styles
            styles = getSampleStyleSheet()
            
            # Create custom style for better international text support
            try:
                normal_style = ParagraphStyle(
                    'CustomNormal',
                    parent=styles['Normal'],
                    fontName='CustomFont',
                    fontSize=12,
                    leading=18,
                    spaceAfter=12
                )
            except:
                # Fallback to default font if custom font not available
                normal_style = styles['Normal']
            
            # Build content
            story = []
            
            for paragraph in paragraphs:
                if paragraph.strip():
                    # Create paragraph
                    para = Paragraph(paragraph, normal_style)
                    story.append(para)
                    
                    # Add some spacing between paragraphs
                    story.append(Spacer(1, 6))
            
            # Build PDF
            doc.build(story)
            
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
        """Process PDF translation from input to output."""
        try:
            # Step 1: Extract text with layout information
            if progress_callback:
                progress_callback("pdf", "Extracting text", 0, 100)
            
            pages_content = self.extract_text_with_layout(input_path)
            if not pages_content:
                return {"success": False, "error": "Failed to extract text from PDF"}
            
            # Step 2: Merge all pages and create paragraphs
            if progress_callback:
                progress_callback("pdf", "Analyzing layout", 10, 100)
            
            all_text_boxes = []
            for page_boxes in pages_content:
                all_text_boxes.extend(page_boxes)
            
            paragraphs = self.merge_paragraphs(all_text_boxes)
            if not paragraphs:
                return {"success": False, "error": "No paragraphs found in PDF"}
            
            # Step 3: Translate paragraphs
            if progress_callback:
                progress_callback("pdf", "Translating content", 20, 100)
            
            def translation_progress(current, total):
                progress = 20 + int((current / total) * 70)  # 20-90% for translation
                if progress_callback:
                    progress_callback("pdf", f"Translating {current}/{total}", progress, 100)
            
            translated_paragraphs = await self.translate_paragraphs(
                paragraphs, target_lang, translation_progress
            )
            
            # Step 4: Create new PDF
            if progress_callback:
                progress_callback("pdf", "Creating PDF", 90, 100)
            
            self.create_pdf_from_paragraphs(translated_paragraphs, output_path)
            
            if progress_callback:
                progress_callback("pdf", "Completed", 100, 100)
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return {"success": False, "error": str(e)}