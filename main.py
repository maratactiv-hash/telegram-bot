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
async def show_start_button(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Начать заявку", callback_data="start_form")]])
    await message.answer("Нажмите кнопку для оформления заявки:", reply_markup=kb)

class ApplicationForm(StatesGroup):
    company = State(); op_type = State(); city = State()
    address = State(); date = State(); phone = State()
    vehicle = State(); note = State()

@dp.message(Command("start"))
async def start(msg: Message):
    await show_start_button(msg)

@dp.callback_query(F.data == "start_form")
async def start_form(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("1. Наименование компании:"); await state.set_state(ApplicationForm.company)

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
