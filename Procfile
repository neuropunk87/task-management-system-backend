web: gunicorn task_management_system.wsgi --log-file -
worker: celery -A task_management_system worker --loglevel=info -P gevent
beat: celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler --loglevel=info
bot: gunicorn -b 0.0.0.0:$PORT notifications.telegram_bot:main --worker-class aiohttp.GunicornWebWorker
