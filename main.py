import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv
import database as db

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_preview = State()
    waiting_for_full_photo = State()

TEXTS = {
    'ru': {
        'start': "Добро пожаловать. Полная конфиденциальность.",
        'menu_catalog': "📸 Каталог",
        'menu_vip': "💬 Живое общение (VIP)",
        'menu_ask': "❓ Задать вопрос",
        'menu_lang': "🌐 Изменить язык",
        'catalog_empty': "Каталог пока пуст.",
        'vip_online': "Автор на связи! Напиши сюда, и он ответит тебе лично.",
        'vip_offline': "Автор сейчас оффлайн. Он зайдет позже и обязательно тебе ответит.",
        'admin_menu': "👑 Панель Администратора\nВыберите действие:",
        'admin_add': "➕ Добавить товар",
        'admin_cancel': "❌ Отмена",
        'admin_cancelled': "Действие отменено. Вы в главном меню.",
        'admin_enter_name': "Введите название товара (например: Set 1):",
        'admin_enter_price': "Введите цену в рублях (только цифры):",
        'admin_enter_preview': "Отправьте фото-превью (для каталога):",
        'admin_enter_full': "Отправьте ЭКСКЛЮЗИВНОЕ фото (его увидят только после оплаты):",
        'admin_success': "Товар успешно добавлен!",
        'pay_card_text': "Для оплаты переведите {price} ₽ на карту:\n`2200 7000 0000 0000` (Сбер)\n\nПосле перевода нажмите кнопку ниже.",
        'wait_confirm': "Ожидайте подтверждения оплаты...",
        'vip_auto_reply': "Сообщение доставлено автору. Как только он выйдет в сеть, он ответит.",
        'admin_status_on': "🟢 Вы в сети.",
        'admin_status_off': "🔴 Вы оффлайн. Включен автоответ.",
        'err_photo': "Ошибка: пожалуйста, отправьте фотографию."
    }
}

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")]
    ])

def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=TEXTS['ru']['menu_catalog'])],
        [KeyboardButton(text=TEXTS['ru']['menu_vip'])],
        [KeyboardButton(text=TEXTS['ru']['menu_ask'])], 
        [KeyboardButton(text=TEXTS['ru']['menu_lang'])]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ])

# --- ГЛОБАЛЬНЫЙ СБРОС СОСТОЯНИЯ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    db.add_user(message.from_user.id, message.from_user.username)
    await message.answer(TEXTS['ru']['start'], reply_markup=get_main_menu())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return 
    await state.clear() 
    await message.answer(TEXTS['ru']['admin_menu'], reply_markup=get_admin_keyboard())

@dp.callback_query(F.data == "admin_cancel")
async def cancel_add_product(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(TEXTS['ru']['admin_cancelled'])
    await callback.answer()

# --- АДМИН ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_add")
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_name)
    await callback.message.edit_text(TEXTS['ru']['admin_enter_name'])
    await callback.answer()

