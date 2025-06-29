# Distributed Video Processing Service

A microservice for distributed video processing using Django, Celery, YOLO, OpenCV, MinIO, and Redis.

## Features
- Video upload via REST API
- Background video processing with YOLO object detection
- Processed videos/images stored in MinIO (S3-compatible)
- Redis for background task queue (Celery)
- Optional ElasticMQ for SQS emulation
- Docker Compose for local development

## Project Structure
```
video-processing-service/
│
├── app/
│   ├── manage.py
│   ├── video_processor/
│   ├── video_app/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env
├── README.md
```

## Setup
1. Clone the repository
2. Create a Python virtual environment and install requirements:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Configure environment variables in `.env` (see example below)
4. Run database migrations:
   ```bash
   cd app
   python manage.py migrate
   ```
5. Start services with Docker Compose:
   ```bash
   docker-compose up --build
   ```

## Example .env
```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=video_processor
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=postgres
DB_PORT=5432
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=video-processing
MINIO_SECURE=False
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
YOLO_MODEL_PATH=yolov8n.pt
YOLO_CONFIDENCE_THRESHOLD=0.5
```

## API Endpoints
- `POST /api/videos/upload/` — Upload a video
- `GET /api/videos/` — List videos
- `GET /api/videos/<uuid>/` — Video details
- `GET /api/tasks/` — List processing tasks
- `GET /api/detected-objects/` — List detected objects
- `GET /api/processed-frames/` — List processed frames

## License
MIT 