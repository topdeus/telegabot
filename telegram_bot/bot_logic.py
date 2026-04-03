from datetime import datetime

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from django.conf import settings
from django.utils import timezone

from .models import AppSettings, BotUser, PaymentReceipt, UserPersonalReminder

bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN)
pending_reminder_data = {}

MENU_ADD_REMINDER = 'Добавить напоминание'
MENU_MY_REMINDERS = 'Мои напоминания'
MENU_DELETE_REMINDER = 'Удалить напоминание'
MENU_HELP = 'Помощь'


def send_content(chat_id, text='', media_field=None):
    if media_field:
        path_to_file = media_field.path
        with open(path_to_file, 'rb') as file_obj:
            ext = media_field.name.lower().split('.')[-1]
            if ext in ['jpg', 'jpeg', 'png', 'webp']:
                bot.send_photo(chat_id, file_obj, caption=text or None)
            elif ext in ['mp4', 'avi', 'mov']:
                bot.send_video(chat_id, file_obj, caption=text or None)
            elif ext in ['mp3', 'ogg', 'wav']:
                bot.send_audio(chat_id, file_obj, caption=text or None)
            else:
                bot.send_document(chat_id, file_obj, caption=text or None)
    elif text:
        bot.send_message(chat_id, text)


def get_settings():
    settings_obj, _ = AppSettings.objects.get_or_create(id=1)
    return settings_obj


def get_registered_user(chat_id):
    return BotUser.objects.filter(telegram_id=chat_id).first()


def require_paid_user(message):
    user = get_registered_user(message.chat.id)
    if not user:
        bot.send_message(message.chat.id, 'Сначала нажмите /start, чтобы бот создал ваш профиль.')
        return None
    if not user.has_paid:
        bot.send_message(message.chat.id, 'Личные напоминания станут доступны после подтверждения оплаты.')
        return None
    return user


def build_main_menu():
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2,
        selective=False,
        one_time_keyboard=False,
        is_persistent=True,
        input_field_placeholder='Выберите действие',
    )
    markup.row(KeyboardButton(MENU_ADD_REMINDER), KeyboardButton(MENU_MY_REMINDERS))
    markup.row(KeyboardButton(MENU_DELETE_REMINDER), KeyboardButton(MENU_HELP))
    return markup


def send_main_menu(chat_id, text):
    markup = build_main_menu()
    bot.send_message(chat_id, text)
    bot.send_message(chat_id, 'Главное меню:', reply_markup=markup)


def create_personal_reminder(user, date_part, time_part, reminder_text):
    naive_datetime = datetime.strptime(f'{date_part} {time_part}', '%d.%m.%Y %H:%M')
    remind_at = timezone.make_aware(naive_datetime, timezone.get_current_timezone())
    if remind_at <= timezone.now():
        raise ValueError('past')
    reminder = UserPersonalReminder.objects.create(user=user, text=reminder_text, remind_at=remind_at)
    return reminder, remind_at


def list_active_reminders(user, limit=10):
    return UserPersonalReminder.objects.filter(user=user, is_sent=False).order_by('remind_at')[:limit]


@bot.message_handler(commands=['start'])
def handle_start(message):
    user, _ = BotUser.objects.get_or_create(
        telegram_id=message.chat.id,
        defaults={'username': message.from_user.username},
    )
    app_settings = get_settings()

    if app_settings.check_subscription and app_settings.channel_id:
        try:
            member = bot.get_chat_member(app_settings.channel_id, message.chat.id)
            user.is_subscribed = member.status not in ['left', 'kicked']
            user.save(update_fields=['is_subscribed'])
        except Exception as exc:
            print(exc)

        if not user.is_subscribed:
            markup = InlineKeyboardMarkup()
            url = app_settings.channel_url or f"https://t.me/{app_settings.channel_id.replace('@', '')}"
            markup.add(InlineKeyboardButton('Перейти в канал', url=url))
            markup.add(InlineKeyboardButton('Я подписался', callback_data='check_sub'))
            bot.send_message(
                message.chat.id,
                'Для доступа к боту, пожалуйста, подпишитесь на наш канал.',
                reply_markup=markup,
            )
            return

    if not user.has_paid:
        text = (
            'Подписка подтверждена.\n\n'
            'Для доступа к материалам необходимо произвести оплату.\n\n'
            f'{app_settings.payment_details}\n\n'
            'После оплаты, пожалуйста, отправьте фото чека в ответ на это сообщение.'
        )
        send_main_menu(message.chat.id, text)
        return

    send_main_menu(message.chat.id, 'Доступ активен. Используйте кнопки меню внизу чата.')


