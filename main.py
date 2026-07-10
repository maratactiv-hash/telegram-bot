import os
import json
import asyncio
import gspread
from datetime import datetime # Добавили для даты
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from google.oauth2.service_account import Credentials
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN = os.environ['TOKEN']
SPREADSHEET_ID = os.environ['SPREADSHEET_ID']

scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_KEY_JSON'])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=TOKEN)
WEBHOOK_URL = "https://ВАШЕ-ИМЯ-НА-RENDER.onrender.com/webhook"
bot.set_webhook(url=WEBHOOK_URL)
dp = Dispatcher()

# Функция для показа стартовой кнопки
async def main():
    app = web.Application()
    
    # Регистрация бота как вебхука
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    
    # Бот будет слушать порт, который дает Render
    port = int(os.environ.get("PORT", 10000))
    
    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Убираем dp.start_polling(bot) и вместо этого просто ждем
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())

@dp.callback_query(F.data == "send_req")
async def send_data(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Добавляем текущую дату/время в начало списка
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    sheet.append_row([now, data['company'], data['op_type'], data['city'], data['address'], data['date'], data['phone'], data['vehicle'], data['note']])
    
    await cb.message.answer("✅ Заявка отправлена!")
    await state.clear()
    # Возвращаем кнопку после завершения
    await show_start_button(cb.message)

# ... (остальной код с main и запуском) ...
