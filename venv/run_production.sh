#!/bin/bash
export FLASK_ENV=production
export FLASK_APP=boardapp.py
export SECRET_KEY=$(python -c 'import os; print(os.urandom(24).hex())')

# データベースディレクトリの作成
mkdir -p instance

# Gunicornでアプリケーションを起動
gunicorn --bind 127.0.0.1:3000 --workers 4 --access-logfile - --error-logfile - wsgi:app 

chmod +x venv/run_production.sh 