@bot.message_handler(commands=['menu'])
def handle_menu_command(message):
    user = get_registered_user(message.chat.id)
    if user and user.has_paid:
        send_main_menu(message.chat.id, 'Меню открыто. Выберите нужное действие кнопками ниже.')
    elif user:
        send_main_menu(
            message.chat.id,
            'Меню открыто. Некоторые действия станут доступны после подтверждения оплаты.',
        )
    else:
        bot.send_message(message.chat.id, 'Сначала нажмите /start, чтобы бот создал ваш профиль.')


@bot.message_handler(func=lambda message: message.text == MENU_ADD_REMINDER)
def handle_add_reminder_menu(message):
    user = require_paid_user(message)
    if not user:
        return
    pending_reminder_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, 'Введите дату напоминания в формате ДД.ММ.ГГГГ')
    bot.register_next_step_handler(message, process_reminder_date_step)


def process_reminder_date_step(message):
    user = require_paid_user(message)
    if not user:
        return
    date_part = (message.text or '').strip()
    try:
        datetime.strptime(date_part, '%d.%m.%Y')
    except ValueError:
        bot.send_message(message.chat.id, 'Не понял дату. Попробуйте еще раз: ДД.ММ.ГГГГ')
        bot.register_next_step_handler(message, process_reminder_date_step)
        return

    pending_reminder_data[message.chat.id] = {'date_part': date_part}
    bot.send_message(message.chat.id, 'Теперь введите время в формате ЧЧ:ММ')
    bot.register_next_step_handler(message, process_reminder_time_step)


def process_reminder_time_step(message):
    user = require_paid_user(message)
    if not user:
        return
    time_part = (message.text or '').strip()
    try:
        datetime.strptime(time_part, '%H:%M')
    except ValueError:
        bot.send_message(message.chat.id, 'Не понял время. Попробуйте еще раз: ЧЧ:ММ')
        bot.register_next_step_handler(message, process_reminder_time_step)
        return

    pending_reminder_data.setdefault(message.chat.id, {})['time_part'] = time_part
    bot.send_message(message.chat.id, 'Напишите текст напоминания')
    bot.register_next_step_handler(message, process_reminder_text_step)


def process_reminder_text_step(message):
    user = require_paid_user(message)
    if not user:
        return
    reminder_text = (message.text or '').strip()
    if not reminder_text:
        bot.send_message(message.chat.id, 'Текст не должен быть пустым. Напишите текст напоминания.')
        bot.register_next_step_handler(message, process_reminder_text_step)
        return

    data = pending_reminder_data.pop(message.chat.id, {})
    try:
        reminder, remind_at = create_personal_reminder(user, data['date_part'], data['time_part'], reminder_text)
    except KeyError:
        bot.send_message(message.chat.id, 'Сессия создания напоминания сбилась. Нажмите "Добавить напоминание" еще раз.')
        return
    except ValueError:
        bot.send_message(message.chat.id, 'Нужно указать дату и время в будущем. Попробуйте снова через меню.')
        return

    send_main_menu(
        message.chat.id,
        f'Напоминание #{reminder.id} сохранено на {timezone.localtime(remind_at).strftime("%d.%m.%Y %H:%M")}.',
    )


@bot.message_handler(func=lambda message: message.text == MENU_MY_REMINDERS)
def handle_my_reminders_menu(message):
    handle_list_reminders(message)


@bot.message_handler(func=lambda message: message.text == MENU_DELETE_REMINDER)
def handle_delete_reminder_menu(message):
    user = require_paid_user(message)
    if not user:
        return
    reminders = list_active_reminders(user)
    if not reminders:
        send_main_menu(message.chat.id, 'У вас нет активных напоминаний для удаления.')
        return

    lines = ['Введите ID напоминания, которое нужно удалить:']
    for reminder in reminders:
        reminder_time = timezone.localtime(reminder.remind_at).strftime('%d.%m.%Y %H:%M')
        lines.append(f'#{reminder.id} - {reminder_time} - {reminder.text}')
    bot.send_message(message.chat.id, '\n'.join(lines))
    bot.register_next_step_handler(message, process_delete_reminder_step)


def process_delete_reminder_step(message):
    user = require_paid_user(message)
    if not user:
        return
    reminder_id_text = (message.text or '').strip().lstrip('#')
    if not reminder_id_text.isdigit():
        bot.send_message(message.chat.id, 'Нужен числовой ID. Нажмите "Удалить напоминание" и попробуйте снова.')
        return

    reminder_id = int(reminder_id_text)
    deleted, _ = UserPersonalReminder.objects.filter(id=reminder_id, user=user, is_sent=False).delete()
    if deleted:
        send_main_menu(message.chat.id, f'Напоминание #{reminder_id} удалено.')
    else:
        send_main_menu(message.chat.id, 'Активное напоминание с таким ID не найдено.')


