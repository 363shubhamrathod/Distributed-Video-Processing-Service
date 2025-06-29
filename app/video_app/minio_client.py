import os
import logging
from typing import List, Optional, Dict
from minio import Minio
from minio.error import S3Error
from django.conf import settings
import uuid

logger = logging.getLogger(__name__)


class MinIOClient:
    """MinIO client for S3-compatible storage operations"""
    
    def __init__(self):
        """Initialize MinIO client with settings"""
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.default_bucket = settings.MINIO_BUCKET_NAME
        self._ensure_buckets_exist()
    
    def _ensure_buckets_exist(self):
        """Ensure required buckets exist"""
        required_buckets = [
            self.default_bucket,
            'processed-videos',
            'extracted-frames',
            'processed-images',
            'temp'
        ]
        
        for bucket_name in required_buckets:
            try:
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
            except S3Error as e:
                logger.error(f"Error creating bucket {bucket_name}: {e}")
    
    def upload_file(self, file_path: str, bucket_name: str = None, 
                   object_name: str = None) -> str:
        """
        Upload a file to MinIO
        
        Args:
            file_path: Local path to the file
            bucket_name: Target bucket name (defaults to default_bucket)
            object_name: Object name in bucket (defaults to filename)
            
        Returns:
            Object key in MinIO
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        bucket_name = bucket_name or self.default_bucket
        object_name = object_name or os.path.basename(file_path)
        
        try:
            # Generate unique object name if not provided
            if object_name == os.path.basename(file_path):
                name, ext = os.path.splitext(object_name)
                object_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            
            # Upload file
            self.client.fput_object(
                bucket_name, object_name, file_path
            )
            
            logger.info(f"Uploaded {file_path} to {bucket_name}/{object_name}")
            return f"{bucket_name}/{object_name}"
            
        except S3Error as e:
            logger.error(f"Error uploading {file_path}: {e}")
            raise
    
    def download_file(self, bucket_name: str, object_name: str, 
                     file_path: str) -> bool:
        """
        Download a file from MinIO
        
        Args:
            bucket_name: Source bucket name
            object_name: Object name in bucket
            file_path: Local path to save the file
            
        Returns:
            True if successful
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Download file
            self.client.fget_object(bucket_name, object_name, file_path)
            
            logger.info(f"Downloaded {bucket_name}/{object_name} to {file_path}")
            return True
            
        except S3Error as e:
            logger.error(f"Error downloading {bucket_name}/{object_name}: {e}")
            return False
    
    def get_file_url(self, bucket_name: str, object_name: str, 
                    expires: int = 3600) -> str:
        """
        Get presigned URL for file download
        
        Args:
            bucket_name: Bucket name
            object_name: Object name
            expires: URL expiration time in seconds
            
        Returns:
            Presigned URL
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name, object_name, expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Error generating URL for {bucket_name}/{object_name}: {e}")
            return None
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """
        Delete a file from MinIO
        
        Args:
            bucket_name: Bucket name
            object_name: Object name
            
        Returns:
            True if successful
        """
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted {bucket_name}/{object_name}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting {bucket_name}/{object_name}: {e}")
            return False
    
    def list_files(self, bucket_name: str = None, prefix: str = "") -> List[Dict]:
        """
        List files in a bucket
        
        Args:
            bucket_name: Bucket name (defaults to default_bucket)
            prefix: Object name prefix filter
            
        Returns:
            List of file information dictionaries
        """
        bucket_name = bucket_name or self.default_bucket
        files = []
        
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            
            for obj in objects:
                files.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag
                })
            
            return files
            
        except S3Error as e:
            logger.error(f"Error listing files in {bucket_name}: {e}")
            return []
    
    def list_buckets(self) -> List[str]:
        """
        List all buckets
        
        Returns:
            List of bucket names
        """
        try:
            buckets = self.client.list_buckets()
            return [bucket.name for bucket in buckets]
        except S3Error as e:
            logger.error(f"Error listing buckets: {e}")
            return []
    
    def bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if bucket exists
        
        Args:
            bucket_name: Bucket name to check
            
        Returns:
            True if bucket exists
        """
        try:
            return self.client.bucket_exists(bucket_name)
        except S3Error as e:
            logger.error(f"Error checking bucket {bucket_name}: {e}")
            return False
    
    def get_bucket_size(self, bucket_name: str) -> int:
        """
        Get total size of bucket in bytes
        
        Args:
            bucket_name: Bucket name
            
        Returns:
            Total size in bytes
        """
        try:
            objects = self.client.list_objects(bucket_name, recursive=True)
            total_size = sum(obj.size for obj in objects)
            return total_size
        except S3Error as e:
            logger.error(f"Error getting size for bucket {bucket_name}: {e}")
            return 0
    
    def copy_file(self, source_bucket: str, source_object: str,
                  dest_bucket: str, dest_object: str) -> bool:
        """
        Copy a file within MinIO
        
        Args:
            source_bucket: Source bucket name
            source_object: Source object name
            dest_bucket: Destination bucket name
            dest_object: Destination object name
            
        Returns:
            True if successful
        """
        try:
            self.client.copy_object(
                dest_bucket, dest_object,
                f"{source_bucket}/{source_object}"
            )
            logger.info(f"Copied {source_bucket}/{source_object} to {dest_bucket}/{dest_object}")
            return True
        except S3Error as e:
            logger.error(f"Error copying {source_bucket}/{source_object}: {e}")
            return False
    
    def upload_video_metadata(self, video_id: str, metadata: Dict) -> str:
        """
        Upload video metadata as JSON
        
        Args:
            video_id: Video ID
            metadata: Metadata dictionary
            
        Returns:
            Object key
        """
        import json
        import tempfile
        
        # Create temporary file with metadata
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metadata, f, indent=2)
            temp_path = f.name
        
        try:
            object_name = f"metadata/{video_id}.json"
            return self.upload_file(temp_path, self.default_bucket, object_name)
        finally:
            os.unlink(temp_path)
    
    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """
        Get video metadata from MinIO
        
        Args:
            video_id: Video ID
            
        Returns:
            Metadata dictionary or None
        """
        import json
        import tempfile
        
        object_name = f"metadata/{video_id}.json"
        
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_path = f.name
            
            # Download metadata file
            if self.download_file(self.default_bucket, object_name, temp_path):
                with open(temp_path, 'r') as f:
                    metadata = json.load(f)
                return metadata
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting metadata for video {video_id}: {e}")
            return None
        finally:
            if 'temp_path' in locals():
                os.unlink(temp_path) 