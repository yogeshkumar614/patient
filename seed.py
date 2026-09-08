from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from database import generate_patient_id, get_connection, insert_record


def seed_data():
    connection = get_connection()
    with connection:
        connection.execute('BEGIN IMMEDIATE')
        user = connection.execute('SELECT user_id FROM users WHERE email=?', ('doctor@medicase.demo',)).fetchone()
        if user is None:
            doctor_id = insert_record(connection, 'users', {'email': 'doctor@medicase.demo', 'name': 'Dr. Meera', 'password_hash': generate_password_hash('demo123')})
        else:
            doctor_id = user['user_id']
        if connection.execute('SELECT COUNT(*) FROM patients').fetchone()[0]:
            return
        names = [('Rahul', 'Sharma', '2003-05-15', 'Male', 'B+'), ('Priya', 'Verma', '1998-11-22', 'Female', 'O+'), ('Ravi', 'Kumar', '1995-02-08', 'Male', 'A+'), ('Ananya', 'Singh', '2001-07-19', 'Female', 'AB+'), ('Arjun', 'Patel', '1987-03-12', 'Male', 'O-'), ('Neha', 'Joshi', '1992-09-04', 'Female', 'B-'), ('Kabir', 'Mehta', '1975-06-28', 'Male', 'A-'), ('Ishita', 'Rao', '2005-12-10', 'Female', 'O+'), ('Aarav', 'Gupta', '2016-04-23', 'Male', 'B+'), ('Sana', 'Khan', '1984-10-30', 'Female', 'AB-')]
        complaints = ['Fever and headache', 'Persistent cough', 'Routine follow-up', 'Seasonal allergy symptoms', 'Knee discomfort']
        patient_ids = []
        now = datetime.now(timezone.utc)
        for index, (first, last, birthday, gender, blood) in enumerate(names):
            patient_id = generate_patient_id(connection)
            patient_ids.append(patient_id)
            insert_record(connection, 'patients', {
                'patient_id': patient_id, 'first_name': first, 'last_name': last,
                'date_of_birth': birthday, 'gender': gender, 'phone': f'90000000{index:02d}',
                'email': f'{first.lower()}@example.com', 'address': 'Demo address, Dehradun, Uttarakhand',
                'blood_group': blood, 'emergency_contact': f'90000100{index:02d}',
                'allergies': 'Dust allergy (fictional demo)' if index == 1 else 'No known allergies reported (fictional demo)',
                'created_at': (now - timedelta(days=10-index)).strftime('%Y-%m-%d %H:%M:%S'),
            })
        for index in range(15):
            patient_id = patient_ids[index % 10]
            visit = (now - timedelta(days=14-index)).strftime('%Y-%m-%d %H:%M:%S')
            case_id = insert_record(connection, 'cases', {
                'patient_id': patient_id, 'chief_complaint': complaints[index % 5], 'duration': '3 days' if index % 5 < 2 else 'Follow-up visit',
                'history_of_present_illness': 'Fictional demonstration: patient describes symptoms and their progression since the previous visit.',
                'past_medical_history': 'History reviewed with the patient. Demo record only.',
                'surgical_history': 'No previous surgery reported.', 'family_history': 'Not recorded.',
                'personal_history': 'Routine and activity discussed during consultation.',
                'allergies': 'Dust allergy reported.' if index % 10 == 1 else 'No known allergies reported.',
                'current_medications': 'Medication history reviewed by the clinician.',
                'examination': 'Example examination notes entered by the care team.',
                'diagnosis': 'Assessment pending clinician review. Fictional case.',
                'treatment_plan': 'Care plan to be documented by the treating clinician.',
                'doctor_notes': 'Synthetic demonstration record; not medical advice.',
                'status': 'Closed' if index % 3 == 0 else 'Active', 'doctor_id': doctor_id, 'visit_date': visit,
            })
            insert_record(connection, 'vitals', {
                'patient_id': patient_id, 'case_id': case_id, 'temperature': 101.2 if index % 5 == 0 else 98.6,
                'pulse': 78 + index % 15, 'respiratory_rate': 18, 'systolic_bp': 120, 'diastolic_bp': 80,
                'oxygen_saturation': 98, 'weight': 68.5 if index % 10 != 8 else 30,
                'height': 172 if index % 10 != 8 else 135, 'recorded_at': visit,
            })


if __name__ == '__main__':
    from app import create_app
    with create_app().app_context():
        seed_data()
    print('Demo ready: doctor@medicase.demo / demo123')
