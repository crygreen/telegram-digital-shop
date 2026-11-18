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
CARD_PAYMENT_DETAILS = os.getenv('CARD_PAYMENT_DETAILS', 'ДЕМО: реквизиты не настроены')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_price_stars = State()
    waiting_for_preview = State()
    waiting_for_full_photo = State()
    waiting_for_template_name = State()
    waiting_for_template_price_rub = State()
    waiting_for_template_price_stars = State()

class CardPaymentStates(StatesGroup):
    waiting_for_receipt = State()

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
        'admin_add_template': "🧩 Добавить шаблон",
        'template_enter_name': "Введите название шаблона:",
        'template_enter_price_rub': "Введите цену в рублях (целое число):",
        'template_enter_price_stars': "Введите цену в Stars (целое число):",
        'template_saved': "Шаблон сохранён.",
        'template_invalid_price': "Введите положительное целое число.",
        'admin_cancel': "❌ Отмена",
        'admin_cancelled': "Действие отменено. Вы в главном меню.",
        'admin_enter_name': "Введите название товара (например: Set 1):",
        'admin_enter_price': "Введите цену в рублях (только цифры):",
        'admin_enter_price_stars': "Введите цену в Stars (только цифры):",
        'admin_enter_preview': "Отправьте фото-превью (для каталога):",
        'admin_enter_full': "Отправьте ЭКСКЛЮЗИВНОЕ фото (его увидят только после оплаты):",
        'admin_success': "Товар успешно добавлен!",
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
        [InlineKeyboardButton(text="🧩 Добавить шаблон", callback_data="admin_add_template")],
        [InlineKeyboardButton(text="📋 Список шаблонов", callback_data="admin_list_templates")],
        [InlineKeyboardButton(text="💳 Заявки на проверку", callback_data="admin_card_orders")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ])

def get_product_creation_keyboard(templates):
    buttons = [
        [InlineKeyboardButton(text="✍️ Свой товар", callback_data="product_custom")],
        [InlineKeyboardButton(text="📚 Выбрать шаблон", callback_data="product_choose_template")]
    ]
    for template_id, name, price_rub, price_stars in templates:
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} — {price_rub} ₽ / {price_stars}⭐",
                callback_data=f"product_template:{template_id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    templates = db.get_templates()
    await callback.message.edit_text(
        "Выберите шаблон или создайте свой товар:",
        reply_markup=get_product_creation_keyboard(templates)
    )
    await callback.answer()

@dp.callback_query(F.data == "product_custom")
async def start_custom_product(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminStates.waiting_for_name)
    await callback.message.edit_text(TEXTS['ru']['admin_enter_name'])
    await callback.answer()

