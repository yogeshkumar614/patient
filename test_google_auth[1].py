import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from authlib.integrations.base_client.errors import OAuthError
from flask import redirect
from requests.exceptions import ConnectionError

from app import create_app
from database import get_connection
from seed import seed_data


class GoogleSignInTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(Path(self.temp.name) / 'patient_case.db'), 'GOOGLE_CLIENT_ID': 'test-client', 'GOOGLE_CLIENT_SECRET': 'test-secret'})
        with self.app.app_context():
            seed_data()
            connection = get_connection()
            with connection:
                connection.execute("UPDATE users SET email='doctor@gmail.com' WHERE user_id=1")
        self.client = self.app.test_client()
        self.google = self.app.extensions['medicase_google']

    def tearDown(self):
        self.temp.cleanup()

    def callback(self, **claims):
        identity = {'sub': 'google-123', 'email': 'doctor@gmail.com', 'email_verified': True, **claims}
        with patch.object(self.google, 'authorize_access_token', return_value={'id_token': 'validated-by-library', 'userinfo': identity}):
            return self.client.get('/auth/google/callback')

    def test_forgot_password_and_start_protected_by_csrf(self):
        page = self.client.get('/forgot-password', headers={'Host': 'untrusted.example'})
        self.assertIn('Continue with Google', page.text)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        self.assertEqual(self.client.post('/auth/google').status_code, 400)
        with patch.object(self.google, 'authorize_redirect', return_value=redirect('https://accounts.google.com/')) as start:
            response = self.client.post('/auth/google', data={'csrf_token': token}, headers={'Host': 'untrusted.example'})
            self.assertEqual(response.status_code, 302)
            start.assert_called_once_with('http://127.0.0.1:5000/auth/google/callback', prompt='select_account')

    def test_real_oauth_start_uses_state_nonce_pkce_and_rejects_wrong_state(self):
        page = self.client.get('/login')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        metadata = {'authorization_endpoint': 'https://accounts.google.com/o/oauth2/v2/auth'}
        with patch.object(self.google, 'load_server_metadata', return_value=metadata):
            response = self.client.post('/auth/google', data={'csrf_token': token})
        parameters = parse_qs(urlparse(response.location).query)
        self.assertTrue(parameters['state'][0])
        self.assertTrue(parameters['nonce'][0])
        self.assertTrue(parameters['code_challenge'][0])
        self.assertEqual(parameters['code_challenge_method'], ['S256'])
        with patch.object(self.google, 'fetch_access_token') as exchange:
            denied = self.client.get('/auth/google/callback?state=forged&code=forged')
            self.assertEqual(denied.location, '/login')
            exchange.assert_not_called()

    def test_registered_verified_google_account_can_recover_access(self):
        with self.client.session_transaction() as old_session:
            old_session['csrf_token'] = 'old'
        self.assertEqual(self.callback().location, '/dashboard')
        with self.client.session_transaction() as authenticated:
            self.assertEqual(authenticated['user_id'], 1)
            self.assertNotIn('csrf_token', authenticated)
            self.assertNotIn('id_token', authenticated)
        with self.app.app_context():
            self.assertEqual(get_connection().execute('SELECT subject FROM google_identities').fetchone()[0], 'google-123')

    def test_unknown_unverified_and_external_email_accounts_are_denied(self):
        for claims in [{'email': 'unknown@gmail.com'}, {'email_verified': False}, {'email_verified': 'true'}, {'sub': ''}, {'email': ''}]:
            self.assertEqual(self.callback(**claims).location, '/login')
            with self.client.session_transaction() as state:
                self.assertNotIn('user_id', state)
        with self.app.app_context():
            connection = get_connection()
            with connection:
                connection.execute("UPDATE users SET email='doctor@example.com' WHERE user_id=1")
        self.assertEqual(self.callback(email='doctor@example.com').location, '/login')
        self.assertEqual(self.callback(email='doctor@example.com', hd='example.com').location, '/dashboard')

    def test_existing_google_subject_cannot_be_replaced(self):
        self.callback()
        with self.client.session_transaction() as state:
            state.clear()
        self.assertEqual(self.callback(sub='different-subject').location, '/login')
        self.assertEqual(self.callback(email='renamed@gmail.com').location, '/dashboard')

    def test_provider_errors_missing_tokens_and_disabled_setup(self):
        for error in [OAuthError('mismatching_state'), ConnectionError('offline'), ValueError('invalid token')]:
            with patch.object(self.google, 'authorize_access_token', side_effect=error):
                self.assertEqual(self.client.get('/auth/google/callback').location, '/login')
        with patch.object(self.google, 'authorize_access_token', return_value={'userinfo': {'sub': 'google-123', 'email_verified': True, 'email': 'doctor@gmail.com'}}):
            self.assertEqual(self.client.get('/auth/google/callback').location, '/login')
        self.assertEqual(self.client.get('/auth/google/callback?error=access_denied').location, '/login')
        self.app.config['GOOGLE_CLIENT_SECRET'] = ''
        self.assertIn('not enabled', self.client.get('/forgot-password').text)
        self.assertIn('disabled', self.client.get('/login').text)
        self.assertEqual(self.client.get('/auth/google/callback').location, '/login')


if __name__ == '__main__':
    unittest.main()
