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

TOKEN = os.environ['TOKEN']
SPREADSHEET_ID = os.environ['SPREADSHEET_ID']

scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_KEY_JSON'])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Функция для показа стартовой кнопки
async def main():
    app = web.Application()
    
    # Регистрация бота
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    
    # ПОЛУЧАЕМ ПОРТ ОТ RENDER
    port = int(os.environ.get("PORT", 10000)) # Используем 10000 как стандарт для Render
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"Сервер запущен на порту {port}")
    await site.start()
    
    # Запуск поллинга
    await dp.start_polling(bot)

# ... (оставляем ваши хендлеры ввода данных до отправки) ...

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
