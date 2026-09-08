import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app
from database import get_connection
from seed import seed_data


class MediCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'DATABASE': str(Path(self.temp.name) / 'patient_case.db')})
        with self.app.app_context():
            seed_data()
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def token(self, path='/login'):
        response = self.client.get(path)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.text)
        self.assertIsNotNone(match, response.text[:500])
        return match.group(1)

    def post(self, path, data, source=None):
        return self.client.post(path, data={**data, 'csrf_token': self.token(source or path)})

    def login(self):
        response = self.post('/login', {'email': 'doctor@medicase.demo', 'password': 'demo123'})
        self.assertEqual(response.status_code, 302)

    def patient_data(self, **changes):
        return {'first_name': 'Test', 'last_name': 'Patient', 'date_of_birth': '1999-01-01', 'gender': 'Other', 'phone': '9000001234', 'email': 'test@example.com', 'blood_group': 'A+', **changes}

    def test_authentication_csrf_logout_and_headers(self):
        for path in ['/dashboard', '/patients', '/reports', '/cases/1', '/report/1', '/patients/PAT0001']:
            self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.client.post('/login', data={'email': 'x'}).status_code, 400)
        self.assertEqual(self.client.post('/login', data={'csrf_token': 'invalid-₹'}).status_code, 400)
        self.assertEqual(self.post('/login', {'email': 'doctor@medicase.demo', 'password': 'wrong'}).status_code, 401)
        self.login()
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertEqual(self.client.post('/patients/new', data=self.patient_data()).status_code, 400)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.post('/logout', {}, '/dashboard').status_code, 302)
        self.assertEqual(self.client.get('/patients').status_code, 302)

    def test_seed_is_idempotent_and_all_pages_render(self):
        with self.app.app_context():
            seed_data()
            connection = get_connection()
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM patients').fetchone()[0], 10)
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM cases').fetchone()[0], 15)
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.login()
        for path in ['/', '/dashboard', '/patients', '/patients/new', '/patients/PAT0001', '/patients/PAT0001/history', '/patients/PAT0001/edit', '/patients/PAT0001/delete', '/cases/new/PAT0001', '/cases/1', '/cases/1/edit', '/cases/1/vitals', '/reports', '/report/1']:
            response = self.client.get(path, follow_redirects=True)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn('localStorage', response.text)
        for path in ['/unknown', '/patients/PAT9999', '/cases/9999', '/report/9999', '/cases/new/PAT9999']:
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_patient_crud_duplicates_and_search(self):
        self.login()
        response = self.post('/patients/new', self.patient_data())
        self.assertEqual(response.status_code, 302)
        profile_url = response.location
        patient_id = profile_url.split('/')[-1]
        self.assertEqual(self.post('/patients/new', self.patient_data()).status_code, 422)
        self.assertEqual(self.post('/patients/new', self.patient_data(first_name='test', phone='90000 01234')).status_code, 422)
        for query in ['Test Patient', patient_id, '9000001234']:
            self.assertIn(patient_id, self.client.get('/patients', query_string={'q': query}).text)
        self.assertNotIn('PAT0001', self.client.get('/patients?q=%25').text)
        self.assertEqual(self.post(profile_url + '/edit', self.patient_data(first_name='Updated')).status_code, 302)
        self.assertIn('Updated', self.client.get(profile_url).text)
        self.assertEqual(self.post(profile_url + '/delete', {'confirm_id': 'WRONG'}).status_code, 422)
        self.assertEqual(self.post(profile_url + '/delete', {'confirm_id': patient_id}).status_code, 302)
        self.assertEqual(self.client.get(profile_url).status_code, 404)
        next_response = self.post('/patients/new', self.patient_data())
        self.assertNotEqual(next_response.location, profile_url)

    def test_patient_validation_and_escaping(self):
        self.login()
        for changes in [{'first_name': ''}, {'date_of_birth': '2999-01-01'}, {'date_of_birth': 'bad'}, {'phone': 'abc'}, {'email': 'invalid'}, {'blood_group': 'X'}, {'gender': 'invalid'}]:
            self.assertEqual(self.post('/patients/new', self.patient_data(**changes)).status_code, 422, changes)
        response = self.post('/patients/new', self.patient_data(first_name='<script>alert(1)</script>'))
        page = self.client.get(response.location).text
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)

    def test_case_vitals_report_edit_and_cascade(self):
        self.login()
        response = self.post('/cases/new/PAT0001', {'chief_complaint': 'New test consultation', 'status': 'Active', 'temperature': '101.2', 'systolic_bp': '120', 'diastolic_bp': '80', 'oxygen_saturation': '0', 'doctor_notes': 'Unique test notes'})
        self.assertEqual(response.status_code, 302)
        case_url = response.location
        case_id = int(case_url.split('/')[-1])
        self.assertIn('New test consultation', self.client.get('/patients/PAT0001').text)
        report = self.client.get(f'/report/{case_id}').text
        self.assertIn('Unique test notes', report)
        self.assertIn('101.2', report)
        self.assertEqual(self.post(case_url + '/edit', {'chief_complaint': 'Updated complaint', 'status': 'Closed'}).status_code, 302)
        self.assertEqual(self.post(case_url + '/vitals', {'pulse': '85'}).status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_connection().execute('SELECT COUNT(*) FROM vitals WHERE case_id=?', (case_id,)).fetchone()[0], 2)
        self.assertIn('Updated complaint', self.client.get(case_url).text)
        self.assertEqual(self.post('/patients/PAT0001/delete', {'confirm_id': 'PAT0001'}).status_code, 302)
        self.assertEqual(self.client.get(case_url).status_code, 404)
        with self.app.app_context():
            connection = get_connection()
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM vitals WHERE patient_id='PAT0001'").fetchone()[0], 0)
            self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_invalid_vitals_do_not_save_partial_cases(self):
        self.login()
        for changes in [{'temperature': 'NaN'}, {'pulse': 'inf'}, {'pulse': '80.5'}, {'oxygen_saturation': '101'}, {'systolic_bp': '120'}, {'systolic_bp': '70', 'diastolic_bp': '90'}, {'chief_complaint': ''}, {'status': 'Invented'}]:
            response = self.post('/cases/new/PAT0001', {'chief_complaint': 'Invalid', 'status': 'Active', **changes})
            self.assertEqual(response.status_code, 422, changes)
        self.assertEqual(self.post('/cases/1/vitals', {}).status_code, 422)
        with self.app.app_context():
            self.assertEqual(get_connection().execute('SELECT COUNT(*) FROM cases').fetchone()[0], 15)

    def test_database_rejects_mismatched_patient_and_case(self):
        with self.app.app_context():
            connection = get_connection()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO vitals (patient_id,case_id,pulse) VALUES ('PAT0002',1,80)")
            connection.rollback()

    def test_login_throttle(self):
        for attempt in range(5):
            self.assertEqual(self.post('/login', {'email': 'wrong@example.com', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.post('/login', {'email': 'wrong@example.com', 'password': 'wrong'}).status_code, 429)


if __name__ == '__main__':
    unittest.main()
