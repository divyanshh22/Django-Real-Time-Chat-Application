from django.test import TestCase, Client
from django.urls import reverse
from login.models import CustomUser

class LoginRedirectTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpassword123',
            email='test@example.com'
        )
        self.client = Client()

    def test_login_redirects_to_chat_home(self):
        # Test logging in redirects to chat home
        response = self.client.post(reverse('login-view'), {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        # Login view redirects to chat:home-view on successful login
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chat:home-view'))

    def test_authenticated_user_accessing_root_redirects_to_chat_home(self):
        # Log the user in
        self.client.login(username='testuser', password='testpassword123')
        # Access the root URL
        response = self.client.get(reverse('login-view'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chat:home-view'))

    def test_chat_home_renders_successfully(self):
        # Create another user and a message
        other_user = CustomUser.objects.create_user(
            username='otheruser',
            password='otherpassword123',
            email='other@example.com'
        )
        from chat.models import Message
        Message.objects.create(
            sender=self.user,
            receiver=other_user,
            text='Hello'
        )

        # Log the user in
        self.client.login(username='testuser', password='testpassword123')
        # Access the chat home URL
        response = self.client.get(reverse('chat:home-view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'otheruser')



