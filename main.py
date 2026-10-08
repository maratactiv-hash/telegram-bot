import os
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from google.oauth2.service_account import Credentials
import gspread
from aiohttp import web

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('TOKEN')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL', '')

# Безопасная загрузка ключа Google с защитой от сбоев экранирования в Render
raw_key = os.environ.get('GOOGLE_KEY_JSON', '{}')
try:
    creds_dict = json.loads(raw_key)
except json.JSONDecodeError:
    fixed_key = raw_key.replace('\\n', '\n')
    creds_dict = json.loads(fixed_key)

creds = Credentials.from_service_account_info(
    creds_dict, 
    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=TOKEN)
dp = Dispatcher()

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Начать заявку")]], 
    resize_keyboard=True, 
    one_time_keyboard=False
)

class ApplicationForm(StatesGroup):
    company = State()
    op_type = State()
    city = State()
    address = State()
    date = State()
    phone = State()
    vehicle = State()
    note = State()    

@dp.message(Command("start"))
async def start(msg: Message): 
    await msg.answer("👋 Система готова. Нажмите кнопку ниже, чтобы создать заявку.", reply_markup=start_kb)

@dp.message(F.text == "Начать заявку")
async def start_form(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("1. Наименование компании:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ApplicationForm.company)

@dp.message(ApplicationForm.company)
async def p_comp(msg: Message, state: FSMContext):
    await state.update_data(company=msg.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снятие пломбы", callback_data="op_remove")],
        [InlineKeyboardButton(text="Наложение пломбы", callback_data="op_add")]
    ])
    await msg.answer("2. Тип операции:", reply_markup=kb)
    await state.set_state(ApplicationForm.op_type)

@dp.callback_query(ApplicationForm.op_type)
async def p_type(cb: CallbackQuery, state: FSMContext):
    op = "Снятие навигационной пломбы" if cb.data == "op_remove" else "Наложение навигационной пломбы"
    await state.update_data(op_type=op)
    await cb.message.answer("3. Область:")
    await state.set_state(ApplicationForm.city)

@dp.message(ApplicationForm.city)
async def p_city(msg: Message, state: FSMContext): 
    await state.update_data(city=msg.text)
    await msg.answer("4. Точный адрес:")
    await state.set_state(ApplicationForm.address)

@dp.message(ApplicationForm.address)
async def p_addr(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    
    # Ограничение: выбрать можно только даты начиная с завтрашнего дня
    tomorrow = datetime.now() + timedelta(days=1)
    
    await msg.answer(
        "5. Выберите дату (доступно с завтрашнего дня):", 
        reply_markup=await SimpleCalendar().start_calendar(min_date=tomorrow)
    )
    await state.set_state(ApplicationForm.date)

@dp.callback_query(SimpleCalendarCallback.filter(), ApplicationForm.date)
async def p_date(cb: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(cb, callback_data)
    if selected:
        # Дополнительная проверка на бэкенде
        tomorrow_date = datetime.now().date() + timedelta(days=1)
        if date.date() < tomorrow_date:
            await cb.answer("❌ Нельзя выбрать прошедшую дату или сегодняшний день!", show_alert=True)
            return

        await state.update_data(date=date.
