@echo off
echo ============================================
echo Devryze Chatbot - Django Setup Script
echo ============================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing dependencies
    exit /b 1
)

echo.
echo [2/3] Running database migrations...
python manage.py makemigrations
python manage.py migrate
if %errorlevel% neq 0 (
    echo Error running migrations
    exit /b 1
)

echo.
echo [3/3] Collecting static files...
python manage.py collectstatic --noinput
if %errorlevel% neq 0 (
    echo Error collecting static files
    exit /b 1
)

echo.
echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo To run the application:
echo   python app.py
echo.
echo Then open your browser to:
echo   http://localhost:8000
echo.
echo API Documentation:
echo   POST http://localhost:8000/api/chatbot/chat/
echo   GET  http://localhost:8000/api/chatbot/health/
echo.
echo Don't forget to set your HuggingFace token:
echo   $env:HUGGINGFACE_TOKEN = "your_token_here"
echo.
pause
