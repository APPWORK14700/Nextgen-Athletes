"""
Media Upload Service for secure file uploads with validation and scanning
"""
import logging
import os
import mimetypes
import hashlib
import filetype  # filetype for file type detection
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models.media import MediaCreate, MediaUpdate
from ..models.media_responses import MediaResponse
from ..models.base import PaginatedResponse
from ..api.exceptions import ValidationError, DatabaseError, ResourceNotFoundError
from .database_service import DatabaseService
from ..utils.athlete_utils import AthleteUtils

logger = logging.getLogger(__name__)


class MediaUploadService:
    """Service for handling secure media uploads with comprehensive validation"""
    
    def __init__(self):
        self.media_repository = DatabaseService("media")
        self.athlete_repository = DatabaseService("athlete_profiles")
        
        # Security configuration
        self.config = {
            'max_file_size_mb': 50,  # 50MB max file size
            'allowed_mime_types': {
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'video/mp4', 'video/avi', 'video/mov', 'video/wmv',
                'application/pdf', 'text/plain'
            },
            'max_filename_length': 255,
            'scan_for_malware': True,
            'virus_total_api_key': os.getenv('VIRUS_TOTAL_API_KEY'),
            'blocked_extensions': {'.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js'},
            'max_uploads_per_hour': 100,
            'upload_rate_limit_window': 3600  # 1 hour
        }
        
        # Initialize upload tracking for rate limiting
        self._upload_counts = {}
    
    def _validate_file_size(self, file_content: bytes) -> None:
        """Validate file size against configured limits"""
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > self.config['max_file_size_mb']:
            raise ValidationError(
                f"File size {file_size_mb:.2f}MB exceeds maximum allowed size of {self.config['max_file_size_mb']}MB"
            )
    
    def _validate_file_type(self, file_content: bytes, filename: str) -> str:
        """Validate file type using filetype library and extension checks"""
        # Check file extension first
        _, ext = os.path.splitext(filename.lower())
        if ext in self.config['blocked_extensions']:
            raise ValidationError(f"File extension {ext} is not allowed")
        
        # Use filetype to detect actual MIME type from content
        detected_type = filetype.guess(file_content)
        if not detected_type:
            raise ValidationError("Unable to determine file type from content")
        
        detected_mime = detected_type.mime
        
        # Validate against allowed MIME types
        if detected_mime not in self.config['allowed_mime_types']:
            raise ValidationError(f"File type {detected_mime} not allowed")
        
        # Additional validation: ensure extension matches detected type
        expected_extensions = {
            'image/jpeg': ['.jpg', '.jpeg'],
            'image/png': ['.png'],
            'image/gif': ['.gif'],
            'image/webp': ['.webp'],
            'video/mp4': ['.mp4'],
            'video/avi': ['.avi'],
            'video/mov': ['.mov'],
            'video/wmv': ['.wmv'],
            'application/pdf': ['.pdf'],
            'text/plain': ['.txt']
        }
        
        if detected_mime in expected_extensions and ext not in expected_extensions[detected_mime]:
            logger.warning(f"File extension {ext} doesn't match detected type {detected_mime}")
        
        return detected_mime
    
    def _validate_filename(self, filename: str) -> str:
        """Validate and sanitize filename"""
        if not filename or len(filename) > self.config['max_filename_length']:
            raise ValidationError(f"Filename must be between 1 and {self.config['max_filename_length']} characters")
        
        # Sanitize filename using AthleteUtils
        sanitized_filename = AthleteUtils.sanitize_file_path(filename)
        
        # Additional security checks
        if '..' in sanitized_filename or '/' in sanitized_filename or '\\' in sanitized_filename:
            raise ValidationError("Filename contains invalid path characters")
        
        return sanitized_filename
    
    def _scan_for_malware(self, file_content: bytes, filename: str) -> None:
        """Basic malware scanning with optional VirusTotal integration"""
        if not self.config['scan_for_malware']:
            return
        
        # Basic heuristic checks
        suspicious_patterns = [
            b'MZ',  # Windows executable
            b'PK',  # ZIP archive (could contain malware)
            b'7F454C46',  # ELF executable
            b'CAFEBABE',  # Java class file
        ]
        
        file_hex = file_content[:100].hex().upper()  # Check first 100 bytes
        
        for pattern in suspicious_patterns:
            if pattern.hex().upper() in file_hex:
                logger.warning(f"Suspicious file pattern detected in {filename}")
                # Don't block immediately, but log for review
        
        # Optional VirusTotal scanning if API key is available
        if self.config['virus_total_api_key']:
            try:
                self._scan_with_virus_total(file_content, filename)
            except Exception as e:
                logger.warning(f"VirusTotal scan failed: {e}")
    
    def _scan_with_virus_total(self, file_content: bytes, filename: str) -> None:
        """Scan file with VirusTotal API"""
        if not self.config['virus_total_api_key']:
            return
        
        try:
            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # Check if file has been previously scanned
            headers = {
                'x-apikey': self.config['virus_total_api_key']
            }
            
            url = f"https://www.virustotal.com/vtapi/v2/file/report"
            params = {'apikey': self.config['virus_total_api_key'], 'resource': file_hash}
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('response_code') == 1:
                    positives = result.get('positives', 0)
                    total = result.get('total', 0)
                    
                    if positives > 0:
                        logger.warning(f"VirusTotal detected {positives}/{total} positives for {filename}")
                        # Could implement additional actions here
                        
        except Exception as e:
            logger.error(f"VirusTotal API error: {e}")
            # Don't fail the upload if VirusTotal is unavailable
    
    def _calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
    
    def _check_upload_rate_limit(self, athlete_id: str) -> None:
        """Check upload rate limit for athlete"""
        current_time = datetime.now()
        
        # Clean up old entries
        self._upload_counts = {
            aid: timestamp for aid, timestamp in self._upload_counts.items()
            if (current_time - timestamp).seconds < self.config['upload_rate_limit_window']
        }
        
        # Check current count
        if athlete_id in self._upload_counts:
            raise ValidationError("Upload rate limit exceeded. Please wait before uploading more files.")
        
        # Update count
        self._upload_counts[athlete_id] = current_time
    
    async def upload_media(self, athlete_id: str, file_content: bytes, filename: str, 
                          metadata: Dict[str, Any] = None) -> MediaResponse:
        """Upload media file with comprehensive security validation"""
        try:
            # Validate athlete exists
            athlete = await self.athlete_repository.get_by_id(athlete_id)
            if not athlete:
                raise ResourceNotFoundError(f"Athlete {athlete_id} not found")
            
            # Check upload rate limit
            self._check_upload_rate_limit(athlete_id)
            
            # Validate file size
            self._validate_file_size(file_content)
            
            # Validate and sanitize filename
            sanitized_filename = self._validate_filename(filename)
            
            # Validate file type
            detected_mime = self._validate_file_type(file_content, sanitized_filename)
            
            # Scan for malware
            self._scan_for_malware(file_content, sanitized_filename)
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_content)
            
            # Prepare media document
            media_data = {
                'athlete_id': athlete_id,
                'filename': sanitized_filename,
                'mime_type': detected_mime,
                'file_size': len(file_content),
                'file_hash': file_hash,
                'upload_timestamp': datetime.now(),
                'metadata': metadata or {},
                'status': 'uploaded'
            }
            
            # Create media record
            media_id = await self.media_repository.create(media_data)
            
            # Get created media
            media_doc = await self.media_repository.get_by_id(media_id)
            
            logger.info(f"Media uploaded successfully: {media_id} for athlete {athlete_id}")
            
            return MediaResponse(**media_doc)
            
        except (ValidationError, ResourceNotFoundError, DatabaseError) as e:
            logger.error(f"Media upload failed for athlete {athlete_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during media upload for athlete {athlete_id}: {e}")
            raise DatabaseError(f"Failed to upload media: {str(e)}")
    
    async def bulk_upload_media(self, athlete_id: str, files: List[Dict[str, Any]]) -> List[MediaResponse]:
        """Bulk upload multiple media files"""
        try:
            # Validate athlete exists
            athlete = await self.athlete_repository.get_by_id(athlete_id)
            if not athlete:
                raise ResourceNotFoundError(f"Athlete {athlete_id} not found")
            
            # Check upload rate limit
            self._check_upload_rate_limit(athlete_id)
            
            uploaded_media = []
            
            for file_info in files:
                try:
                    media_response = await self.upload_media(
                        athlete_id=athlete_id,
                        file_content=file_info['content'],
                        filename=file_info['filename'],
                        metadata=file_info.get('metadata')
                    )
                    uploaded_media.append(media_response)
                    
                except Exception as e:
                    logger.error(f"Failed to upload file {file_info.get('filename', 'unknown')}: {e}")
                    # Continue with other files
                    continue
            
            if not uploaded_media:
                raise ValidationError("No files were uploaded successfully")
            
            logger.info(f"Bulk upload completed: {len(uploaded_media)}/{len(files)} files uploaded")
            
            return uploaded_media
            
        except Exception as e:
            logger.error(f"Bulk upload failed for athlete {athlete_id}: {e}")
            raise
    
    async def validate_upload_permissions(self, athlete_id: str, user_id: str) -> bool:
        """Validate that user has permission to upload for this athlete"""
        try:
            # Basic validation - could be enhanced with role-based permissions
            if athlete_id != user_id:
                # Check if user is admin or has special permissions
                # For now, only allow athletes to upload their own media
                return False
            return True
        except Exception as e:
            logger.error(f"Permission validation failed: {e}")
            return False 