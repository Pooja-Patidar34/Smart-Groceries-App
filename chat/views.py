from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Chat, Message
from .serializers import *
from recipe_section.models import ListedMeal
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from transactions.models import Order




class SendMessageAPIView(APIView):
    def post(self, request):
        data = request.data

        meal_id = data.get("meal_id")

        try:
            meal = ListedMeal.objects.get(id=meal_id)
        except ListedMeal.DoesNotExist:
            return Response({'ok':False,"error": "Meal ID not found."}, status=404)
        
        seller_id = data.get("seller_id")
        buyer_id = data.get("buyer_id")

            
        # Check if chat already exists
        chat, created = Chat.objects.get_or_create(meal = meal, seller_id = seller_id, buyer_id = buyer_id)
        try:
            orders = Order.objects.get(buyer = buyer_id, seller = seller_id)
            orders.chat_id = chat.id 
            orders.save()
        except Exception:
            pass


        # Now attach chat to message
        message_data = {
            "chat": chat,
            "seller_id": data.get("seller_id"),
            "buyer_id": data.get("buyer_id"),
            "message": data.get("message"),
            "message_type": data.get("message_type"),
            "read_status": data.get("read_status", False)
        }
        Message.objects.create(**message_data)

        return Response({'ok':True,'data':chat.id},status=status.HTTP_201_CREATED)



class GetMessagesAPIView(APIView):
    def get(self, request):
        try:
            chat_id = request.data.get('chat_id')
            chat  = Chat.objects.get(id = chat_id)
            messages = Message.objects.filter(chat = chat)
            serializer = MessageSerializer(messages, many = True)
            return Response({'ok':True,"data": serializer.data})
        except Exception:
            return Response({'ok': False, 'error': 'Invalid or missing meal_id, seller_id, or buyer_id.'})


class SearchText(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        text = request.data.get('text')
        chat_id = request.data.get('chat_id')
        
        chat = Chat.objects.get(id = chat_id)
        messages = Message.objects.filter(chat=chat, message__icontains=text).order_by('-timestamp')
        
        paginator = PageNumberPagination()
        paginator.page_size = 10  

        result_page = paginator.paginate_queryset(messages, request)
        serialized_data = SearchedMessageSerializer(result_page, many=True).data
        data = {
            "ok": True,
            "count": paginator.page.paginator.count,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "data": serialized_data
        }
        return Response(data, status = status.HTTP_200_OK)
    
class SetReadStatus(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        chat_id = request.data.get('chat_id')
        
        if not chat_id:
            return Response({'ok': False, 'error': 'chat_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        Message.objects.filter(chat__id=chat_id,read_status = False).update(read_status=True)

        return Response({'ok': True, 'data': "Marked as read."}, status=status.HTTP_200_OK)


class CountMessages(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        chat_id = request.data.get('chat_id')
        unread_messages = Message.objects.filter(chat__id=chat_id,read_status = False).count()

        return Response({'ok':True,'data':unread_messages},status=status.HTTP_200_OK)



class DeleteMessage(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        chat_id = request.data.get('chat_id')
        message_ids = request.data.get('message_ids', [])

        if not chat_id or not message_ids:
            return Response(
                {'ok': False, 'error': 'chat_id and message_ids are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(message_ids, list) or not all(isinstance(i, int) for i in message_ids):
            return Response(
                {'ok': False, 'error': 'message_ids must be a list of integers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Message.objects.filter(chat__id=chat_id, id__in = message_ids).delete()

        return Response(
            {'ok': True, 'data': "Messages Deleted."},
            status=status.HTTP_200_OK
        )

class ReverseMessage(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pass
    
