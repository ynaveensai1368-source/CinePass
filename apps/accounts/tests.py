from unittest.mock import patch, MagicMock
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

    def test_user_login_with_email_and_username(self):
        login_url = reverse('accounts:login')
        # Login using email
        res1 = self.client.post(login_url, {
            'username': 'accuser@example.com',
            'password': 'Password123'
        })
        self.assertEqual(res1.status_code, 302)

        self.client.logout()

        # Login using username
        res2 = self.client.post(login_url, {
            'username': 'accuser',
            'password': 'Password123'
        })
        self.assertEqual(res2.status_code, 302)

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

    def test_google_login_redirect(self):
        url = reverse('accounts:google_login')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.url.startswith('https://accounts.google.com/o/oauth2/v2/auth'))
        self.assertIn('client_id=', res.url)
        self.assertIn('redirect_uri=', res.url)
        self.assertIn('state=', res.url)

    @patch('requests.get')
    @patch('requests.post')
    def test_google_login_callback_new_user(self, mock_post, mock_get):
        # 1. Set session state
        session = self.client.session
        session['google_oauth_state'] = 'test_state_123'
        session['google_oauth_next'] = '/'
        session.save()

        # 2. Mock token exchange response
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            'access_token': 'fake_google_access_token_123'
        }
        mock_post.return_value = mock_token_resp

        # 3. Mock userinfo response
        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            'email': 'googleuser@gmail.com',
            'given_name': 'Google',
            'family_name': 'User',
            'name': 'Google User',
            'picture': 'https://example.com/avatar.jpg'
        }
        mock_get.return_value = mock_userinfo_resp

        # 4. Trigger callback
        callback_url = reverse('accounts:google_callback')
        res = self.client.get(callback_url, {'code': 'fake_code_123', 'state': 'test_state_123'})
        self.assertEqual(res.status_code, 302)

        # 5. Verify user created
        new_user = User.objects.filter(email='googleuser@gmail.com').first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.first_name, 'Google')
        self.assertEqual(new_user.last_name, 'User')
        self.assertEqual(new_user.role, 'CUSTOMER')

    @patch('requests.get')
    @patch('requests.post')
    def test_google_login_callback_existing_user(self, mock_post, mock_get):
        session = self.client.session
        session['google_oauth_state'] = 'test_state_456'
        session.save()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {'access_token': 'fake_token'}
        mock_post.return_value = mock_token_resp

        mock_userinfo_resp = MagicMock()
        mock_userinfo_resp.status_code = 200
        mock_userinfo_resp.json.return_value = {
            'email': 'accuser@example.com',
            'given_name': 'UpdatedFirst',
            'family_name': 'UpdatedLast'
        }
        mock_get.return_value = mock_userinfo_resp

        callback_url = reverse('accounts:google_callback')
        res = self.client.get(callback_url, {'code': 'fake_code_456', 'state': 'test_state_456'})
        self.assertEqual(res.status_code, 302)

        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'UpdatedFirst')
