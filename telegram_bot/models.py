from django.db import models
from django.utils import timezone



class AppSettings(models.Model):
    check_subscription = models.BooleanField("Проверять подписку", default=False)
    channel_id = models.CharField("ID канала или юзернейм (@channel)", max_length=100, blank=True)
    channel_url = models.URLField("Ссылка на канал", blank=True, help_text="Для кнопки 'Перейти в канал'")
    payment_details = models.TextField("Реквизиты для оплаты", blank=True)
    
    class Meta:
        verbose_name = "Настройки бота"
        verbose_name_plural = "Настройки бота"

    def __str__(self):
        return "Основные настройки"

    def save(self, *args, **kwargs):
        self.pk = 1
        super(AppSettings, self).save(*args, **kwargs)

class MessageStep(models.Model):
    order = models.PositiveIntegerField("Порядок шага", unique=True, help_text="1 - первое сообщение, 2 - второе и т.д.")
    text = models.TextField("Текст сообщения", blank=True)
    media = models.FileField("Медиафайл (Фото/Видео/Аудио/Документ)", upload_to='steps/', blank=True, null=True)
    delay_minutes = models.PositiveIntegerField("Задержка перед отправкой (в минутах)", default=0, help_text="0 - отправить сразу. (Игнорируется, если задано Точное время)")
    exact_time = models.TimeField("Точное время отправки", blank=True, null=True, help_text="Если указано, бот проигнорирует задержку в минутах и отправит сообщение ровно в это время.")
    days_delay = models.PositiveIntegerField("Через сколько дней (для точного времени)", default=0, help_text="0 = в этот же день, 1 = на следующий день после предыдущего шага.")

    class Meta:
        verbose_name = "Шаг воронки"
        verbose_name_plural = "Цепочка сообщений (Воронка)"
        ordering = ['order']

    def __str__(self):
        return f"Шаг {self.order}: {self.text[:30]}..."

class BotUser(models.Model):
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    username = models.CharField("Юзернейм", max_length=100, blank=True, null=True)
    is_subscribed = models.BooleanField("Подписан на канал?", default=False)
    has_paid = models.BooleanField("Оплатил доступ?", default=False)
    current_step = models.ForeignKey(MessageStep, on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name="Текущий шаг")
    next_step_time = models.DateTimeField("Время следующего сообщения", null=True, blank=True)

    class Meta:
        verbose_name = "Пользователь бота"
        verbose_name_plural = "Пользователи бота"

    def __str__(self):
        return f"{self.username or self.telegram_id}"

class PaymentReceipt(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает проверки'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    )
    user = models.ForeignKey(BotUser, on_delete=models.CASCADE, verbose_name="Пользователь")
    receipt_image = models.FileField("Скриншот чека", upload_to='receipts/')
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        verbose_name = "Квитанция об оплате"
        verbose_name_plural = "Квитанции об оплате"

    def __str__(self):
        return f"Чек от {self.user} ({self.get_status_display()})"

class SystemDailyReminder(models.Model):
    text = models.TextField("Текст напоминания", blank=True)
    media = models.FileField("Медиафайл (Фото/Видео/Документ)", upload_to='reminders/', blank=True, null=True)
    send_time = models.TimeField("Время ежедневной отправки")

    class Meta:
        verbose_name = "Системное напоминание"
        verbose_name_plural = "Системные ежедневные напоминания (Для всех)"
        ordering = ['send_time']
    
    def __str__(self):
        return f"Ежедневная рассылка в {self.send_time}"

class SystemReminderLog(models.Model):
    user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    reminder = models.ForeignKey(SystemDailyReminder, on_delete=models.CASCADE)
    date_sent = models.DateField("Дата отправки")
    
    class Meta:
        unique_together = ('user', 'reminder', 'date_sent')

class UserPersonalReminder(models.Model):
    user = models.ForeignKey(BotUser, on_delete=models.CASCADE, verbose_name="Пользователь")
    text = models.TextField("Текст напоминания")
    remind_at = models.DateTimeField("Когда напомнить")
    is_sent = models.BooleanField("Отправлено", default=False)
    
    class Meta:
        verbose_name = "Личное напоминание пользователя"
        verbose_name_plural = "Личные напоминания от пользователей"

    def __str__(self):
        return f"Напоминание для {self.user} на {self.remind_at}"
