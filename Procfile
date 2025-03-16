web: gunicorn task_management_system.wsgi --log-file - & python notifications/telegram_bot.py
worker: celery -A task_management_system worker --loglevel=info -P gevent & celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler --loglevel=info
