from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab


# Встановлення змінної оточення для налаштувань Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'task_management_system.settings')

app = Celery('task_management_system')

# Завантаження налаштування з файлу settings.py з префіксом CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматичне виявлення завдань у файлах utils.py у всіх встановлених апках Django
app.autodiscover_tasks(['task_management_system.utils'])

# Додаткові параметри
app.conf.broker_connection_retry_on_startup = True
worker_cancel_long_running_tasks_on_connection_loss = True

app.conf.beat_schedule = {
    'notify_deadlines_every_day': {
        'task': 'notifications.utils.notify_deadlines',
        'schedule': crontab(hour='9', minute='0'),
        'options': {'timezone': 'Europe/Kyiv'},
    },
    'delete_old_notifications_every_day': {
        'task': 'notifications.utils.delete_old_notifications',
        'schedule': crontab(hour='0', minute='0'),
        'options': {'timezone': 'Europe/Kyiv'},
    },
}

app.conf.enable_utc = True
app.conf.timezone = 'Europe/Kyiv'
app.conf.beat_scheduler = 'django_celery_beat.schedulers.DatabaseScheduler'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