@bot.message_handler(func=lambda message: message.text == MENU_HELP)
def handle_help_menu(message):
    user = get_registered_user(message.chat.id)
    if user and user.has_paid:
        send_main_menu(
            message.chat.id,
            'Используйте кнопки меню внизу чата.\n\n'
            'Команды тоже работают:\n'
            '/remind\n'
            '/my_reminders\n'
            '/cancel_reminder ID',
        )
    else:
        bot.send_message(message.chat.id, 'Сначала нажмите /start и завершите доступ, после этого появится меню.')


@bot.message_handler(commands=['remind'])
def handle_add_reminder(message):
    user = require_paid_user(message)
    if not user:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        bot.send_message(
            message.chat.id,
            'Отправьте команду в формате:\n'
            '/remind ДД.ММ.ГГГГ ЧЧ:ММ текст напоминания\n\n'
            'Пример:\n'
            '/remind 05.04.2026 14:30 Позвонить клиенту',
        )
        return

    date_part, time_part, reminder_text = parts[1], parts[2], parts[3].strip()
    if not reminder_text:
        bot.send_message(message.chat.id, 'Текст напоминания не должен быть пустым.')
        return

    try:
        reminder, remind_at = create_personal_reminder(user, date_part, time_part, reminder_text)
    except ValueError:
        bot.send_message(
            message.chat.id,
            'Не удалось сохранить напоминание. Проверьте формат даты/времени и убедитесь, что время в будущем.',
        )
        return

    send_main_menu(
        message.chat.id,
        f'Напоминание #{reminder.id} сохранено на {timezone.localtime(remind_at).strftime("%d.%m.%Y %H:%M")}.',
    )


@bot.message_handler(commands=['my_reminders'])
def handle_list_reminders(message):
    user = require_paid_user(message)
    if not user:
        return

    reminders = list_active_reminders(user)
    if not reminders:
        send_main_menu(message.chat.id, 'У вас пока нет активных личных напоминаний.')
        return

    lines = ['Ваши ближайшие напоминания:']
    for reminder in reminders:
        reminder_time = timezone.localtime(reminder.remind_at).strftime('%d.%m.%Y %H:%M')
        lines.append(f'#{reminder.id} - {reminder_time} - {reminder.text}')
    lines.append('')
    lines.append('Удалить можно кнопкой "Удалить напоминание" или командой /cancel_reminder ID')
    send_main_menu(message.chat.id, '\n'.join(lines))


@bot.message_handler(commands=['cancel_reminder'])
def handle_cancel_reminder(message):
    user = require_paid_user(message)
    if not user:
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        bot.send_message(message.chat.id, 'Используйте формат: /cancel_reminder ID')
        return

    reminder_id = int(parts[1].strip())
    deleted, _ = UserPersonalReminder.objects.filter(id=reminder_id, user=user, is_sent=False).delete()
    if deleted:
        send_main_menu(message.chat.id, f'Напоминание #{reminder_id} удалено.')
    else:
        send_main_menu(message.chat.id, 'Активное напоминание с таким ID не найдено.')


@bot.callback_query_handler(func=lambda call: call.data == 'check_sub')
def handle_check_sub(call):
    app_settings = get_settings()
    user = BotUser.objects.get(telegram_id=call.message.chat.id)

    if app_settings.check_subscription and app_settings.channel_id:
        try:
            member = bot.get_chat_member(app_settings.channel_id, call.message.chat.id)
            if member.status in ['member', 'creator', 'administrator']:
                user.is_subscribed = True
                user.save(update_fields=['is_subscribed'])
                bot.answer_callback_query(call.id, 'Подписка подтверждена!')
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text='Подписка подтверждена.',
                )
                if not user.has_paid:
                    text = (
                        'Для получения доступа необходимо произвести оплату.\n\n'
                        f'{app_settings.payment_details}\n\n'
                        'После оплаты, пожалуйста, отправьте фото чека в ответ на это сообщение.'
                    )
                    bot.send_message(call.message.chat.id, text)
            else:
                bot.answer_callback_query(call.id, 'Вы еще не подписались!', show_alert=True)
        except Exception as exc:
            bot.answer_callback_query(call.id, 'Ошибка проверки. Попробуйте позже.')
            print(f'Sub check err: {exc}')


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user = BotUser.objects.get(telegram_id=message.chat.id)
        if user.has_paid:
            send_main_menu(message.chat.id, 'У вас уже есть доступ. Чек больше не требуется.')
            return

        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        from django.core.files.base import ContentFile

        receipt = PaymentReceipt(user=user)
        receipt.receipt_image.save(f'receipt_{message.chat.id}.jpg', ContentFile(downloaded_file))
        receipt.save()
        bot.send_message(message.chat.id, 'Чек успешно загружен. Ожидайте проверки администратором.')
    except BotUser.DoesNotExist:
        bot.send_message(message.chat.id, 'Нажмите /start для регистрации.')
