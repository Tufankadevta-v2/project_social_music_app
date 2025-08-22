# Social Task Management Backend

A Django REST API backend for a social task management application that allows friends to connect, create tasks, and compete with each other.

## Features

- Phone number-based authentication with OTP verification
- Contact-based friend discovery (WhatsApp-style privacy)
- Personal and shared task management
- Social feed and activity tracking
- Gamification with points and achievements
- Real-time notifications via WebSockets
- Comprehensive privacy controls

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis

### Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

5. Update the `.env` file with your configuration

6. Run migrations:
   ```bash
   python manage.py migrate
   ```

7. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

8. Start the development server:
   ```bash
   python manage.py runserver
   ```

### Running with Celery

For background tasks and real-time features:

1. Start Redis server
2. Start Celery worker:
   ```bash
   celery -A social_task_backend worker -l info
   ```

3. Start Celery beat (for periodic tasks):
   ```bash
   celery -A social_task_backend beat -l info
   ```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/api/docs/
- API Schema: http://localhost:8000/api/schema/

## Project Structure

```
social_task_backend/
├── accounts/          # User authentication and profiles
├── friends/           # Friend connections and contact syncing
├── tasks/             # Task management and shared tasks
├── social/            # Activity feeds and gamification
├── notifications/     # Real-time notifications
├── social_task_backend/
│   ├── settings/      # Environment-specific settings
│   ├── celery.py      # Celery configuration
│   └── ...
├── static/            # Static files
├── media/             # User uploaded files
├── templates/         # Django templates
└── logs/              # Application logs
```

## Environment Variables

See `.env.example` for all required environment variables.

## Development

- Use `development.py` settings for local development
- Use `production.py` settings for production deployment
- All apps follow Django REST Framework conventions
- WebSocket support via Django Channels for real-time features