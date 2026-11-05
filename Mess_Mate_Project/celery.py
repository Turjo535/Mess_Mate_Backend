
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Mess_Mate_Project.settings')

app = Celery('Mess_Mate_Project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()