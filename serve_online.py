import os
from pathlib import Path

from waitress import serve

from app import create_app
from seed import seed_data


def online_app():
    data_directory = Path(os.environ.get('DATA_DIR', '/data'))
    data_directory.mkdir(parents=True, exist_ok=True)
    if not os.environ.get('MEDICASE_SECRET_KEY'):
        raise RuntimeError('Set MEDICASE_SECRET_KEY before starting the online server.')
    app = create_app({'DATABASE': str(data_directory / 'patient_case.db'), 'SESSION_COOKIE_SECURE': True})
    if os.environ.get('MEDICASE_DEMO') == '1':
        with app.app_context():
            seed_data()
    return app


if __name__ == '__main__':
    serve(online_app(), host='0.0.0.0', port=int(os.environ.get('PORT', '8080')))
