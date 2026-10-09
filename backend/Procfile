web: gunicorn -c gunicorn.conf.py app:app
worker: celery -A app.celery worker --loglevel=info
