#!/usr/bin/env sh
set -e

python - <<'PY'
import os, time
from sqlalchemy import create_engine, text
url = os.environ.get('DATABASE_URL')
if url and url.startswith('postgresql'):
    for i in range(60):
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text('select 1'))
            print('Postgres disponível.')
            break
        except Exception as exc:
            if i == 59:
                raise
            print(f'Aguardando Postgres... {exc}')
            time.sleep(1)
PY

alembic upgrade head
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python scripts/seed_demo.py
fi
exec uvicorn ui.api:app --host 0.0.0.0 --port 8000
