import os
import hashlib
import magic
from typing import Optional, List
from pathlib import Path


class SecurityValidator:
    """Security validation for uploaded files."""
    
    ALLOWED_MIME_TYPES = {
        'epub': ['application/epub+zip', 'application/zip'],
        'pdf': ['application/pdf']
    }
    
    ALLOWED_EXTENSIONS = ['.epub', '.pdf']
    
    # Maximum file size (100MB by default)
    MAX_FILE_SIZE = int(os.getenv('UPLOAD_MAX_SIZE', 104857600))
    
    # Suspicious patterns to check in file content
    SUSPICIOUS_PATTERNS = [
        b'<script',
        b'javascript:',
        b'<?php',
        b'<%',
        b'<iframe',
        b'eval(',
        b'document.write',
        b'window.location'
    ]
    
    @classmethod
    def validate_file_extension(cls, filename: str) -> bool:
        """Validate file has allowed extension."""
        suffix = Path(filename).suffix.lower()
        return suffix in cls.ALLOWED_EXTENSIONS
    
    @classmethod
    def validate_file_size(cls, file_size: int) -> bool:
        """Validate file size is within limits."""
        return file_size <= cls.MAX_FILE_SIZE
    
    @classmethod
    def validate_mime_type(cls, file_path: str, expected_type: str) -> bool:
        """Validate MIME type using python-magic."""
        try:
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(file_path)
            
            allowed_mimes = cls.ALLOWED_MIME_TYPES.get(expected_type, [])
            return detected_mime in allowed_mimes
        except Exception:
            # If magic fails, fall back to extension check
            return cls.validate_file_extension(file_path)
    
    @classmethod
    def scan_for_malicious_content(cls, file_path: str, max_scan_size: int = 1024 * 1024) -> List[str]:
        """Scan file for suspicious patterns."""
        threats = []
        
        try:
            with open(file_path, 'rb') as f:
                # Only scan first MB to avoid performance issues
                content = f.read(max_scan_size)
                
                for pattern in cls.SUSPICIOUS_PATTERNS:
                    if pattern in content.lower():
                        threats.append(f"Suspicious pattern found: {pattern.decode('utf-8', errors='ignore')}")
        except Exception as e:
            threats.append(f"Failed to scan file: {e}")
        
        return threats
    
    @classmethod
    def calculate_file_hash(cls, file_path: str) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    @classmethod
    def validate_file(cls, file_path: str, filename: str, expected_type: str) -> dict:
        """Complete file validation."""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'file_hash': None
        }
        
        # Check file exists
        if not os.path.exists(file_path):
            result['valid'] = False
            result['errors'].append("File not found")
            return result
        
        # Validate extension
        if not cls.validate_file_extension(filename):
            result['valid'] = False
            result['errors'].append(f"Invalid file extension. Allowed: {', '.join(cls.ALLOWED_EXTENSIONS)}")
        
        # Validate file size
        file_size = os.path.getsize(file_path)
        if not cls.validate_file_size(file_size):
            result['valid'] = False
            result['errors'].append(f"File too large. Maximum size: {cls.MAX_FILE_SIZE} bytes")
        
        # Validate MIME type
        if not cls.validate_mime_type(file_path, expected_type):
            result['valid'] = False
            result['errors'].append(f"Invalid file type. Expected {expected_type}")
        
        # Scan for malicious content
        threats = cls.scan_for_malicious_content(file_path)
        if threats:
            result['warnings'].extend(threats)
            # Don't fail validation for warnings, but log them
        
        # Calculate file hash for integrity
        try:
            result['file_hash'] = cls.calculate_file_hash(file_path)
        except Exception as e:
            result['warnings'].append(f"Failed to calculate file hash: {e}")
        
        return result


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self.requests = {}  # IP -> list of timestamps
        self.max_requests = int(os.getenv('RATE_LIMIT_REQUESTS', 10))
        self.time_window = int(os.getenv('RATE_LIMIT_WINDOW', 3600))  # 1 hour
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if client is allowed to make request."""
        import time
        
        now = time.time()
        
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if now - req_time < self.time_window
            ]
        else:
            self.requests[client_ip] = []
        
        # Check if under limit
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_ip].append(now)
        return True
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client."""
        if client_ip not in self.requests:
            return self.max_requests
        
        return max(0, self.max_requests - len(self.requests[client_ip]))


# Global instances
security_validator = SecurityValidator()
rate_limiter = RateLimiter()