from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('chat/', views.chat_view, name='chat'),
    path('health/', views.health_check, name='health'),
]
