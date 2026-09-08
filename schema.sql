PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT,
    date_of_birth TEXT,
    gender TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    blood_group TEXT,
    emergency_contact TEXT,
    allergies TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cases (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    chief_complaint TEXT NOT NULL,
    history_of_present_illness TEXT,
    past_medical_history TEXT,
    surgical_history TEXT,
    family_history TEXT,
    personal_history TEXT,
    allergies TEXT,
    current_medications TEXT,
    diagnosis TEXT,
    treatment_plan TEXT,
    doctor_notes TEXT,
    duration TEXT DEFAULT '',
    examination TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active','Closed')),
    doctor_id INTEGER REFERENCES users(user_id),
    updated_at TEXT,
    visit_date TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vitals (
    vital_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    case_id INTEGER REFERENCES cases(case_id) ON DELETE SET NULL,
    temperature REAL,
    pulse INTEGER,
    respiratory_rate INTEGER,
    systolic_bp INTEGER,
    diastolic_bp INTEGER,
    oxygen_saturation REAL,
    weight REAL,
    height REAL,
    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS google_identities (
    subject TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS login_attempts (email TEXT PRIMARY KEY, attempts INTEGER NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_patient_phone ON patients(phone);
CREATE INDEX IF NOT EXISTS idx_case_patient ON cases(patient_id);
CREATE INDEX IF NOT EXISTS idx_case_date ON cases(visit_date);
CREATE INDEX IF NOT EXISTS idx_vitals_patient ON vitals(patient_id);
CREATE INDEX IF NOT EXISTS idx_vitals_case ON vitals(case_id);
CREATE TRIGGER IF NOT EXISTS vitals_patient_insert BEFORE INSERT ON vitals
WHEN NEW.case_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cases WHERE case_id=NEW.case_id AND patient_id=NEW.patient_id)
BEGIN SELECT RAISE(ABORT, 'Case and patient must match'); END;
CREATE TRIGGER IF NOT EXISTS vitals_patient_update BEFORE UPDATE ON vitals
WHEN NEW.case_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM cases WHERE case_id=NEW.case_id AND patient_id=NEW.patient_id)
BEGIN SELECT RAISE(ABORT, 'Case and patient must match'); END;
