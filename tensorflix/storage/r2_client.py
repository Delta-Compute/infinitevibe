"""
R2 Storage client for handling video submissions.
"""
from __future__ import annotations

import os
from typing import Optional, BinaryIO
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from loguru import logger

from tensorflix.config import CONFIG


class R2StorageClient:
    """Client for interacting with Cloudflare R2 storage."""
    
    def __init__(self):
        """Initialize R2 client with credentials from config."""
        if not all([CONFIG.r2_account_id, CONFIG.r2_access_key_id, CONFIG.r2_secret_access_key]):
            raise ValueError("R2 credentials not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
        
        self.endpoint_url = f"https://{CONFIG.r2_account_id}.r2.cloudflarestorage.com"
        self.bucket_name = CONFIG.r2_bucket_name
        
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=CONFIG.r2_access_key_id,
            aws_secret_access_key=CONFIG.r2_secret_access_key,
            region_name='auto'
        )
        
        logger.info(f"R2 client initialized for bucket: {self.bucket_name}")
    
    def validate_r2_link(self, r2_link: str) -> bool:
        """
        Validate that an R2 link exists and is accessible.
        
        Args:
            r2_link: The R2 storage link to validate
            
        Returns:
            True if the object exists, False otherwise
        """
        try:
            # Extract object key from R2 link
            # Expected format: https://bucket.r2.dev/path/to/video.mp4
            # or https://custom-domain.com/path/to/video.mp4
            key = self._extract_key_from_url(r2_link)
            if not key:
                logger.warning(f"Invalid R2 link format: {r2_link}")
                return False
            
            # Check if object exists
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"R2 object validated: {key}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.warning(f"R2 object not found: {r2_link}")
            else:
                logger.error(f"R2 validation error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating R2 link: {e}")
            return False
    
    def get_object_metadata(self, r2_link: str) -> Optional[dict]:
        """
        Get metadata for an R2 object.
        
        Args:
            r2_link: The R2 storage link
            
        Returns:
            Dictionary with object metadata or None if not found
        """
        try:
            key = self._extract_key_from_url(r2_link)
            if not key:
                return None
            
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            
            return {
                'size': response['ContentLength'],
                'content_type': response.get('ContentType', 'unknown'),
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'metadata': response.get('Metadata', {})
            }
        except Exception as e:
            logger.error(f"Error getting R2 object metadata: {e}")
            return None
    
    def generate_presigned_url(self, r2_link: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for temporary access to an R2 object.
        
        Args:
            r2_link: The R2 storage link
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL or None if generation failed
        """
        try:
            key = self._extract_key_from_url(r2_link)
            if not key:
                return None
            
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for {key}, expires in {expiration}s")
            return url
            
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def download_video(self, r2_link: str, local_path: str) -> bool:
        """
        Download a video from R2 to local storage.
        
        Args:
            r2_link: The R2 storage link
            local_path: Local file path to save the video
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            key = self._extract_key_from_url(r2_link)
            if not key:
                return False
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            self.client.download_file(self.bucket_name, key, local_path)
            logger.info(f"Downloaded video from R2: {key} -> {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from R2: {e}")
            return False
    
    def upload_video(self, local_path: str, r2_key: str, metadata: Optional[dict] = None) -> Optional[str]:
        """
        Upload a video to R2 storage.
        
        Args:
            local_path: Local file path of the video
            r2_key: Key (path) in R2 bucket
            metadata: Optional metadata to attach to the object
            
        Returns:
            R2 URL of the uploaded object or None if upload failed
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Determine content type
            if local_path.endswith('.mp4'):
                extra_args['ContentType'] = 'video/mp4'
            elif local_path.endswith('.webm'):
                extra_args['ContentType'] = 'video/webm'
            
            # Upload file
            self.client.upload_file(local_path, self.bucket_name, r2_key, ExtraArgs=extra_args)
            
            # Generate public URL
            if CONFIG.r2_public_url:
                url = f"{CONFIG.r2_public_url}/{r2_key}"
            else:
                url = f"{self.endpoint_url}/{self.bucket_name}/{r2_key}"
            
            logger.info(f"Uploaded video to R2: {local_path} -> {r2_key}")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading to R2: {e}")
            return None
    
    def _extract_key_from_url(self, r2_link: str) -> Optional[str]:
        """Extract the object key from an R2 URL."""
        try:
            # Remove protocol
            if r2_link.startswith('https://'):
                r2_link = r2_link[8:]
            elif r2_link.startswith('http://'):
                r2_link = r2_link[7:]
            
            # Extract key based on URL format
            if CONFIG.r2_public_url and CONFIG.r2_public_url in r2_link:
                # Custom domain format
                key = r2_link.replace(CONFIG.r2_public_url.replace('https://', '').replace('http://', '') + '/', '')
            elif f"{self.bucket_name}.r2" in r2_link:
                # Standard R2 format
                parts = r2_link.split('/', 1)
                if len(parts) > 1:
                    key = parts[1]
                else:
                    return None
            elif '/' in r2_link:
                # Try to extract after first slash
                parts = r2_link.split('/', 1)
                if len(parts) > 1:
                    key = parts[1]
                else:
                    return None
            else:
                return None
            
            return key
            
        except Exception as e:
            logger.error(f"Error extracting key from URL {r2_link}: {e}")
            return None