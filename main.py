import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
import os
import json
import gspread
from google.oauth2 import service_account
from aiohttp import web

# Добавьте эту функцию в ваш main.py
async def handle(request):
    return web.Response(text="Bot is running")

# И запустите веб-сервер вместе с ботом в функции main()
async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 8080)))
    await site.start()
    
    # И тут же запускаем бота
    await dp.start_polling(bot)
# Список необходимых областей (Scopes)
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
# НАСТРОЙКИ
TOKEN = '8822079594:AAGvB3S2Gnqvt7dg-a-GKZ9BRnA5zZBxeg0'
SPREADSHEET_ID = '107883788446408333252' #'1PXu_0hC-dHC_64KZYI0HdN7x-NxsyoUct8muHGE8f30'
#gc = gspread.service_account(filename='service_account.json')
#sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
creds_dict = json.loads(os.environ['GOOGLE_KEY_JSON'])
creds = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=SCOPES
)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(os.environ['SPREADSHEET_ID']).sheet1

bot = Bot(token=TOKEN)
dp = Dispatcher()

class ApplicationForm(StatesGroup):
    company = State(); op_type = State(); city = State()
    address = State(); date = State(); phone = State()
    vehicle = State(); note = State()

@dp.message(Command("start"))
async def start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Начать заявку", callback_data="start_form")]])
    await msg.answer("Привет! Нажми для старта:", reply_markup=kb)

@dp.callback_query(F.data == "start_form")
async def start_form(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("1. Наименование компании:"); await state.set_state(ApplicationForm.company)

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
    await state.update_data(address=msg.text); await msg.answer("5. Выберите дату:", reply_markup=await SimpleCalendar().start_calendar()); await state.set_state(ApplicationForm.date)

@dp.callback_query(SimpleCalendarCallback.filter())
async def p_date(cb: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(cb, callback_data)
    if selected:
        if date.date() < datetime.now().date() + timedelta(days=1):
            await cb.message.answer("Ошибка! Минимум завтрашний день.")
        else:
            await state.update_data(date=date.strftime("%d.%m.%Y")); await cb.message.answer("6. Номер телефона:"); await state.set_state(ApplicationForm.phone)

@dp.message(ApplicationForm.phone)
async def p_ph(msg: Message, state: FSMContext):
    await state.update_data(phone=msg.text); await msg.answer("7. Гос.номер авто:"); await state.set_state(ApplicationForm.vehicle)

@dp.message(ApplicationForm.vehicle)
async def p_vh(msg: Message, state: FSMContext):
    await state.update_data(vehicle=msg.text); await msg.answer("8. Примечание:"); await state.set_state(ApplicationForm.note)

@dp.message(ApplicationForm.note)
async def p_note(msg: Message, state: FSMContext):
    data = await state.update_data(note=msg.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отправить заявку", callback_data="send_req")]])
    await msg.answer("Все верно?", reply_markup=kb)

@dp.callback_query(F.data == "send_req")
async def send_data(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sheet.append_row([data['company'], data['op_type'], data['city'], data['address'], data['date'], data['phone'], data['vehicle'], data['note']])
    await cb.message.answer("✅ Заявка отправлена!"); await state.clear()

async def main(): await dp.start_polling(bot)
if __name__ == '__main__': asyncio.run(main())
