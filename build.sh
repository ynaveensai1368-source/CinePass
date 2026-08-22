#!/usr/bin/env bash
# exit on error
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed_data

# Optional TMDb sync if network/API key is accessible (non-fatal if offline)
python manage.py import_tmdb_data --pages 1 || true

