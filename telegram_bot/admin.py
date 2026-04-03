from django import forms
from django.contrib import admin

from .bot_logic import bot, send_main_menu
from .models import AppSettings, BotUser, MessageStep, PaymentReceipt, SystemDailyReminder, UserPersonalReminder


class TimePickerAdminForm(forms.ModelForm):
    send_time = forms.TimeField(
        widget=forms.TimeInput(format='%H:%M', attrs={'type': 'time', 'step': 60}),
        input_formats=['%H:%M', '%H:%M:%S'],
    )

    class Meta:
        model = SystemDailyReminder
        fields = '__all__'


@admin.register(SystemDailyReminder)
class SystemDailyReminderAdmin(admin.ModelAdmin):
    list_display = ('text', 'send_time')
    form = TimePickerAdminForm

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault('send_time', '09:00')
        return initial


@admin.register(UserPersonalReminder)
class UserPersonalReminderAdmin(admin.ModelAdmin):
    list_display = ('user', 'text', 'remind_at', 'is_sent')
    list_filter = ('is_sent',)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not AppSettings.objects.exists()


@admin.register(MessageStep)
class MessageStepAdmin(admin.ModelAdmin):
    list_display = ('order', 'short_text', 'delay_minutes', 'has_media')

    def short_text(self, obj):
        return obj.text[:50] + '...' if obj.text else 'Без текста'

    short_text.short_description = 'Текст'

    def has_media(self, obj):
        return bool(obj.media)

    has_media.short_description = 'Есть медиа?'
    has_media.boolean = True


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'is_subscribed', 'has_paid', 'current_step', 'next_step_time')
    list_filter = ('is_subscribed', 'has_paid')
    search_fields = ('telegram_id', 'username')


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at', 'image_preview')
    list_filter = ('status',)

    from django.utils.html import format_html

    def image_preview(self, obj):
        if obj.receipt_image:
            try:
                return self.format_html(
                    '<a href="{0}" target="_blank"><img src="{0}" width="50" height="50" style="object-fit:cover; border-radius:5px;" /></a>',
                    obj.receipt_image.url,
                )
            except Exception:
                return 'Нет файла'
        return 'Нет фото'

    image_preview.short_description = 'Чек'

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            if obj.status == 'approved':
                obj.user.has_paid = True
                should_start_funnel = obj.user.current_step_id is None and obj.user.next_step_time is None
                obj.user.save()
                try:
                    send_main_menu(
                        obj.user.telegram_id,
                        'Чек одобрен, доступ открыт. Используйте кнопки меню внизу чата.',
                    )

                    first_step = MessageStep.objects.order_by('order').first()
                    if first_step and should_start_funnel:
                        from datetime import timedelta
                        from django.utils import timezone

                        obj.user.current_step = first_step
                        if first_step.exact_time:
                            local_now = timezone.localtime(timezone.now())
                            scheduled_local = local_now.replace(
                                hour=first_step.exact_time.hour,
                                minute=first_step.exact_time.minute,
                                second=first_step.exact_time.second,
                                microsecond=0,
                            ) + timedelta(days=first_step.days_delay)
                            if scheduled_local <= local_now:
                                scheduled_local += timedelta(days=1)
                            obj.user.next_step_time = timezone.make_aware(
                                scheduled_local.replace(tzinfo=None),
                                timezone.get_current_timezone(),
                            )
                        elif first_step.delay_minutes == 0:
                            obj.user.next_step_time = timezone.now()
                        else:
                            obj.user.next_step_time = timezone.now() + timedelta(minutes=first_step.delay_minutes)
                        obj.user.save()
                except Exception as exc:
                    print(f'Error sending message to {obj.user.telegram_id}: {exc}')

            elif obj.status == 'rejected':
                try:
                    bot.send_message(
                        obj.user.telegram_id,
                        'Ваш чек отклонен. Попробуйте еще раз или свяжитесь с поддержкой.',
                    )
                except Exception:
                    pass
        super().save_model(request, obj, form, change)
