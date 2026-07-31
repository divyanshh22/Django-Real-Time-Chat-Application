from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Message
from login.models import CustomUser
import redis
from datetime import datetime


@login_required(login_url='login-view')
def home_view(request):
    # current user ke saare messages
    all_messages = Message.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    )

    # unique users nikaal jinse baat ki hai
    user_ids = set()
    for msg in all_messages:
        if msg.sender != request.user:
            user_ids.add(msg.sender.id)
        if msg.receiver != request.user:
            user_ids.add(msg.receiver.id)

    chat_users = CustomUser.objects.filter(id__in=user_ids)

    # Add online status from Redis
    online_users = {}
    last_seen = {}
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        online_users = r.hgetall('online_users')
        last_seen = r.hgetall('last_seen')
    except Exception:
        pass

    for user in chat_users:
        user.is_online = online_users.get(str(user.id)) == 'online'
        user.last_seen_str = last_seen.get(str(user.id))

    return render(request, 'chat/home.html', {
        'chat_users': chat_users,
    })



@login_required(login_url='login-view')
def conversation_view(request, username):
    other_user = get_object_or_404(CustomUser, username=username)

    # dono ke beech ke messages
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    )

    # messages read mark karo
    Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)

    # POST - naya message save karo
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        photo = request.FILES.get('photo')

        if text or photo:
            Message.objects.create(
                sender=request.user,
                receiver=other_user,
                text=text,
                photo=photo
            )
        return redirect('chat:conversation-view', username=username)

    # Get online status from Redis
    is_online = False
    last_seen_str = None
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        is_online = r.hget('online_users', str(other_user.id)) == 'online'
        last_seen_str = r.hget('last_seen', str(other_user.id))
    except Exception:
        pass

    other_user.is_online = is_online
    other_user.last_seen_str = last_seen_str

    return render(request, 'chat/conversation.html', {
        'other_user': other_user,
        'messages': messages,
    })


@login_required(login_url='login-view')
def search_view(request):
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        results = CustomUser.objects.filter(
            username__icontains=query
        ).exclude(id=request.user.id)  # khud ko exclude karo

    return render(request, 'chat/search.html', {
        'results': results,
        'query': query,
    })


@login_required(login_url='login-view')
@require_http_methods(["GET"])
def get_messages_api(request, username):
    """API endpoint to fetch messages for WebSocket initialization"""
    other_user = get_object_or_404(CustomUser, username=username)

    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).order_by('timestamp')

    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'sender_id': msg.sender.id,
            'sender_username': msg.sender.username,
            'text': msg.text,
            'photo_url': msg.photo.url if msg.photo else None,
            'timestamp': msg.timestamp.isoformat(),
            'is_read': msg.is_read
        })

    return JsonResponse({'messages': messages_data})


@login_required(login_url='login-view')
@require_http_methods(["GET"])
def get_user_status_api(request, user_id):
    """API endpoint to get user online status"""
    try:
        user = CustomUser.objects.get(id=user_id)
        is_online = False
        last_seen = None
        try:
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
            is_online = r.hget('online_users', str(user_id)) == 'online'
            last_seen = r.hget('last_seen', str(user_id))
        except Exception:
            pass

        return JsonResponse({
            'user_id': user.id,
            'username': user.username,
            'is_online': is_online,
            'last_seen': last_seen
        })
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
