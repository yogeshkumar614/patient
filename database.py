import sqlite3
from pathlib import Path

from flask import current_app, g

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / 'patient_case.db'
SCHEMA = ROOT / 'schema.sql'


def get_connection():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_connection(error=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def initialize_database():
    connection = get_connection()
    connection.executescript(SCHEMA.read_text(encoding='utf-8'))
    additions = {
        'patients': {'allergies': "TEXT DEFAULT ''"},
        'cases': {
            'duration': "TEXT DEFAULT ''", 'examination': "TEXT DEFAULT ''",
            'status': "TEXT NOT NULL DEFAULT 'Active'", 'doctor_id': 'INTEGER REFERENCES users(user_id)',
            'updated_at': 'TEXT',
        },
    }
    for table, columns in additions.items():
        existing = {row['name'] for row in connection.execute(f'PRAGMA table_info({table})')}
        for column, definition in columns.items():
            if column not in existing:
                connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    maximum = connection.execute("SELECT COALESCE(MAX(CAST(SUBSTR(patient_id,4) AS INTEGER)),0) FROM patients WHERE patient_id GLOB 'PAT[0-9]*'").fetchone()[0]
    connection.execute("INSERT INTO counters VALUES ('patient',?) ON CONFLICT(name) DO UPDATE SET value=MAX(value,excluded.value)", (maximum,))
    connection.commit()


def generate_patient_id(connection):
    row = connection.execute("UPDATE counters SET value=value+1 WHERE name='patient' RETURNING value").fetchone()
    return f"PAT{row['value']:04d}"


def insert_record(connection, table, values):
    columns = ', '.join(values)
    placeholders = ', '.join('?' for key in values)
    return connection.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', tuple(values.values())).lastrowid


def update_record(connection, table, values, key, record_id):
    assignments = ', '.join(f'{column}=?' for column in values)
    connection.execute(f'UPDATE {table} SET {assignments} WHERE {key}=?', (*values.values(), record_id))
