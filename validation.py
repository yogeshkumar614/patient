import math
import re
from datetime import date

PATIENT_FIELDS = ['first_name', 'last_name', 'date_of_birth', 'gender', 'phone', 'email', 'address', 'blood_group', 'emergency_contact', 'allergies']
CASE_FIELDS = ['chief_complaint', 'duration', 'history_of_present_illness', 'past_medical_history', 'surgical_history', 'family_history', 'personal_history', 'allergies', 'current_medications', 'examination', 'diagnosis', 'treatment_plan', 'doctor_notes', 'status']
CASE_LABELS = {
    'chief_complaint': 'Chief complaint', 'duration': 'Duration',
    'history_of_present_illness': 'History of present illness', 'past_medical_history': 'Past medical history',
    'surgical_history': 'Surgical history', 'family_history': 'Family history', 'personal_history': 'Personal history',
    'allergies': 'Allergies', 'current_medications': 'Current medications', 'examination': 'General examination',
    'diagnosis': 'Clinician-recorded assessment', 'treatment_plan': 'Clinician-recorded care plan', 'doctor_notes': 'Doctor notes',
}
VITALS = {
    'temperature': ('Temperature', '°F', 70, 115, False),
    'pulse': ('Pulse', 'bpm', 1, 300, True),
    'respiratory_rate': ('Respiratory rate', '/min', 1, 100, True),
    'systolic_bp': ('Systolic BP', 'mmHg', 20, 300, True),
    'diastolic_bp': ('Diastolic BP', 'mmHg', 10, 200, True),
    'oxygen_saturation': ('Oxygen saturation', '%', 0, 100, False),
    'weight': ('Weight', 'kg', 0.1, 500, False),
    'height': ('Height', 'cm', 10, 260, False),
}
GENDERS = ['Female', 'Male', 'Other', 'Prefer not to say']
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']


def clean_fields(form, fields):
    return {key: form.get(key, '').strip() for key in fields}


def validate_patient(form):
    data = clean_fields(form, PATIENT_FIELDS)
    errors = {}
    for key in ['first_name', 'date_of_birth', 'phone']:
        if not data[key]:
            errors[key] = 'This field is required.'
    for key, value in data.items():
        limit = 2000 if key in ['address', 'allergies'] else 150
        if len(value) > limit:
            errors[key] = f'Use {limit} characters or fewer.'
    if data['date_of_birth']:
        try:
            birthday = date.fromisoformat(data['date_of_birth'])
            if birthday > date.today() or (date.today() - birthday).days > 130 * 366:
                errors['date_of_birth'] = 'Enter a birth date within the last 130 years.'
        except ValueError:
            errors['date_of_birth'] = 'Enter a valid date.'
    for key in ['phone', 'emergency_contact']:
        value = data[key]
        if value:
            normalized = re.sub(r'[\s().-]', '', value)
            if not re.fullmatch(r'\+?[0-9]{7,15}', normalized):
                errors[key] = 'Enter 7–15 digits, with an optional + country code.'
            else:
                data[key] = normalized
    if data['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', data['email']):
        errors['email'] = 'Enter a valid email address.'
    if data['gender'] and data['gender'] not in GENDERS:
        errors['gender'] = 'Choose a listed gender.'
    if data['blood_group'] and data['blood_group'] not in BLOOD_GROUPS:
        errors['blood_group'] = 'Choose a listed blood group.'
    return data, errors


def validate_vitals(form):
    data, errors = {}, {}
    for key, (label, unit, minimum, maximum, integer) in VITALS.items():
        raw = form.get(key, '').strip()
        data[key] = None
        if not raw:
            continue
        try:
            value = float(raw)
            if not math.isfinite(value) or not minimum <= value <= maximum or (integer and not value.is_integer()):
                raise ValueError
            data[key] = int(value) if integer else value
        except ValueError:
            errors[key] = f'Enter {minimum}–{maximum} {unit}' + (' as a whole number.' if integer else '.')
    systolic, diastolic = data['systolic_bp'], data['diastolic_bp']
    if (systolic is None) != (diastolic is None):
        errors['systolic_bp'] = 'Enter both blood pressure values, or leave both empty.'
    elif systolic is not None and systolic <= diastolic:
        errors['systolic_bp'] = 'Systolic must be greater than diastolic.'
    return data, errors


def validate_case(form):
    data = clean_fields(form, CASE_FIELDS)
    errors = {}
    if not data['chief_complaint']:
        errors['chief_complaint'] = 'Describe the reason for this visit.'
    for key, value in data.items():
        if len(value) > 5000:
            errors[key] = 'Use 5,000 characters or fewer.'
    if data['status'] not in ['Active', 'Closed']:
        errors['status'] = 'Choose Active or Closed.'
    vitals, vital_errors = validate_vitals(form)
    return data, vitals, errors | vital_errors
