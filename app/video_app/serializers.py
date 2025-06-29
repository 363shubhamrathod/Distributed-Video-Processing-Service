from rest_framework import serializers
from .models import Video, DetectedObject, ProcessedFrame, ProcessingTask


class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video model"""
    uploaded_by = serializers.ReadOnlyField(source='uploaded_by.username')
    filename = serializers.ReadOnlyField()
    file_size_mb = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description', 'video_file', 'uploaded_by', 
            'uploaded_at', 'status', 'processing_started_at', 'processing_completed_at',
            'error_message', 'duration', 'frame_count', 'fps', 'resolution', 
            'file_size', 'filename', 'file_size_mb', 'duration_formatted',
            'minio_bucket', 'minio_key', 'processed_minio_key'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'uploaded_at', 'status', 'processing_started_at',
            'processing_completed_at', 'error_message', 'duration', 'frame_count',
            'fps', 'resolution', 'file_size', 'filename', 'minio_bucket', 
            'minio_key', 'processed_minio_key'
        ]
    
    def get_file_size_mb(self, obj):
        """Convert file size to MB"""
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return None
    
    def get_duration_formatted(self, obj):
        """Format duration as MM:SS"""
        if obj.duration:
            minutes = int(obj.duration // 60)
            seconds = int(obj.duration % 60)
            return f"{minutes:02d}:{seconds:02d}"
        return None


class VideoUploadSerializer(serializers.ModelSerializer):
    """Serializer for video upload"""
    class Meta:
        model = Video
        fields = ['title', 'description', 'video_file']
    
    def validate_video_file(self, value):
        """Validate uploaded video file"""
        import os
        from django.conf import settings
        
        # Check file size
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f"File size must be under {settings.MAX_UPLOAD_SIZE / (1024*1024*1024):.1f}GB"
            )
        
        # Check file extension
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type not supported. Allowed types: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
            )
        
        return value


class DetectedObjectSerializer(serializers.ModelSerializer):
    """Serializer for DetectedObject model"""
    class Meta:
        model = DetectedObject
        fields = [
            'id', 'video', 'frame_number', 'object_class', 'confidence',
            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height', 'detected_at'
        ]
        read_only_fields = ['id', 'detected_at']


class ProcessedFrameSerializer(serializers.ModelSerializer):
    """Serializer for ProcessedFrame model"""
    class Meta:
        model = ProcessedFrame
        fields = [
            'id', 'video', 'frame_number', 'frame_image', 'objects_detected',
            'processing_time', 'minio_key'
        ]
        read_only_fields = ['id', 'objects_detected', 'processing_time', 'minio_key']


class ProcessingTaskSerializer(serializers.ModelSerializer):
    """Serializer for ProcessingTask model"""
    video_title = serializers.ReadOnlyField(source='video.title')
    
    class Meta:
        model = ProcessingTask
        fields = [
            'id', 'video', 'video_title', 'task_type', 'celery_task_id',
            'status', 'created_at', 'started_at', 'completed_at',
            'error_message', 'progress'
        ]
        read_only_fields = [
            'id', 'celery_task_id', 'status', 'created_at', 'started_at',
            'completed_at', 'error_message', 'progress'
        ]


class VideoDetailSerializer(VideoSerializer):
    """Detailed serializer for Video model with related objects"""
    detected_objects = DetectedObjectSerializer(many=True, read_only=True)
    processed_frames = ProcessedFrameSerializer(many=True, read_only=True)
    processing_tasks = ProcessingTaskSerializer(many=True, read_only=True)
    
    class Meta(VideoSerializer.Meta):
        fields = VideoSerializer.Meta.fields + [
            'detected_objects', 'processed_frames', 'processing_tasks'
        ]


class ObjectDetectionResultSerializer(serializers.Serializer):
    """Serializer for object detection results"""
    frame_number = serializers.IntegerField()
    objects = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of detected objects with bbox and confidence"
    )
    processing_time = serializers.FloatField(help_text="Processing time in seconds")


class ProcessingStatusSerializer(serializers.Serializer):
    """Serializer for processing status updates"""
    video_id = serializers.UUIDField()
    status = serializers.CharField()
    progress = serializers.IntegerField(min_value=0, max_value=100)
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False) 