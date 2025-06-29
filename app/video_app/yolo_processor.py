import cv2
import numpy as np
import os
import time
from typing import List, Dict, Tuple, Optional
from ultralytics import YOLO
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class YOLOProcessor:
    """YOLO-based object detection processor for videos"""
    
    def __init__(self, model_path: str = None, confidence_threshold: float = None):
        """
        Initialize YOLO processor
        
        Args:
            model_path: Path to YOLO model file
            confidence_threshold: Minimum confidence for detections
        """
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.confidence_threshold = confidence_threshold or settings.YOLO_CONFIDENCE_THRESHOLD
        
        # Load YOLO model
        try:
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def process_video(self, video_path: str, output_path: str = None, 
                     frame_interval: int = 1) -> Dict:
        """
        Process video and detect objects
        
        Args:
            video_path: Path to input video file
            output_path: Path to save processed video (optional)
            frame_interval: Process every Nth frame
            
        Returns:
            Dictionary with processing results
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Setup video writer if output path is provided
        video_writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        results = {
            'total_frames': frame_count,
            'processed_frames': 0,
            'detections': [],
            'processing_time': 0,
            'video_metadata': {
                'fps': fps,
                'frame_count': frame_count,
                'width': width,
                'height': height,
                'duration': frame_count / fps if fps > 0 else 0
            }
        }
        
        start_time = time.time()
        frame_number = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process every Nth frame
                if frame_number % frame_interval == 0:
                    frame_results = self._process_frame(frame, frame_number)
                    results['detections'].append(frame_results)
                    results['processed_frames'] += 1
                    
                    # Draw bounding boxes on frame
                    if output_path and frame_results['objects']:
                        frame = self._draw_detections(frame, frame_results['objects'])
                
                # Write frame to output video
                if video_writer:
                    video_writer.write(frame)
                
                frame_number += 1
                
                # Log progress
                if frame_number % 100 == 0:
                    logger.info(f"Processed {frame_number}/{frame_count} frames")
        
        finally:
            cap.release()
            if video_writer:
                video_writer.release()
        
        results['processing_time'] = time.time() - start_time
        logger.info(f"Video processing completed in {results['processing_time']:.2f} seconds")
        
        return results
    
    def _process_frame(self, frame: np.ndarray, frame_number: int) -> Dict:
        """
        Process a single frame for object detection
        
        Args:
            frame: Input frame as numpy array
            frame_number: Frame number for tracking
            
        Returns:
            Dictionary with detection results
        """
        start_time = time.time()
        
        # Run YOLO detection
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        
        # Extract detection results
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    # Get class and confidence
                    cls = int(box.cls[0].cpu().numpy())
                    conf = float(box.conf[0].cpu().numpy())
                    
                    # Get class name
                    class_name = self.model.names[cls]
                    
                    detections.append({
                        'class': class_name,
                        'confidence': conf,
                        'bbox': {
                            'x': float(x1),
                            'y': float(y1),
                            'width': float(x2 - x1),
                            'height': float(y2 - y1)
                        }
                    })
        
        processing_time = time.time() - start_time
        
        return {
            'frame_number': frame_number,
            'objects': detections,
            'processing_time': processing_time,
            'object_count': len(detections)
        }
    
    def _draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame
        
        Args:
            frame: Input frame
            detections: List of detection dictionaries
            
        Returns:
            Frame with drawn detections
        """
        for detection in detections:
            bbox = detection['bbox']
            x, y, w, h = int(bbox['x']), int(bbox['y']), int(bbox['width']), int(bbox['height'])
            
            # Draw bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Draw label
            label = f"{detection['class']} {detection['confidence']:.2f}"
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return frame
    
    def extract_frames(self, video_path: str, output_dir: str, 
                      frame_interval: int = 30) -> List[str]:
        """
        Extract frames from video at specified intervals
        
        Args:
            video_path: Path to input video
            output_dir: Directory to save extracted frames
            frame_interval: Extract every Nth frame
            
        Returns:
            List of paths to extracted frame images
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        frame_paths = []
        frame_number = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_number % frame_interval == 0:
                    frame_path = os.path.join(output_dir, f"frame_{frame_number:06d}.jpg")
                    cv2.imwrite(frame_path, frame)
                    frame_paths.append(frame_path)
                
                frame_number += 1
        
        finally:
            cap.release()
        
        logger.info(f"Extracted {len(frame_paths)} frames to {output_dir}")
        return frame_paths
    
    def get_video_metadata(self, video_path: str) -> Dict:
        """
        Get video metadata without processing
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video metadata
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            return {
                'fps': fps,
                'frame_count': frame_count,
                'width': width,
                'height': height,
                'duration': duration,
                'resolution': f"{width}x{height}",
                'file_size': os.path.getsize(video_path)
            }
        finally:
            cap.release() 