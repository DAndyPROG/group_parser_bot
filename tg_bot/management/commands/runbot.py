from django.core.management.base import BaseCommand
import asyncio
from tg_bot.main import run_bot_forever
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start Telegram bot'

    def handle(self, *args, **options):
        self.stdout.write('Starting Telegram bot...')
        try:
            asyncio.run(run_bot_forever())
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('Bot stopped'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error starting bot: {e}')) 