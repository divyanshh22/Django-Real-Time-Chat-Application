from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Message


class ChatMessageDeliveryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_model = get_user_model()
        self.sender = self.user_model.objects.create_user(username='sender', password='secret123')
        self.receiver = self.user_model.objects.create_user(username='receiver', password='secret123')
        self.client.force_login(self.sender)

    def test_send_message_api_creates_message_for_authenticated_user(self):
        response = self.client.post(
            reverse('chat:send-message-api', kwargs={'username': self.receiver.username}),
            {'text': 'hello there'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Message.objects.filter(sender=self.sender, receiver=self.receiver, text='hello there').exists())
