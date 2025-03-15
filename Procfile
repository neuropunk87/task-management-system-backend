web: gunicorn task_management_system.wsgi --log-file -
worker: celery -A task_management_system worker --loglevel=info -P gevent
beat: celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler --loglevel=info
bot: python notifications/telegram_bot.py
