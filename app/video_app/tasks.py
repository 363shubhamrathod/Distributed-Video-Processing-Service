import os
import time
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import Video, DetectedObject, ProcessedFrame, ProcessingTask
from .yolo_processor import YOLOProcessor
from .minio_client import MinIOClient

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_video_task(self, video_id: str):
    """
    Celery task to process video with YOLO object detection
    
    Args:
        video_id: UUID of the video to process
    """
    try:
        # Get video object
        video = Video.objects.get(id=video_id)
        
        # Create processing task record
        task_record = ProcessingTask.objects.create(
            video=video,
            task_type='video_processing',
            celery_task_id=self.request.id,
            status='running',
            started_at=timezone.now()
        )
        
        # Update video status
        video.status = 'processing'
        video.processing_started_at = timezone.now()
        video.save()
        
        logger.info(f"Starting video processing for {video.title} (ID: {video_id})")
        
        # Initialize YOLO processor
        processor = YOLOProcessor()
        
        # Get video metadata
        video_path = video.video_file.path
        metadata = processor.get_video_metadata(video_path)
        
        # Update video with metadata
        video.duration = metadata['duration']
        video.frame_count = metadata['frame_count']
        video.fps = metadata['fps']
        video.resolution = metadata['resolution']
        video.file_size = metadata['file_size']
        video.save()
        
        # Create output directory for processed video
        output_dir = os.path.join(settings.MEDIA_ROOT, 'processed_videos')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output video path
        filename = os.path.basename(video_path)
        name, ext = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"processed_{name}{ext}")
        
        # Process video with YOLO
        results = processor.process_video(
            video_path=video_path,
            output_path=output_path,
            frame_interval=1  # Process every frame
        )
        
        # Save detected objects to database
        for frame_result in results['detections']:
            frame_number = frame_result['frame_number']
            
            # Create processed frame record
            processed_frame = ProcessedFrame.objects.create(
                video=video,
                frame_number=frame_number,
                objects_detected=frame_result['object_count'],
                processing_time=frame_result['processing_time']
            )
            
            # Save detected objects
            for obj in frame_result['objects']:
                DetectedObject.objects.create(
                    video=video,
                    frame_number=frame_number,
                    object_class=obj['class'],
                    confidence=obj['confidence'],
                    bbox_x=obj['bbox']['x'],
                    bbox_y=obj['bbox']['y'],
                    bbox_width=obj['bbox']['width'],
                    bbox_height=obj['bbox']['height']
                )
        
        # Upload processed video to MinIO
        minio_client = MinIOClient()
        if os.path.exists(output_path):
            minio_key = minio_client.upload_file(output_path, 'processed-videos')
            video.processed_minio_key = minio_key
            video.save()
        
        # Update task status
        task_record.status = 'completed'
        task_record.completed_at = timezone.now()
        task_record.progress = 100
        task_record.save()
        
        # Update video status
        video.status = 'completed'
        video.processing_completed_at = timezone.now()
        video.save()
        
        logger.info(f"Video processing completed for {video.title}")
        
        return {
            'status': 'success',
            'video_id': video_id,
            'processed_frames': results['processed_frames'],
            'total_detections': sum(len(d['objects']) for d in results['detections']),
            'processing_time': results['processing_time']
        }
        
    except Video.DoesNotExist:
        logger.error(f"Video with ID {video_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {str(e)}")
        
        # Update task status
        if 'task_record' in locals():
            task_record.status = 'failed'
            task_record.completed_at = timezone.now()
            task_record.error_message = str(e)
            task_record.save()
        
        # Update video status
        if 'video' in locals():
            video.status = 'failed'
            video.error_message = str(e)
            video.save()
        
        raise


