import os
import json
import asyncio
import gspread
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from google.oauth2.service_account import Credentials
from aiohttp import web

# --- НАСТРОЙКИ ---
TOKEN = os.environ['TOKEN']
SPREADSHEET_ID = os.environ['SPREADSHEET_ID']

# Авторизация Google
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_KEY_JSON'])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРА ---
start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Начать заявку")]],
    resize_keyboard=True
)

# --- СОСТОЯНИЯ ---
class ApplicationForm(StatesGroup):
    company = State(); op_type = State(); city = State()
    address = State(); date = State(); phone = State() # Вернули date
    vehicle = State(); note = State()    

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def start(msg: Message):
    # При старте бот "забывает" старый контекст, если пользователь решил начать заново
    await msg.answer("👋 Добро пожаловать!\n\nИспользуйте кнопку ниже, чтобы оформить новую заявку.", reply_markup=start_kb)

@dp.message(F.text == "Начать заявку")
async def start_form(msg: Message, state: FSMContext):
    await state.clear() # Полный сброс предыдущей заявки
    await msg.answer("1. Наименование компании:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ApplicationForm.company)

@dp.message(ApplicationForm.company)
async def p_comp(msg: Message, state: FSMContext):
    await state.update_data(company=msg.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Снятие пломбы", callback_data="op_remove")],
        [InlineKeyboardButton(text="Наложение пломбы", callback_data="op_add")]
    ])
    await msg.answer("2. Тип операции:", reply_markup=kb); await state.set_state(ApplicationForm.op_type)

@dp.callback_query(ApplicationForm.op_type)
async def p_type(cb: CallbackQuery, state: FSMContext):
    op = "Снятие навигационной пломбы" if cb.data == "op_remove" else "Наложение навигационной пломбы"
    await state.update_data(op_type=op)
    await cb.message.answer("3. Город:"); await state.set_state(ApplicationForm.city)

@dp.message(ApplicationForm.city)
async def p_city(msg: Message, state: FSMContext):
    await state.update_data(city=msg.text); await msg.answer("4. Точный адрес:"); await state.set_state(ApplicationForm.address)

@dp.message(ApplicationForm.address)
async def p_addr(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    # Вызываем календарь
    await msg.answer("5. Выберите дату:", reply_markup=await SimpleCalendar().start_calendar())
    await state.set_state(ApplicationForm.date)

@dp.callback_query(SimpleCalendarCallback.filter(), ApplicationForm.date)
async def p_date(cb: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(cb, callback_data)
    if selected:
        await state.update_data(date=date.strftime("%d.%m.%Y"))
        await cb.message.answer("6. Номер телефона:"); await state.set_state(ApplicationForm.phone)

@dp.message(ApplicationForm.phone)
async def p_ph(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text); await msg.answer("7. Гос.номер авто:"); await state.set_state(ApplicationForm.vehicle)

@dp.message(ApplicationForm.vehicle)
async def p_vh(msg: Message, state: FSMContext):
    await state.update_data(vehicle=msg.text); await msg.answer("8. Примечание:"); await state.set_state(ApplicationForm.note)

@dp.message(ApplicationForm.note)
async def p_note(msg: Message, state: FSMContext):
    await state.update_data(note=msg.text)
    # Кнопки "Да" и "Нет"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data="send_req"),
            InlineKeyboardButton(text="❌ Нет", callback_data="cancel_req")
        ]
    ])
    await msg.answer("Все данные верны?", reply_markup=kb)

@dp.callback_query(F.data == "cancel_req")
async def cancel_data(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    # Редактируем старое сообщение, убирая кнопки
    await cb.message.edit_text("❌ Заявка отменена.", reply_markup=None)
    # Принудительно отправляем новое сообщение с кнопкой "Начать заявку"
    await cb.message.answer("Вы можете начать новую заявку:", reply_markup=start_kb)

@dp.callback_query(F.data == "send_req")
async def send_data(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    today = datetime.now().strftime("%d.%m.%Y")
    
    # Порядок столбцов: Дата заявки | Компания | Тип | Город | Адрес | Выбранная Дата | Телефон | Авто | Примечание
    sheet.append_row([
        today, 
        data.get('company'), 
        data.get('op_type'), 
        data.get('city'), 
        data.get('address'), 
        data.get('date'),    # <--- Вот она, ваша выбранная дата!
        data.get('phone'), 
        data.get('vehicle'), 
        data.get('note')
    ])
    
    await cb.message.edit_text("✅ Заявка успешно отправлена!", reply_markup=None)
    await cb.message.answer("Хотите оформить еще одну?", reply_markup=start_kb)
    await state.clear()

# --- ЗАПУСК ---
async def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Режим поллинга для надежности получения сообщений
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
