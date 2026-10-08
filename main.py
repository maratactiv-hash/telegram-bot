import os
import json
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
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

# Постоянная клавиатура с кнопкой сброса/старта (не исчезает)
start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Начать заявку")]], 
    resize_keyboard=True, 
    is_persistent=True
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
async def cmd_start(msg: Message, state: FSMContext): 
    await state.clear()
    await msg.answer(
        "👋 Система готова. Нажмите кнопку ниже, чтобы создать заявку.", 
        reply_markup=start_kb
    )

@dp.message(F.text == "Начать заявку")
async def start_form_btn(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("1. Наименование компании:", reply_markup=start_kb)
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
    await cb.message.answer("3. Область:", reply_markup=start_kb)
    await state.set_state(ApplicationForm.city)

@dp.message(ApplicationForm.city)
async def p_city(msg: Message, state: FSMContext): 
    await state.update_data(city=msg.text)
    await msg.answer("4. Точный адрес:", reply_markup=start_kb)
    await state.set_state(ApplicationForm.address)

@dp.message(ApplicationForm.address)
async def p_addr(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    
    # Запускаем календарь через метод start_calendar без громоздких настроек, которые вызывают зависания
    now = datetime.now()
    await msg.answer(
        "5. Выберите дату (доступно начиная с завтрашнего дня):", 
        reply_markup=await SimpleCalendar().start_calendar(year=now.year, month=now.month)
    )
    await state.set_state(ApplicationForm.date)

@dp.callback_query(SimpleCalendarCallback.filter(), ApplicationForm.date)
async def p_date(cb: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(cb, callback_data)
    
    if selected:
        tomorrow_date = datetime.now().date() + timedelta(days=1)
        
        # Строгая проверка: если выбрана сегодняшняя или прошедшая дата — предупреждаем, календарь оставляем открытым
        if date.date() < tomorrow_date:
            await cb.answer("❌ Нельзя выбрать прошедшую дату или сегодняшний день! Выберите дату начиная с завтрашнего дня.", show_alert=True)
            return

        # Если дата корректная — сохраняем и переходим к следующему шагу
        await state.update_data(date=date.strftime("%d.%m.%Y"))
        await cb.message.edit_text(f"Выбрана дата: {date.strftime('%d.%m.%Y')}")
        await cb.message.answer("6. Номер телефона:", reply_markup=start_kb)
        await state.set_state(ApplicationForm.phone)

@dp.message(ApplicationForm.phone)
async def p_ph(msg: Message, state: FSMContext): 
    await state.update_data(phone=msg.text)
    await msg.answer("7. Гос.номер авто:", reply_markup=start_kb)
    await state.set_state(ApplicationForm.vehicle)

@dp.message(ApplicationForm.vehicle)
async def p_vh(msg: Message, state: FSMContext): 
    await state.update_data(vehicle=msg.text)
    await msg.answer("8. Примечание:", reply_markup=start_kb)
    await state.set_state(ApplicationForm.note)

@dp.message(ApplicationForm.note)
async def p_note(msg: Message, state: FSMContext):
    await state.update_data(note=msg.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data="send_req"),
        InlineKeyboardButton(text="❌ Нет", callback_data="cancel_req")
    ]])
    await msg.answer("Все данные верны?", reply_markup=kb)

@dp.callback_query(F.data == "cancel_req")
async def cancel_data(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Заявка отменена.", reply_markup=None)
    await cb.message.answer("Выберите действие:", reply_markup=start_kb)

@dp.callback_query(F.data == "send_req")
async def send_data(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    today = datetime.now().strftime("%d.%m.%Y")

    try:
        company_col = sheet.col_values(3)
        target_row = len(company_col) + 1

        row_data = [
            today, data.get('company'), data.get('op_type'), 
            data.get('city'), data.get('address'), data.get('date'), 
            data.get('phone'), data.get('vehicle'), data.get('note')
        ]

        sheet.update(f"B{target_row}", [row_data])
        await cb.message.edit_text("✅ Заявка успешно отправлена!", reply_markup=None)
        await cb.message.answer("Заявка принята в работу.", reply_markup=start_kb)
    except Exception as e:
        await cb.message.edit_text(f"❌ Ошибка записи в таблицу:\n<code>{e}</code>", parse_mode="HTML")
        await cb.message.answer("Попробуйте снова.", reply_markup=start_kb)

    await state.clear()

async def handle_webhook(request: web.Request):
    if request.method == "GET":
        return web.Response(text="OK")
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    return await handler(request)

async def main():
    app = web.Application()
    app.router.add_route("*", "/webhook", handle_webhook)
    setup_application(app, dp, bot=bot)
    
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
        await bot.set_webhook(webhook_url)
        
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
