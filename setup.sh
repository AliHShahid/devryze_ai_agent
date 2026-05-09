#!/bin/bash
echo "============================================"
echo "Devryze Chatbot - Django Setup Script"
echo "============================================"
echo

echo "[1/3] Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error installing dependencies"
    exit 1
fi

echo
echo "[2/3] Running database migrations..."
python manage.py makemigrations
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "Error running migrations"
    exit 1
fi

echo
echo "[3/3] Collecting static files..."
python manage.py collectstatic --noinput
if [ $? -ne 0 ]; then
    echo "Error collecting static files"
    exit 1
fi

echo
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo
echo "To run the application:"
echo "  python app.py"
echo
echo "Then open your browser to:"
echo "  http://localhost:8000"
echo
echo "API Documentation:"
echo "  POST http://localhost:8000/api/chatbot/chat/"
echo "  GET  http://localhost:8000/api/chatbot/health/"
echo
echo "Don't forget to set your HuggingFace token:"
echo "  export HUGGINGFACE_TOKEN=your_token_here"
echo
