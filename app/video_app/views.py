from rest_framework import generics, status, views
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from .models import Video, DetectedObject, ProcessedFrame, ProcessingTask
from .serializers import (
    VideoSerializer, VideoUploadSerializer, VideoDetailSerializer,
    DetectedObjectSerializer, ProcessedFrameSerializer, ProcessingTaskSerializer
)
from .tasks import process_video_task

class VideoUploadView(generics.CreateAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoUploadSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        video = serializer.save(uploaded_by=self.request.user if self.request.user.is_authenticated else None)
        # Trigger background processing
        process_video_task.delay(str(video.id))

class VideoListView(generics.ListAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class VideoDetailView(generics.RetrieveAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

class ProcessingTaskListView(generics.ListAPIView):
    queryset = ProcessingTask.objects.all()
    serializer_class = ProcessingTaskSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        video_id = self.request.query_params.get('video_id')
        if video_id:
            return self.queryset.filter(video_id=video_id)
        return self.queryset

class DetectedObjectListView(generics.ListAPIView):
    queryset = DetectedObject.objects.all()
    serializer_class = DetectedObjectSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        video_id = self.request.query_params.get('video_id')
        if video_id:
            return self.queryset.filter(video_id=video_id)
        return self.queryset

class ProcessedFrameListView(generics.ListAPIView):
    queryset = ProcessedFrame.objects.all()
    serializer_class = ProcessedFrameSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        video_id = self.request.query_params.get('video_id')
        if video_id:
            return self.queryset.filter(video_id=video_id)
        return self.queryset 