@dp.callback_query(F.data == "product_choose_template")
async def choose_product_template(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    templates = db.get_templates()
    if not templates:
        return await callback.answer("Сначала добавьте шаблон.", show_alert=True)
    await callback.message.edit_text(
        "Выберите шаблон:",
        reply_markup=get_product_creation_keyboard(templates)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("product_template:"))
async def start_product_from_template(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    template_id = int(callback.data.split(":")[1])
    template = db.get_template(template_id)
    if not template:
        return await callback.answer("Шаблон не найден.", show_alert=True)
    _, name, price_rub, price_stars = template
    await state.update_data(name=name, price_rub=price_rub, price_stars=price_stars)
    await state.set_state(AdminStates.waiting_for_preview)
    await callback.message.edit_text(TEXTS['ru']['admin_enter_preview'])
    await callback.answer()

@dp.callback_query(F.data == "admin_add_template")
async def start_add_template(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    await state.set_state(AdminStates.waiting_for_template_name)
    await callback.message.edit_text(TEXTS['ru']['template_enter_name'])
    await callback.answer()

@dp.callback_query(F.data == "admin_list_templates")
async def show_templates(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    templates = db.get_templates()
    if not templates:
        await callback.message.answer("Шаблонов пока нет.")
    else:
        lines = ["Шаблоны:"]
        for template_id, name, price_rub, price_stars in templates:
            lines.append(f"{template_id}. {name} — {price_rub} ₽ / {price_stars}⭐")
        await callback.message.answer("\n".join(lines))
    await callback.answer()

@dp.message(AdminStates.waiting_for_template_name)
async def process_template_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text or not message.text.strip():
        return await message.answer("Введите название текстом.")
    await state.update_data(template_name=message.text.strip())
    await state.set_state(AdminStates.waiting_for_template_price_rub)
    await message.answer(TEXTS['ru']['template_enter_price_rub'])

@dp.message(AdminStates.waiting_for_template_price_rub)
async def process_template_price_rub(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        price_rub = int(message.text)
        if price_rub <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return await message.answer(TEXTS['ru']['template_invalid_price'])
    await state.update_data(template_price_rub=price_rub)
    await state.set_state(AdminStates.waiting_for_template_price_stars)
    await message.answer(TEXTS['ru']['template_enter_price_stars'])

@dp.message(AdminStates.waiting_for_template_price_stars)
async def process_template_price_stars(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        price_stars = int(message.text)
        if price_stars <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return await message.answer(TEXTS['ru']['template_invalid_price'])
    template_data = await state.get_data()
    db.add_template(
        template_data['template_name'],
        template_data['template_price_rub'],
        price_stars
    )
    await state.clear()
    await message.answer(TEXTS['ru']['template_saved'], reply_markup=get_main_menu())

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
        price_rub = int(message.text)
        if price_rub <= 0:
            raise ValueError
        await state.update_data(price_rub=price_rub)
        await state.set_state(AdminStates.waiting_for_price_stars)
        await message.answer(TEXTS['ru']['admin_enter_price_stars'])
    except (ValueError, TypeError):
        await message.answer("Введите положительное целое число.")

@dp.message(AdminStates.waiting_for_price_stars)
async def process_price_stars(message: types.Message, state: FSMContext):
    try:
        price_stars = int(message.text)
        if price_stars <= 0:
            raise ValueError
        await state.update_data(price_stars=price_stars)
        await state.set_state(AdminStates.waiting_for_preview)
        await message.answer(TEXTS['ru']['admin_enter_preview'])
    except (ValueError, TypeError):
        await message.answer("Введите положительное целое число.")

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
    db.add_product(
        user_data['name'],
        user_data['price_rub'],
        user_data['price_stars'],
        user_data['photo_id'],
        message.photo[-1].file_id
    )
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
        prod_id, name, price_rub, price_stars, photo_id, full_photo_id = prod
        buy_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Купить за {price_rub} ₽ / {price_stars}⭐", callback_data=f"buy_{prod_id}")]
        ])
        await message.answer_photo(photo=photo_id, caption=f"{name} — {price_rub} ₽ / {price_stars}⭐", reply_markup=buy_kb)

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
    product = db.get_product(product_id)
    if not product: return await callback.answer("Товар не найден.", show_alert=True)
        
    prod_id, name, price_rub, price_stars, photo_id, full_photo_id = product
    if price_stars is None:
        return await callback.answer("Для товара не задана цена в Stars.", show_alert=True)
    await bot.send_invoice(
        chat_id=callback.from_user.id, title=name, description=f"Доступ: {name}",
        payload=f"product_{prod_id}", provider_token="", currency="XTR",    
        prices=[types.LabeledPrice(label=name, amount=price_stars)], start_parameter="shop"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_card_"))
async def process_pay_card(callback: types.CallbackQuery):
    try:
        product_id = int(callback.data.removeprefix("pay_card_"))
    except ValueError:
        return await callback.answer("Некорректный товар.", show_alert=True)
    product = db.get_product(product_id)
    if not product:
        return await callback.answer("Товар не найден.", show_alert=True)
    try:
        order_id = db.create_card_order(callback.from_user.id, product)
    except ValueError:
        return await callback.answer("Для товара не заданы цена или файл.", show_alert=True)
    order = db.get_card_order(order_id)
    if order["status"] != "awaiting_receipt":
        return await callback.answer(f"Заявка №{order_id} уже обрабатывается.", show_alert=True)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить чек", callback_data=f"card_receipt:{order_id}")]
    ])
    await callback.answer()
    await callback.message.answer(
        f"Заявка №{order_id}\n{order['product_name']}\n"
        f"Сумма: {order['price_rub']} ₽\n"
        f"Реквизиты: {CARD_PAYMENT_DETAILS}\n"
        "После перевода приложите фото или PDF чека. Выдача — после проверки администратором.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("card_receipt:"))
async def request_card_receipt(callback: types.CallbackQuery, state: FSMContext):
    try:
        order_id = int(callback.data.split(":")[1])
    except ValueError:
        return await callback.answer("Некорректная заявка.", show_alert=True)
    order = db.get_card_order(order_id)
    if not order or order["user_id"] != callback.from_user.id:
        return await callback.answer("Заявка недоступна.", show_alert=True)
    if order["status"] != "awaiting_receipt":
        return await callback.answer("Чек уже передан на проверку.", show_alert=True)
    if await state.get_state() is not None:
        return await callback.answer("Завершите текущий ввод или отправьте /cancel.", show_alert=True)
    await state.set_state(CardPaymentStates.waiting_for_receipt)
    await state.update_data(card_order_id=order_id)
    await callback.answer()
    await callback.message.answer(f"Отправьте фото или PDF чека для заявки №{order_id}. Отмена: /cancel.")


def get_card_review_keyboard(order):
    order_id = order["id"]
    if order["status"] == "submitted":
        buttons = [
            [InlineKeyboardButton(text="Поступление проверено — выдать", callback_data=f"card_approve:{order_id}")],
            [InlineKeyboardButton(text="Отклонить", callback_data=f"card_reject:{order_id}")]
        ]
    elif order["status"] == "delivery_failed":
        buttons = [[InlineKeyboardButton(text="Повторить выдачу", callback_data=f"card_retry:{order_id}")]]
    else:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_card_order_to_admin(order):
    caption = (
        f"Заявка №{order['id']}\nТовар: {order['product_name'][:150]}\n"
        f"Сумма: {order['price_rub']} ₽\nПокупатель ID: {order['user_id']}\n"
        f"Статус: {order['status']}\n"
        "Чек сам по себе не подтверждает платёж. Сверьте поступление перед выдачей."
    )
    keyboard = get_card_review_keyboard(order)
    if order["receipt_type"] == "photo":
        await bot.send_photo(ADMIN_ID, photo=order["receipt_id"], caption=caption, reply_markup=keyboard)
    else:
        await bot.send_document(ADMIN_ID, document=order["receipt_id"], caption=caption, reply_markup=keyboard)


@dp.message(Command("cancel"))
async def cancel_current_input(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Ввод отменён. Заявка сохранена: к ней можно вернуться по кнопке отправки чека.")


@dp.message(CardPaymentStates.waiting_for_receipt)
async def receive_card_receipt(message: types.Message, state: FSMContext):
    if message.photo:
        receipt_id, receipt_type = message.photo[-1].file_id, "photo"
    elif message.document and message.document.mime_type == "application/pdf":
        if message.document.file_size and message.document.file_size > 10 * 1024 * 1024:
            return await message.answer("PDF должен быть не больше 10 МБ.")
        receipt_id, receipt_type = message.document.file_id, "document"
    else:
        return await message.answer("Нужно фото или PDF чека. Отмена: /cancel.")
    data = await state.get_data()
    order_id = data.get("card_order_id")
    if not order_id or not db.submit_card_receipt(order_id, message.from_user.id, receipt_id, receipt_type):
        await state.clear()
        return await message.answer("Заявка недоступна или чек уже принят.")
    await state.clear()
    try:
        await send_card_order_to_admin(db.get_card_order(order_id))
    except Exception:
        logging.exception("Could not notify administrator about card order %s", order_id)
        return await message.answer(f"Чек заявки №{order_id} сохранён. Уведомление задерживается; заявка доступна администратору.")
    await message.answer(f"Чек заявки №{order_id} отправлен на проверку. Товар выдаётся после подтверждения поступления.")


@dp.callback_query(F.data == "admin_card_orders")
async def show_pending_card_orders(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    await callback.answer()
    orders = db.get_pending_card_orders()
    if not orders:
        return await callback.message.answer("Заявок на проверку нет.")
    for order in orders:
        await send_card_order_to_admin(order)


@dp.callback_query(F.data.startswith("card_approve:") | F.data.startswith("card_retry:") | F.data.startswith("card_reject:"))
async def review_card_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("Нет доступа.", show_alert=True)
    try:
        action, raw_id = callback.data.split(":")
        order_id = int(raw_id)
    except ValueError:
        return await callback.answer("Некорректная заявка.", show_alert=True)
    order = db.get_card_order(order_id)
    if not order:
        return await callback.answer("Заявка не найдена.", show_alert=True)
    expected = "delivery_failed" if action == "card_retry" else "submitted"
    target = "rejected" if action == "card_reject" else "delivering"
    if not db.change_card_order_status(order_id, expected, target):
        return await callback.answer("Заявка уже обработана или сейчас выдаётся.", show_alert=True)
    await callback.answer()
    if target == "rejected":
        try:
            await bot.send_message(order["user_id"], f"Заявка №{order_id} отклонена. Свяжитесь с администратором для уточнения.")
        except Exception:
            logging.exception("Could not notify buyer about rejected order %s", order_id)
        await callback.message.answer(f"Заявка №{order_id} отклонена.")
        return
    try:
        await bot.send_photo(
            order["user_id"], photo=order["full_photo_id"],
            caption=f"Оплата заявки №{order_id} подтверждена. Спасибо за покупку!",
            protect_content=True
        )
    except Exception:
        db.change_card_order_status(order_id, "delivering", "delivery_failed")
        logging.exception("Card order delivery failed: %s", order_id)
        failed = db.get_card_order(order_id)
        await callback.message.answer(
            f"Заявка №{order_id}: не удалось подтвердить доставку. Перед повтором проверьте чат: "
            "при сетевом сбое Telegram мог уже принять файл.",
            reply_markup=get_card_review_keyboard(failed)
        )
        return
    db.change_card_order_status(order_id, "delivering", "delivered")
    await callback.message.answer(f"Заявка №{order_id}: товар выдан.")


@dp.callback_query(F.data.startswith("confirm_card_") | F.data.startswith("admin_approve_"))
async def outdated_card_button(callback: types.CallbackQuery):
    await callback.answer("Старая кнопка. Откройте актуальную заявку через каталог или меню администратора.", show_alert=True)

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
        prod_id, name, price_rub, price_stars, photo_id, full_photo_id = product
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
