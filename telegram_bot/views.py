import secrets

import telebot
from django.conf import settings
from django.http import HttpResponseForbidden
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .bot_logic import bot

@csrf_exempt
def webhook(request):
    if request.method == 'POST':
        expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
        if expected_secret:
            received_secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
            if not secrets.compare_digest(received_secret, expected_secret):
                return HttpResponseForbidden('forbidden')
        json_str = request.body.decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return HttpResponse('ok', status=200)
    else:
        return HttpResponse('Webhook is active.')