@dp.message(AdminStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not message.text:
        return await message.answer("Ошибка: введите текст!")
    await state.update_data(name=message.text)
    await state.set_state(AdminStates.waiting_for_price)
    await message.answer(TEXTS['ru']['admin_enter_price'])

@dp.message(AdminStates.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await state.set_state(AdminStates.waiting_for_preview)
        await message.answer(TEXTS['ru']['admin_enter_preview'])
    except (ValueError, TypeError):
        await message.answer("Ошибка: введите только цифры!")

@dp.message(AdminStates.waiting_for_preview)
async def process_preview(message: types.Message, state: FSMContext):
    if not message.photo:
        return await message.answer(TEXTS['ru']['err_photo'])
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(AdminStates.waiting_for_full_photo)
    await message.answer(TEXTS['ru']['admin_enter_full'])

@dp.message(AdminStates.waiting_for_full_photo)
async def process_full_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        return await message.answer(TEXTS['ru']['err_photo'])
    user_data = await state.get_data()
    db.add_product(user_data['name'], user_data['price'], user_data['photo_id'], message.photo[-1].file_id)
    await message.answer(TEXTS['ru']['admin_success'], reply_markup=get_main_menu())
    await state.clear()

# --- КАТАЛОГ И ОПЛАТА ---
@dp.message(F.text == TEXTS['ru']['menu_catalog'])
async def show_catalog(message: types.Message):
    products = db.get_products()
    if not products:
        await message.answer(TEXTS['ru']['catalog_empty'])
        return
        
    for prod in products:
        prod_id, name, price, photo_id, full_photo_id = prod
        buy_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Купить за {price} ₽", callback_data=f"buy_{prod_id}")]
        ])
        await message.answer_photo(photo=photo_id, caption=f"{name} - {price} ₽", reply_markup=buy_kb)

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_choice(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    payment_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оплатить Звездами", callback_data=f"pay_stars_{product_id}")],
        [InlineKeyboardButton(text="💳 Оплатить на карту", callback_data=f"pay_card_{product_id}")]
    ])
    await callback.message.answer("Выберите удобный способ оплаты:", reply_markup=payment_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_pay_stars(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    products = db.get_products()
    product = next((p for p in products if p[0] == product_id), None)
    if not product: return await callback.answer("Товар не найден.", show_alert=True)
        
    prod_id, name, price, photo_id, full_photo_id = product
    await bot.send_invoice(
        chat_id=callback.from_user.id, title=name, description=f"Доступ: {name}",
        payload=f"product_{prod_id}", provider_token="", currency="XTR",    
        prices=[types.LabeledPrice(label=name, amount=price * 2)], start_parameter="shop"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_card_"))
async def process_pay_card(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    products = db.get_products()
    product = next((p for p in products if p[0] == product_id), None)
    if not product: return await callback.answer("Товар не найден.", show_alert=True)
        
    prod_id, name, price, photo_id, full_photo_id = product
    card_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я перевел(а)", callback_data=f"confirm_card_{prod_id}")]
    ])
    await callback.message.answer(TEXTS['ru']['pay_card_text'].format(price=price), parse_mode="Markdown", reply_markup=card_kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_card_"))
async def process_confirm_card(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    products = db.get_products()
    product = next((p for p in products if p[0] == product_id), None)
    if not product: return await callback.answer("Товар не найден.", show_alert=True)
        
    prod_id, name, price, photo_id, full_photo_id = product
    await callback.message.answer(TEXTS['ru']['wait_confirm'])
    
    user_link = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {callback.from_user.id}"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_approve_{prod_id}_{callback.from_user.id}")]
    ])
    await bot.send_message(
        chat_id=ADMIN_ID, 
        text=f"💳 **Заявка на оплату картой!**\nТовар: {name}\nСумма: {price} ₽\nКлиент: {user_link}", 
        parse_mode="Markdown", reply_markup=admin_kb
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_approve_"))
async def process_admin_approve(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    _, _, product_id, client_id = callback.data.split("_")
    product_id, client_id = int(product_id), int(client_id)
    
    products = db.get_products()
    product = next((p for p in products if p[0] == product_id), None)
    if product:
        prod_id, name, price, photo_id, full_photo_id = product
        try:
            await bot.send_message(client_id, f"✅ Оплата картой подтверждена! Твой товар: {name}")
            await bot.send_photo(client_id, photo=full_photo_id, caption="Спасибо за покупку!", protect_content=True)
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")
        await callback.message.edit_text(f"✅ Оплата подтверждена. Товар '{name}' выдан.")
    await callback.answer()

# --- VIP И ЧАТ ---
@dp.message(F.text.in_([TEXTS['ru']['menu_vip'], TEXTS['ru']['menu_ask']]))
async def handle_chat_requests(message: types.Message):
    status = db.get_status()
    if status == 'online':
        await message.answer(TEXTS['ru']['vip_online'])
    else:
        await message.answer(TEXTS['ru']['vip_offline'])
        
    user_link = f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={message.from_user.id}"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль клиента", url=user_link)]
    ])
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=f"💬 Клиент хочет пообщаться: @{message.from_user.username}", reply_markup=admin_kb)
    except Exception:
        pass

@dp.message(Command("online"))
async def cmd_online(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    db.set_status('online')
    await message.answer(TEXTS['ru']['admin_status_on'])

@dp.message(Command("offline"))
async def cmd_offline(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    db.set_status('offline')
    await message.answer(TEXTS['ru']['admin_status_off'])

# --- ОБРАБОТКА ТЕКСТА В ЧАТЕ ---
@dp.message(F.chat.type == "private", ~F.text.startswith("/"))
async def handle_messages(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    # Если пользователь в процессе добавления товара, этот обработчик НЕ РАБОТАЕТ
    if current_state is not None: return 
        
    if message.from_user.id == ADMIN_ID:
        if message.reply_to_message:
            client_id = db.get_client_by_admin_msg(message.reply_to_message.message_id)
            if client_id:
                try:
                    await bot.send_message(client_id, f"👑 **Автор:**\n{message.text}", parse_mode="Markdown")
                    await message.answer("✅ Ответ отправлен клиенту.")
                except Exception:
                    await message.answer("❌ Ошибка: клиент заблокировал бота.")
            else:
                await message.answer("❌ Не удалось найти клиента.")
        else:
            await message.answer("🤷‍♂️ Чтобы ответить клиенту, сделайте Reply на его сообщение.")
    else:
        user_link = f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={message.from_user.id}"
        try:
            admin_msg = await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"💬 **Сообщение от** @{message.from_user.username}:\n\n{message.text}",
                parse_mode="Markdown",
                reply_markup=types.ForceReply(selective=True)
            )
            db.save_chat_link(admin_msg.message_id, message.from_user.id)
            await bot.send_message(chat_id=ADMIN_ID, text=f"👤 Профиль: {user_link}", disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Ошибка: {e}")
        if db.get_status() == 'offline':
            await message.answer(TEXTS['ru']['vip_auto_reply'])

# --- ОПЛАТА ЗВЕЗДАМИ (УСПЕХ) ---
@dp.pre_checkout_query()
async def process_pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    product_id = int(message.successful_payment.invoice_payload.split("_")[1])
    products = db.get_products()
    product = next((p for p in products if p[0] == product_id), None)
    if product:
        prod_id, name, price, photo_id, full_photo_id = product
        await message.answer(f"✅ Оплата звездами прошла успешно! Твой эксклюзив: {name}")
        try: await message.answer_photo(photo=full_photo_id, caption="Спасибо за покупку!", protect_content=True)
        except: await message.answer_photo(photo=photo_id, protect_content=True)
        await bot.send_message(ADMIN_ID, text=f"💰 Новая продажа (Stars)!\nТовар: {name}\nПокупатель: @{message.from_user.username}")

@dp.message(F.text == TEXTS['ru']['menu_lang'])
async def change_language(message: types.Message):
    await message.answer("Язык изменен на русский.", reply_markup=get_main_menu())

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")