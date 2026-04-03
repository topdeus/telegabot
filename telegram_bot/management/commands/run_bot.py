from django.core.management.base import BaseCommand
from django.core.management import call_command
from telegram_bot.bot_logic import bot
import threading
import time

def reminder_loop():
    while True:
        try:
            call_command('run_reminders')
        except Exception as e:
            pass # Игнорируем вывод, чтобы не спамить
        time.sleep(5) # проверяем воронку каждые 5 секунд

class Command(BaseCommand):
    help = 'Запуск бота в режиме постоянного опроса (Long Polling) для локального тестирования'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Бот успешно запущен в режиме Long Polling!'))
        
        # Запускаем фоновый поток для рассылки по воронке (замена Cron для тестов)
        t = threading.Thread(target=reminder_loop)
        t.daemon = True
        t.start()
        self.stdout.write(self.style.SUCCESS('Фоновая процессия напоминаний запущена (каждые 30 сек).'))

        # Очищаем вебхук на всякий случай
        try:
            bot.remove_webhook()
        except:
            pass
            
        # Запускаем бесконечный опрос
        bot.infinity_polling()
