import sys
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'reports'

    def ready(self):
        skip = {'migrate', 'makemigrations', 'collectstatic', 'shell',
                'test', 'seed_data', 'createsuperuser', 'check'}
        if any(cmd in sys.argv for cmd in skip):
            return
        from . import scheduler
        scheduler.start()
