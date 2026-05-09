# Devryze Chatbot - Django Edition

An AI-powered chatbot application built with Django and LangChain, featuring a modern REST API and interactive web interface.

## Migration from Gradio to Django

This project has been converted from Gradio to Django for better scalability, API flexibility, and production-readiness.

### Key Changes

- **UI Framework**: Gradio → Django (with custom HTML/CSS template)
- **API**: Implicit Gradio interface → Explicit REST API endpoints
- **Backend**: Gradio app server → Django development/production server
- **Database**: SQLite with Django ORM support for chat histories

## Project Structure

```
influxai/
├── app.py                    # Django development server launcher
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── config/                   # Django project configuration
│   ├── __init__.py
│   ├── settings.py          # Django settings
│   ├── urls.py              # Main URL routing
│   └── wsgi.py              # WSGI configuration
├── chatbot/                 # Chatbot Django app
│   ├── __init__.py
│   ├── admin.py             # Django admin configuration
│   ├── apps.py              # App configuration
│   ├── chain.py             # LangChain logic & LLM setup
│   ├── models.py            # Database models
│   ├── urls.py              # App URL routing
│   └── views.py             # API views & handlers
├── templates/               # HTML templates
│   └── index.html           # Chat UI template
└── static/                  # Static files (CSS, JS, images)
```

## Features

- **RAG (Retrieval Augmented Generation)**: Uses FAISS vector database for context-aware responses
- **Multi-user Sessions**: SQLite-based chat history with per-user session management
- **REST API**: `/api/chatbot/chat/` endpoint for programmatic access
- **Persistent History**: All conversations stored in SQLite database
- **Modern UI**: Responsive web interface with real-time chat experience
- **LLM Integration**: Uses HuggingFace endpoints (configurable model)

## Setup & Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set HuggingFace API Token

```bash
# Windows PowerShell
$env:HUGGINGFACE_TOKEN = "your_token_here"

# Or set it permanently in your system environment variables
```

### 3. Ensure PDF Files Exist

Place your PDF files in the working directory:
- `devryze chatbot dataset.pdf`
- `data5.pdf`

The chatbot will still work without PDFs (using the LLM directly), but will have better context with them.

## Running the Application

### Start the Django Development Server

```bash
python app.py
```

or

```bash
python manage.py runserver 0.0.0.0:8000
```

The application will be available at: **http://localhost:8000**

### Access the Chat Interface

- **Web UI**: http://localhost:8000
- **API Endpoint**: POST http://localhost:8000/api/chatbot/chat/
- **Health Check**: GET http://localhost:8000/api/chatbot/health/

## API Usage

### Chat Endpoint

**Endpoint**: `POST /api/chatbot/chat/`

**Request Body**:
```json
{
  "message": "What is Devryze?",
  "user_id": "optional_user_identifier"
}
```

**Response**:
```json
{
  "user_message": "What is Devryze?",
  "bot_response": "Devryze is...",
  "user_id": "optional_user_identifier"
}
```

### Health Check

**Endpoint**: `GET /api/chatbot/health/`

**Response**:
```json
{
  "status": "ok",
  "message": "Devryze Chatbot is running"
}
```

## Database & Chat History

Chat history is stored in SQLite (`chat_history.db`). Each conversation is linked to a `user_id` for session management.

To view chat history in Django admin:

```bash
python manage.py createsuperuser
python manage.py runserver
# Visit http://localhost:8000/admin/
```

## Configuration

Edit `config/settings.py` to customize:

- `SECRET_KEY`: Change for production
- `DEBUG`: Set to `False` for production
- `ALLOWED_HOSTS`: Add your domain
- `DATABASES`: Configure database backend
- `CORS_ALLOWED_ORIGINS`: Add your frontend URLs

## Models & LLM

**Current Configuration**:
- **Embedding Model**: `all-MiniLM-L6-v2` (HuggingFace)
- **LLM**: `deepseek-ai/DeepSeek-R1-Distill-Llama-8B` (via HuggingFace Endpoint)
- **Vector Store**: FAISS (in-memory)
- **Chat History**: SQLite

To change the LLM, edit `chatbot/chain.py`:

```python
repo_id = "your-new-model/repo"
```

## Troubleshooting

### Module Not Found Errors

Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### HUGGINGFACE_TOKEN Not Set

Get a token from https://huggingface.co/settings/tokens and set it:
```bash
$env:HUGGINGFACE_TOKEN = "hf_your_token_here"
```

### Port Already in Use

Run on a different port:
```bash
python manage.py runserver 0.0.0.0:9000
```

### PDFs Not Loading

Check that PDF files exist in the current working directory. The chatbot will still function without them using the LLM directly.

## Production Deployment

For production, use a production-grade WSGI server:

```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Also:
1. Set `DEBUG = False` in `config/settings.py`
2. Update `SECRET_KEY` to a secure value
3. Configure `ALLOWED_HOSTS` with your domain
4. Use a production database (PostgreSQL recommended)
5. Set up HTTPS with SSL certificates

## License

© 2024 Devryze Chatbot

