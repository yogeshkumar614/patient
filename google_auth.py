import sqlite3

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from authlib.jose.errors import JoseError
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from requests.exceptions import RequestException

from database import get_connection


def configure_google_auth(app):
    oauth = OAuth(app)
    google = oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile', 'code_challenge_method': 'S256', 'timeout': 15},
    )
    app.extensions['medicase_google'] = google
    blueprint = Blueprint('google_auth', __name__)

    def enabled():
        return bool(current_app.config['GOOGLE_CLIENT_ID'] and current_app.config['GOOGLE_CLIENT_SECRET'])

    @app.context_processor
    def google_context():
        return {'google_enabled': enabled()}

    def failure(message):
        flash(message, 'error')
        return redirect(url_for('login'))

    @blueprint.get('/forgot-password')
    def forgot_password():
        if g.user:
            return redirect(url_for('dashboard'))
        return render_template('forgot-password.html', title='Forgot password')

    @blueprint.post('/auth/google')
    def start():
        if g.user:
            return redirect(url_for('dashboard'))
        if not enabled():
            return failure('Google sign-in is not enabled yet. Contact your workspace administrator for help signing in.')
        try:
            return google.authorize_redirect(current_app.config['GOOGLE_REDIRECT_URI'], prompt='select_account')
        except (OAuthError, RequestException, ValueError):
            return failure('Google sign-in is temporarily unavailable. Please try again.')

    @blueprint.get('/auth/google/callback')
    def callback():
        if g.user:
            return redirect(url_for('dashboard'))
        if not enabled():
            return failure('Google sign-in is not enabled yet. Contact your workspace administrator.')
        if request.args.get('error'):
            return failure('Google sign-in was cancelled or declined. You can try again.')
        try:
            token = google.authorize_access_token()
            identity = token.get('userinfo') if token.get('id_token') else None
        except (OAuthError, JoseError, RequestException, ValueError, KeyError):
            return failure('Google sign-in could not be verified. Please start again from the sign-in page.')
        if not identity or identity.get('email_verified') is not True or not identity.get('sub'):
            return failure('Google could not verify this account. Please use your registered Google account.')
        subject = identity['sub']
        email = (identity.get('email') or '').strip().lower()
        connection = get_connection()
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                linked = connection.execute('SELECT user_id FROM google_identities WHERE subject=?', (subject,)).fetchone()
                if linked:
                    user_id = linked['user_id']
                else:
                    authoritative_email = email.endswith('@gmail.com') or bool(identity.get('hd'))
                    user = connection.execute('SELECT user_id FROM users WHERE email=?', (email,)).fetchone() if authoritative_email else None
                    if not user:
                        return failure('This Google account is not connected to an approved MediCase account. Ask your workspace administrator to check your registered email.')
                    user_id = user['user_id']
                    connection.execute('INSERT INTO google_identities (subject,user_id) VALUES (?,?)', (subject, user_id))
                connection.execute('DELETE FROM login_attempts WHERE email=(SELECT email FROM users WHERE user_id=?)', (user_id,))
        except sqlite3.IntegrityError:
            return failure('This MediCase account is already connected to another Google account. Contact your workspace administrator.')
        session.clear()
        session['user_id'] = user_id
        session.permanent = True
        return redirect(url_for('dashboard'))

    app.register_blueprint(blueprint)