@shared_task(bind=True)
def extract_frames_task(self, video_id: str, frame_interval: int = 30):
    """
    Celery task to extract frames from video
    
    Args:
        video_id: UUID of the video
        frame_interval: Extract every Nth frame
    """
    try:
        video = Video.objects.get(id=video_id)
        
        # Create processing task record
        task_record = ProcessingTask.objects.create(
            video=video,
            task_type='frame_extraction',
            celery_task_id=self.request.id,
            status='running',
            started_at=timezone.now()
        )
        
        # Initialize processor
        processor = YOLOProcessor()
        
        # Create output directory
        output_dir = os.path.join(settings.MEDIA_ROOT, 'extracted_frames', str(video_id))
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract frames
        frame_paths = processor.extract_frames(
            video_path=video.video_file.path,
            output_dir=output_dir,
            frame_interval=frame_interval
        )
        
        # Upload frames to MinIO
        minio_client = MinIOClient()
        uploaded_keys = []
        
        for frame_path in frame_paths:
            minio_key = minio_client.upload_file(frame_path, 'extracted-frames')
            uploaded_keys.append(minio_key)
        
        # Update task status
        task_record.status = 'completed'
        task_record.completed_at = timezone.now()
        task_record.progress = 100
        task_record.save()
        
        logger.info(f"Frame extraction completed for {video.title}: {len(frame_paths)} frames")
        
        return {
            'status': 'success',
            'video_id': video_id,
            'extracted_frames': len(frame_paths),
            'minio_keys': uploaded_keys
        }
        
    except Video.DoesNotExist:
        logger.error(f"Video with ID {video_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error extracting frames from video {video_id}: {str(e)}")
        
        if 'task_record' in locals():
            task_record.status = 'failed'
            task_record.completed_at = timezone.now()
            task_record.error_message = str(e)
            task_record.save()
        
        raise


@shared_task(bind=True)
def detect_objects_in_frames_task(self, video_id: str, frame_numbers: list = None):
    """
    Celery task to detect objects in specific frames
    
    Args:
        video_id: UUID of the video
        frame_numbers: List of frame numbers to process (None for all)
    """
    try:
        video = Video.objects.get(id=video_id)
        
        # Create processing task record
        task_record = ProcessingTask.objects.create(
            video=video,
            task_type='object_detection',
            celery_task_id=self.request.id,
            status='running',
            started_at=timezone.now()
        )
        
        # Initialize processor
        processor = YOLOProcessor()
        
        # Get video metadata
        metadata = processor.get_video_metadata(video.video_file.path)
        total_frames = metadata['frame_count']
        
        # Determine frames to process
        if frame_numbers is None:
            # Process every 30th frame by default
            frame_numbers = list(range(0, total_frames, 30))
        
        cap = cv2.VideoCapture(video.video_file.path)
        detections_count = 0
        
        try:
            for i, frame_number in enumerate(frame_numbers):
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                ret, frame = cap.read()
                
                if ret:
                    # Process frame
                    frame_result = processor._process_frame(frame, frame_number)
                    
                    # Save detected objects
                    for obj in frame_result['objects']:
                        DetectedObject.objects.create(
                            video=video,
                            frame_number=frame_number,
                            object_class=obj['class'],
                            confidence=obj['confidence'],
                            bbox_x=obj['bbox']['x'],
                            bbox_y=obj['bbox']['y'],
                            bbox_width=obj['bbox']['width'],
                            bbox_height=obj['bbox']['height']
                        )
                        detections_count += 1
                    
                    # Update progress
                    progress = int((i + 1) / len(frame_numbers) * 100)
                    task_record.progress = progress
                    task_record.save()
        
        finally:
            cap.release()
        
        # Update task status
        task_record.status = 'completed'
        task_record.completed_at = timezone.now()
        task_record.progress = 100
        task_record.save()
        
        logger.info(f"Object detection completed for {video.title}: {detections_count} objects detected")
        
        return {
            'status': 'success',
            'video_id': video_id,
            'processed_frames': len(frame_numbers),
            'detections_count': detections_count
        }
        
    except Video.DoesNotExist:
        logger.error(f"Video with ID {video_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error detecting objects in video {video_id}: {str(e)}")
        
        if 'task_record' in locals():
            task_record.status = 'failed'
            task_record.completed_at = timezone.now()
            task_record.error_message = str(e)
            task_record.save()
        
        raise


@shared_task
def cleanup_temp_files_task():
    """Clean up temporary files older than 24 hours"""
    import shutil
    from datetime import timedelta
    
    temp_dirs = [
        os.path.join(settings.MEDIA_ROOT, 'extracted_frames'),
        os.path.join(settings.MEDIA_ROOT, 'temp')
    ]
    
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    # Check if directory is older than 24 hours
                    dir_time = timezone.now() - timedelta(hours=1)  # Placeholder
                    if dir_time < cutoff_time:
                        shutil.rmtree(item_path)
                        logger.info(f"Cleaned up temporary directory: {item_path}")


@shared_task
def health_check_task():
    """Health check task to verify system components"""
    try:
        # Check YOLO model
        processor = YOLOProcessor()
        logger.info("YOLO model health check passed")
        
        # Check MinIO connection
        minio_client = MinIOClient()
        buckets = minio_client.list_buckets()
        logger.info(f"MinIO health check passed. Available buckets: {len(buckets)}")
        
        return {
            'status': 'healthy',
            'yolo_model': 'ok',
            'minio_connection': 'ok',
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        } 