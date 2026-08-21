from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class AccountsSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='accuser',
            email='accuser@example.com',
            password='Password123'
        )

    def test_user_registration(self):
        url = reverse('accounts:register')
        res = self.client.post(url, {
            'username': 'newuser123',
            'email': 'newuser123@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'ComplexP@ssw0rd2026!',
            'password2': 'ComplexP@ssw0rd2026!'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(User.objects.filter(email='newuser123@example.com').exists())

    def test_user_login_and_logout(self):
        login_url = reverse('accounts:login')
        res = self.client.post(login_url, {
            'username': 'accuser@example.com',
            'password': 'Password123'
        })
        self.assertEqual(res.status_code, 302)

        logout_url = reverse('accounts:logout')
        res_logout = self.client.get(logout_url)
        self.assertEqual(res_logout.status_code, 302)

    def test_user_profile_view(self):
        self.client.login(email='accuser@example.com', password='Password123')
        profile_url = reverse('accounts:profile')
        res = self.client.get(profile_url)
        self.assertEqual(res.status_code, 200)

    def test_payment_history_view(self):
        self.client.login(email='accuser@example.com', password='Password123')
        pay_hist_url = reverse('accounts:payment_history')
        res = self.client.get(pay_hist_url)
        self.assertEqual(res.status_code, 200)
