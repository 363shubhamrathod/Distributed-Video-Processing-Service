from django.db import models
from django.contrib.auth.models import User
import uuid
import os


def video_upload_path(instance, filename):
    """Generate upload path for video files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('videos', filename)


def processed_video_upload_path(instance, filename):
    """Generate upload path for processed video files"""
    ext = filename.split('.')[-1]
    filename = f"processed_{uuid.uuid4()}.{ext}"
    return os.path.join('processed_videos', filename)


def image_upload_path(instance, filename):
    """Generate upload path for processed images"""
    ext = filename.split('.')[-1]
    filename = f"frame_{uuid.uuid4()}.{ext}"
    return os.path.join('processed_images', filename)


class Video(models.Model):
    """Model for uploaded videos"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_file = models.FileField(upload_to=video_upload_path)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Video metadata
    duration = models.FloatField(null=True, blank=True)  # in seconds
    frame_count = models.IntegerField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    resolution = models.CharField(max_length=20, blank=True)  # e.g., "1920x1080"
    file_size = models.BigIntegerField(null=True, blank=True)  # in bytes
    
    # MinIO storage info
    minio_bucket = models.CharField(max_length=100, blank=True)
    minio_key = models.CharField(max_length=500, blank=True)
    processed_minio_key = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} ({self.status})"
    
    @property
    def filename(self):
        return os.path.basename(self.video_file.name)


class DetectedObject(models.Model):
    """Model for detected objects in video frames"""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='detected_objects')
    frame_number = models.IntegerField()
    object_class = models.CharField(max_length=100)
    confidence = models.FloatField()
    bbox_x = models.FloatField()
    bbox_y = models.FloatField()
    bbox_width = models.FloatField()
    bbox_height = models.FloatField()
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['frame_number', '-confidence']
    
    def __str__(self):
        return f"{self.object_class} (frame {self.frame_number}, conf: {self.confidence:.2f})"


class ProcessedFrame(models.Model):
    """Model for processed video frames with object detection"""
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='processed_frames')
    frame_number = models.IntegerField()
    frame_image = models.ImageField(upload_to=image_upload_path, null=True, blank=True)
    objects_detected = models.IntegerField(default=0)
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    minio_key = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['frame_number']
        unique_together = ['video', 'frame_number']
    
    def __str__(self):
        return f"Frame {self.frame_number} of {self.video.title}"


class ProcessingTask(models.Model):
    """Model for tracking Celery tasks"""
    TASK_TYPES = [
        ('video_processing', 'Video Processing'),
        ('object_detection', 'Object Detection'),
        ('frame_extraction', 'Frame Extraction'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='processing_tasks')
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    celery_task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    progress = models.IntegerField(default=0)  # 0-100
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task_type} task for {self.video.title} ({self.status})" 