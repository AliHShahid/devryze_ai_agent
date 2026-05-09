from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .chain import chat
import json


@api_view(['POST'])
def chat_view(request):
    """
    Handle chat messages via REST API.
    
    Expected JSON:
    {
        "message": "Your message here",
        "user_id": "optional_user_identifier"
    }
    """
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        user_id = data.get('user_id', 'default_user')
        
        if not message:
            return Response(
                {'error': 'Message cannot be empty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response = chat(message, user_id)
        # Normalize and provide a helpful fallback if model returned nothing
        if not response or not str(response).strip():
            print(f"Warning: chat() returned empty for user_id={user_id}, message={message}")
            response = "Model did not return a response. Check server logs or HuggingFace token/permissions."

        return Response({
            'user_message': message,
            'bot_response': response,
            'user_id': user_id
        }, status=status.HTTP_200_OK)
        
    except json.JSONDecodeError:
        return Response(
            {'error': 'Invalid JSON'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'ok',
        'message': 'Devryze Chatbot is running'
    }, status=status.HTTP_200_OK)
