import hmac
import os
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import DATABASE, ROOT, close_connection, generate_patient_id, get_connection, initialize_database, insert_record, update_record
from validation import BLOOD_GROUPS, CASE_LABELS, GENDERS, VITALS, validate_case, validate_patient, validate_vitals
from google_auth import configure_google_auth


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(DATABASE), SECRET_KEY=os.environ.get('MEDICASE_SECRET_KEY'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('MEDICASE_HTTPS') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=256 * 1024,
        GOOGLE_CLIENT_ID=os.environ.get('GOOGLE_CLIENT_ID', ''),
        GOOGLE_CLIENT_SECRET=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        GOOGLE_REDIRECT_URI=os.environ.get('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/auth/google/callback'),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY']:
        secret_path = ROOT / '.secret_key'
        try:
            with secret_path.open('x', encoding='utf-8') as secret_file:
                secret_file.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config['SECRET_KEY'] = secret_path.read_text(encoding='utf-8').strip()
    app.teardown_appcontext(close_connection)
    with app.app_context():
        initialize_database()
    configure_google_auth(app)

    def csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return session['csrf_token']

    @app.before_request
    def protect_request():
        g.user = None
        if session.get('user_id'):
            g.user = get_connection().execute('SELECT * FROM users WHERE user_id=?', (session['user_id'],)).fetchone()
        if request.endpoint and request.endpoint not in ['login', 'static', 'google_auth.start', 'google_auth.callback', 'google_auth.forgot_password'] and not g.user:
            return redirect(url_for('login'))
        if request.method == 'POST':
            token = request.form.get('csrf_token', '')
            if not token or not hmac.compare_digest(token.encode('utf-8'), session.get('csrf_token', '').encode('utf-8')):
                abort(400, description='Your form expired. Reload the page and try again.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.template_filter('age')
    def age_filter(birthday):
        if not birthday:
            return '—'
        try:
            born = date.fromisoformat(birthday)
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            return '—'

    @app.context_processor
    def template_context():
        return dict(csrf_token=csrf_token, today=date.today().isoformat(), case_labels=CASE_LABELS, vital_fields=VITALS, genders=GENDERS, blood_groups=BLOOD_GROUPS)

    def patient_or_404(patient_id):
        patient = get_connection().execute('SELECT * FROM patients WHERE patient_id=?', (patient_id,)).fetchone()
        if patient is None:
            abort(404)
        return patient

    def case_or_404(case_id):
        case = get_connection().execute('SELECT cases.*, users.name AS clinician FROM cases LEFT JOIN users ON users.user_id=cases.doctor_id WHERE case_id=?', (case_id,)).fetchone()
        if case is None:
            abort(404)
        return case

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user:
            return redirect(url_for('dashboard'))
        error, status = None, 200
        email = request.form.get('email', '').strip().lower()[:150]
        if request.method == 'POST':
            connection = get_connection()
            attempt = connection.execute('SELECT * FROM login_attempts WHERE email=?', (email,)).fetchone()
            if attempt and attempt['attempts'] >= 5 and time.time() - attempt['updated_at'] < 300:
                error, status = 'Too many attempts. Try again in five minutes.', 429
            else:
                user = connection.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
                if user and check_password_hash(user['password_hash'], request.form.get('password', '')):
                    with connection:
                        connection.execute('DELETE FROM login_attempts WHERE email=?', (email,))
                    session.clear()
                    session['user_id'] = user['user_id']
                    session.permanent = True
                    return redirect(url_for('dashboard'))
                count = attempt['attempts'] + 1 if attempt and time.time() - attempt['updated_at'] < 300 else 1
                with connection:
                    connection.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,?,?)', (email, count, time.time()))
                error, status = 'Email or password is incorrect.', 401
        return render_template('index.html', title='Sign in', error=error, email=email), status

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    def home():
        return redirect(url_for('dashboard'))

    @app.get('/dashboard')
    def dashboard():
        connection = get_connection()
        stats = {
            'patients': connection.execute('SELECT COUNT(*) FROM patients').fetchone()[0],
            'cases': connection.execute('SELECT COUNT(*) FROM cases').fetchone()[0],
            'active': connection.execute("SELECT COUNT(*) FROM cases WHERE status='Active'").fetchone()[0],
            'today': connection.execute('SELECT COUNT(*) FROM cases WHERE substr(visit_date,1,10)=?', (datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0],
        }
        patients = connection.execute('SELECT * FROM patients ORDER BY created_at DESC, patient_id DESC LIMIT 6').fetchall()
        recent_cases = connection.execute('SELECT cases.*, first_name, last_name FROM cases JOIN patients USING(patient_id) ORDER BY visit_date DESC,case_id DESC LIMIT 4').fetchall()
        return render_template('dashboard.html', title='Dashboard', stats=stats, patients=patients, recent_cases=recent_cases)

    @app.get('/patients')
    def patients():
        query = request.args.get('q', '').strip()[:150]
        pattern = '%' + query.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        rows = get_connection().execute("SELECT * FROM patients WHERE patient_id LIKE ? ESCAPE '!' OR (first_name || ' ' || COALESCE(last_name,'')) LIKE ? ESCAPE '!' OR phone LIKE ? ESCAPE '!' OR blood_group LIKE ? ESCAPE '!' ORDER BY created_at DESC,patient_id DESC", (pattern,) * 4).fetchall()
        return render_template('patients.html', title='Patient directory', patients=rows, query=query)

    def save_patient(patient=None):
        errors, data = {}, dict(patient) if patient else {}
        if request.method == 'POST':
            data, errors = validate_patient(request.form)
            if not errors:
                connection = get_connection()
                try:
                    with connection:
                        connection.execute('BEGIN IMMEDIATE')
                        duplicate = connection.execute("SELECT patient_id FROM patients WHERE lower(trim(first_name))=lower(?) AND lower(trim(COALESCE(last_name,'')))=lower(?) AND date_of_birth=? AND phone=? AND patient_id<>?", (data['first_name'], data['last_name'], data['date_of_birth'], data['phone'], patient['patient_id'] if patient else '')).fetchone()
                        if duplicate:
                            errors['duplicate'] = f"A matching patient already exists: {duplicate['patient_id']}. Open that record instead."
                        else:
                            patient_id = patient['patient_id'] if patient else generate_patient_id(connection)
                            if patient:
                                update_record(connection, 'patients', data, 'patient_id', patient_id)
                            else:
                                insert_record(connection, 'patients', {'patient_id': patient_id, **data})
                    if not errors:
                        flash('Patient record saved.', 'success')
                        return redirect(url_for('patient_profile', patient_id=patient_id))
                except sqlite3.IntegrityError:
                    errors['duplicate'] = 'The record conflicts with an existing patient. Please review the details.'
        return render_template('add-patient.html', title='Edit patient' if patient else 'Register patient', data=data, errors=errors, patient=patient), 422 if errors else 200

    @app.route('/patients/new', methods=['GET', 'POST'])
    def add_patient():
        return save_patient()

    @app.route('/patients/<patient_id>/edit', methods=['GET', 'POST'])
    def edit_patient(patient_id):
        return save_patient(patient_or_404(patient_id))

    @app.get('/patients/<patient_id>/history')
    @app.get('/patients/<patient_id>')
    def patient_profile(patient_id):
        patient = patient_or_404(patient_id)
        cases = get_connection().execute('SELECT * FROM cases WHERE patient_id=? ORDER BY visit_date DESC, case_id DESC', (patient_id,)).fetchall()
        vitals = get_connection().execute('SELECT * FROM vitals WHERE patient_id=? ORDER BY recorded_at DESC,vital_id DESC LIMIT 1', (patient_id,)).fetchone()
        return render_template('patient-profile.html', title='Patient profile', patient=patient, cases=cases, vitals=vitals)

    @app.route('/patients/<patient_id>/delete', methods=['GET', 'POST'])
    def delete_patient(patient_id):
        patient = patient_or_404(patient_id)
        if request.method == 'POST':
            if request.form.get('confirm_id', '') != patient_id:
                return render_template('delete-patient.html', title='Delete patient', patient=patient, error='Enter the patient ID exactly to confirm.'), 422
            connection = get_connection()
            with connection:
                connection.execute('DELETE FROM patients WHERE patient_id=?', (patient_id,))
            flash('Patient and linked case records deleted.', 'success')
            return redirect(url_for('patients'))
        return render_template('delete-patient.html', title='Delete patient', patient=patient)

    def save_case(patient, case=None):
        errors = {}
        data = dict(case) if case else {'status': 'Active', 'allergies': patient['allergies']}
        if request.method == 'POST':
            data, vitals, errors = validate_case(request.form)
            if not errors:
                connection = get_connection()
                with connection:
                    if case:
                        update_record(connection, 'cases', data, 'case_id', case['case_id'])
                        connection.execute('UPDATE cases SET updated_at=CURRENT_TIMESTAMP WHERE case_id=?', (case['case_id'],))
                        case_id = case['case_id']
                    else:
                        case_id = insert_record(connection, 'cases', {**data, 'patient_id': patient['patient_id'], 'doctor_id': g.user['user_id']})
                    if any(value is not None for value in vitals.values()):
                        insert_record(connection, 'vitals', {**vitals, 'patient_id': patient['patient_id'], 'case_id': case_id})
                flash('Case saved. The patient timeline is up to date.', 'success')
                return redirect(url_for('case_details', case_id=case_id))
            data = dict(request.form)
        return render_template('case-form.html', title='Edit case' if case else 'New case', patient=patient, case=case, data=data, errors=errors), 422 if errors else 200

    @app.route('/cases/new/<patient_id>', methods=['GET', 'POST'])
    def add_case(patient_id):
        return save_case(patient_or_404(patient_id))

    @app.route('/cases/<int:case_id>/edit', methods=['GET', 'POST'])
    def edit_case(case_id):
        case = case_or_404(case_id)
        return save_case(patient_or_404(case['patient_id']), case)

    @app.get('/cases/<int:case_id>')
    def case_details(case_id):
        case = case_or_404(case_id)
        vitals = get_connection().execute('SELECT * FROM vitals WHERE case_id=? ORDER BY recorded_at DESC,vital_id DESC', (case_id,)).fetchall()
        return render_template('case-details.html', title='Case details', case=case, patient=patient_or_404(case['patient_id']), vitals= vitals)

    @app.route('/cases/<int:case_id>/vitals', methods=['GET', 'POST'])
    def add_vitals(case_id):
        case = case_or_404(case_id)
        data, errors = {}, {}
        if request.method == 'POST':
            values, errors = validate_vitals(request.form)
            data = dict(request.form)
            if not errors and all(value is None for value in values.values()):
                errors['vitals'] = 'Enter at least one measurement.'
            if not errors:
                connection = get_connection()
                with connection:
                    insert_record(connection, 'vitals', {**values, 'patient_id': case['patient_id'], 'case_id': case_id})
                flash('Vitals recorded.', 'success')
                return redirect(url_for('case_details', case_id=case_id))
        return render_template('vitals-form.html', title='Record vitals', case=case, data=data, errors=errors), 422 if errors else 200

    @app.get('/reports')
    def reports():
        cases = get_connection().execute('SELECT cases.*,first_name,last_name FROM cases JOIN patients USING(patient_id) ORDER BY visit_date DESC,case_id DESC').fetchall()
        return render_template('reports.html', title='Reports', cases=cases)

    @app.get('/report/<int:case_id>')
    def report(case_id):
        case = case_or_404(case_id)
        vitals = get_connection().execute('SELECT * FROM vitals WHERE case_id=? ORDER BY recorded_at DESC,vital_id DESC', (case_id,)).fetchall()
        return render_template('report.html', title='Patient case summary', case=case, patient=patient_or_404(case['patient_id']), vitals=vitals)

    def handle_error(error):
        if error.code == 500:
            get_connection().rollback()
        messages = {400: 'The request could not be completed.', 404: 'This record or page could not be found.', 405: 'This action requires a different request.', 413: 'This form is too large.', 500: 'Something went wrong. Please try again.', 503: 'The database is busy. Please try again shortly.'}
        return render_template('error.html', title=f'Error {error.code}', code=error.code, message=messages.get(error.code, 'Unable to complete this request.')), error.code

    for code in [400, 404, 405, 413, 500, 503]:
        app.register_error_handler(code, handle_error)

    @app.errorhandler(sqlite3.OperationalError)
    def database_error(error):
        app.logger.error('Database operation failed: %s', type(error).__name__)
        get_connection().rollback()
        return render_template('error.html', title='Database unavailable', code=503, message='The database is unavailable. Please try again shortly.'), 503

    @app.cli.command('init-db')
    def init_db_command():
        initialize_database()
        click.echo('Database initialized without deleting records.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        from seed import seed_data
        seed_data()
        click.echo('Demo ready: doctor@medicase.demo / demo123')

    @app.cli.command('create-user')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True)
    @click.password_option()
    def create_user_command(email, name, password):
        if len(password) < 10:
            raise click.ClickException('Use at least 10 characters.')
        connection = get_connection()
        try:
            with connection:
                insert_record(connection, 'users', {'email': email.strip().lower(), 'name': name.strip(), 'password_hash': generate_password_hash(password)})
        except sqlite3.IntegrityError:
            raise click.ClickException('That email already exists.') from None
        click.echo('User created.')

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000, debug=False)
