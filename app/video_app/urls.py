from django.urls import path
from . import views

urlpatterns = [
    path('videos/', views.VideoListView.as_view(), name='video-list'),
    path('videos/upload/', views.VideoUploadView.as_view(), name='video-upload'),
    path('videos/<uuid:pk>/', views.VideoDetailView.as_view(), name='video-detail'),
    path('tasks/', views.ProcessingTaskListView.as_view(), name='task-list'),
    path('detected-objects/', views.DetectedObjectListView.as_view(), name='detected-object-list'),
    path('processed-frames/', views.ProcessedFrameListView.as_view(), name='processed-frame-list'),
] 