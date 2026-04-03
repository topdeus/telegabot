from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta

from telegram_bot.bot_logic import send_content
from telegram_bot.models import (
    BotUser,
    MessageStep,
    SystemDailyReminder,
    SystemReminderLog,
    UserPersonalReminder,
)

class Command(BaseCommand):
    help = 'Запуск рассылки напоминаний по воронке'

    def handle(self, *args, **options):
        now = timezone.now()

        users = BotUser.objects.filter(
            has_paid=True,
            current_step__isnull=False,
            next_step_time__lte=now
        )
        
        for user in users:
            step = user.current_step
            self.send_step(user.telegram_id, step)

            next_step = MessageStep.objects.filter(order__gt=step.order).order_by('order').first()
            if next_step:
                user.current_step = next_step
                user.next_step_time = self.calculate_step_time(now, next_step)
                user.save()
            else:
                user.current_step = None
                user.next_step_time = None
                user.save()

        self.send_system_reminders(now)
        self.send_personal_reminders(now)

        self.stdout.write(self.style.SUCCESS('Успешно завершена проверка рассылок'))

    def calculate_step_time(self, base_time, step):
        if step.exact_time:
            local_base = timezone.localtime(base_time)
            scheduled_local = datetime.combine(
                local_base.date() + timedelta(days=step.days_delay),
                step.exact_time,
            )
            scheduled = timezone.make_aware(scheduled_local, timezone.get_current_timezone())
            if scheduled <= base_time:
                scheduled += timedelta(days=1)
            return scheduled
        return base_time + timedelta(minutes=step.delay_minutes)

    def send_step(self, chat_id, step):
        try:
            send_content(chat_id, step.text, step.media)
        except Exception as e:
            print(f"Failed to send step to {chat_id}: {e}")

    def send_system_reminders(self, now):
        current_time = timezone.localtime(now).time().replace(second=0, microsecond=0)
        current_date = timezone.localdate(now)
        reminders = SystemDailyReminder.objects.filter(send_time=current_time)
        if not reminders.exists():
            return

        users = BotUser.objects.filter(has_paid=True)
        for reminder in reminders:
            for user in users:
                already_sent = SystemReminderLog.objects.filter(
                    user=user,
                    reminder=reminder,
                    date_sent=current_date,
                ).exists()
                if already_sent:
                    continue
                try:
                    send_content(user.telegram_id, reminder.text, reminder.media)
                    SystemReminderLog.objects.create(
                        user=user,
                        reminder=reminder,
                        date_sent=current_date,
                    )
                except Exception as e:
                    print(f"Failed to send system reminder {reminder.id} to {user.telegram_id}: {e}")

    def send_personal_reminders(self, now):
        reminders = UserPersonalReminder.objects.filter(is_sent=False, remind_at__lte=now).select_related('user')
        for reminder in reminders:
            try:
                send_content(reminder.user.telegram_id, reminder.text)
                reminder.is_sent = True
                reminder.save(update_fields=['is_sent'])
            except Exception as e:
                print(f"Failed to send personal reminder {reminder.id} to {reminder.user.telegram_id}: {e}")
