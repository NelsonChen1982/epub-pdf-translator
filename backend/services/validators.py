import zipfile
import os
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from lxml import etree
from pathlib import Path


logger = logging.getLogger(__name__)


class EPUBValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_mimetype(self, epub_path: str) -> bool:
        """Validate mimetype file is first and uncompressed."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                # Check if mimetype is first file
                if zf.namelist()[0] != 'mimetype':
                    self.errors.append("mimetype must be the first file in ZIP")
                    return False
                
                # Check if mimetype is uncompressed
                mimetype_info = zf.getinfo('mimetype')
                if mimetype_info.compress_type != zipfile.ZIP_STORED:
                    self.errors.append("mimetype must be uncompressed")
                    return False
                
                # Check mimetype content
                mimetype_content = zf.read('mimetype').decode('utf-8')
                if mimetype_content.strip() != 'application/epub+zip':
                    self.errors.append(f"Invalid mimetype content: {mimetype_content}")
                    return False
                
                return True
        except Exception as e:
            self.errors.append(f"Failed to validate mimetype: {e}")
            return False
    
    def validate_container_xml(self, epub_path: str) -> Optional[str]:
        """Validate container.xml and return OPF path."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                container_xml = zf.read('META-INF/container.xml')
                root = etree.fromstring(container_xml)
                
                # Find OPF file path
                ns = {'container': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile = root.find('.//container:rootfile', ns)
                
                if rootfile is None:
                    self.errors.append("No rootfile found in container.xml")
                    return None
                
                opf_path = rootfile.get('full-path')
                if not opf_path:
                    self.errors.append("No full-path in rootfile")
                    return None
                
                # Check if OPF file exists in ZIP
                if opf_path not in zf.namelist():
                    self.errors.append(f"OPF file not found in ZIP: {opf_path}")
                    return None
                
                return opf_path
        except Exception as e:
            self.errors.append(f"Failed to validate container.xml: {e}")
            return None
    
    def validate_opf(self, epub_path: str, opf_path: str) -> Tuple[List[str], List[str]]:
        """Validate OPF file and return manifest items and spine order."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                opf_content = zf.read(opf_path)
                root = etree.fromstring(opf_content)
                
                ns = {'opf': 'http://www.idpf.org/2007/opf'}
                
                # Check manifest items
                manifest_items = []
                manifest = root.find('.//opf:manifest', ns)
                if manifest is None:
                    self.errors.append("No manifest found in OPF")
                    return [], []
                
                for item in manifest.findall('opf:item', ns):
                    item_id = item.get('id')
                    href = item.get('href')
                    if item_id and href:
                        manifest_items.append((item_id, href))
                
                # Check spine order
                spine_order = []
                spine = root.find('.//opf:spine', ns)
                if spine is None:
                    self.errors.append("No spine found in OPF")
                    return manifest_items, []
                
                for itemref in spine.findall('opf:itemref', ns):
                    idref = itemref.get('idref')
                    if idref:
                        spine_order.append(idref)
                
                # Validate spine references exist in manifest
                manifest_ids = [item[0] for item in manifest_items]
                for idref in spine_order:
                    if idref not in manifest_ids:
                        self.errors.append(f"Spine idref '{idref}' not found in manifest")
                
                return manifest_items, spine_order
        except Exception as e:
            self.errors.append(f"Failed to validate OPF: {e}")
            return [], []
    
    def validate_file_existence(self, epub_path: str, opf_path: str, manifest_items: List[Tuple[str, str]]) -> bool:
        """Validate all manifest files exist in ZIP."""
        try:
            with zipfile.ZipFile(epub_path, 'r') as zf:
                opf_base = str(Path(opf_path).parent)
                zip_files = set(zf.namelist())
                
                for item_id, href in manifest_items:
                    # Normalize path
                    if opf_base == ".":
                        file_path = href
                    else:
                        file_path = f"{opf_base}/{href}".replace("//", "/")
                    
                    if file_path not in zip_files:
                        self.errors.append(f"Manifest file not found in ZIP: {file_path}")
                
                return len(self.errors) == 0
        except Exception as e:
            self.errors.append(f"Failed to validate file existence: {e}")
            return False
    
    def run_epubcheck(self, epub_path: str) -> bool:
        """Run epubcheck if available."""
        try:
            result = subprocess.run(
                ['epubcheck', epub_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.errors.append(f"epubcheck failed: {result.stderr}")
                return False
            
            if result.stdout:
                logger.info(f"epubcheck output: {result.stdout}")
            
            return True
        except subprocess.TimeoutExpired:
            self.warnings.append("epubcheck timed out")
            return True  # Don't fail on timeout
        except FileNotFoundError:
            self.warnings.append("epubcheck not found, skipping validation")
            return True  # Don't fail if epubcheck not installed
        except Exception as e:
            self.warnings.append(f"epubcheck error: {e}")
            return True  # Don't fail on epubcheck errors
    
    def validate_epub(self, epub_path: str) -> Dict:
        """Complete EPUB validation."""
        self.errors = []
        self.warnings = []
        
        # Step 1: Validate mimetype
        if not self.validate_mimetype(epub_path):
            return {
                "valid": False,
                "errors": self.errors,
                "warnings": self.warnings
            }
        
        # Step 2: Validate container.xml
        opf_path = self.validate_container_xml(epub_path)
        if not opf_path:
            return {
                "valid": False,
                "errors": self.errors,
                "warnings": self.warnings
            }
        
        # Step 3: Validate OPF
        manifest_items, spine_order = self.validate_opf(epub_path, opf_path)
        if not manifest_items or not spine_order:
            return {
                "valid": False,
                "errors": self.errors,
                "warnings": self.warnings
            }
        
        # Step 4: Validate file existence
        self.validate_file_existence(epub_path, opf_path, manifest_items)
        
        # Step 5: Run epubcheck
        self.run_epubcheck(epub_path)
        
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings
        }