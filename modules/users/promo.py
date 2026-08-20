"""
Промокоды: /addpromo, /delpromo, /promos, /promo
"""
import json

from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from loader import vip, bot
from utils import config
from data import Promo

# ── Вспомогательные ─────────────────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return str(user_id) == str(config('admin_id'))


def _captcha_kb(promo_code: str) -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой открытия Mini App капчи."""
    webapp_url = config('webapp_url').rstrip('/')
    # Передаём промокод через query-параметр
    url = f'{webapp_url}/captcha?promo={promo_code}'
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True,
        keyboard=[[
            KeyboardButton(
                text='🔐 Пройти проверку',
                web_app=WebAppInfo(url=url)
            )
        ]]
    )


# ── NFT сообщение ────────────────────────────────────────────────────────────

NFT_TEXT = (
    '🎁 <b>Вам дарят NFT: JesterHat #120172</b>\n\n'
    'Учтите, что подарок можно принять только с аккаунта, '
    'на который был отправлен данный подарок. '
    'Ссылка действительна 60 минут с момента получения.\n\n'
    'https://t.me/nft/JesterHat-120172'
)

NFT_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton('Получить 🎁', url='https://t.me/FairStars_robot?start=gift')
]])


# ── Команды админа ───────────────────────────────────────────────────────────

@vip.message_handler(commands=['addpromo'])
async def cmd_addpromo(msg: Message):
    """
    /addpromo <код> <кол-во использований>
    Пример: /addpromo gift 10
    """
    if not _is_admin(msg.from_user.id):
        return

    parts = msg.text.split()
    if len(parts) != 3:
        await msg.answer(
            '❌ <b>Формат:</b> /addpromo &lt;код&gt; &lt;кол-во&gt;\n'
            'Пример: <code>/addpromo gift 10</code>'
        )
        return

    _, code, uses_str = parts
    if not uses_str.isdigit() or int(uses_str) <= 0:
        await msg.answer('❌ Кол-во использований должно быть положительным числом.')
        return

    ok = Promo().add(code=code, uses=int(uses_str), admin_id=msg.from_user.id)
    if ok:
        await msg.answer(
            f'✅ Промокод <code>{code.lower()}</code> создан на <b>{uses_str}</b> использований.'
        )
    else:
        await msg.answer(f'⚠️ Промокод <code>{code.lower()}</code> уже существует.')


@vip.message_handler(commands=['delpromo'])
async def cmd_delpromo(msg: Message):
    """
    /delpromo <код>
    """
    if not _is_admin(msg.from_user.id):
        return

    parts = msg.text.split()
    if len(parts) != 2:
        await msg.answer('❌ <b>Формат:</b> /delpromo &lt;код&gt;')
        return

    code = parts[1]
    ok = Promo().delete(code)
    if ok:
        await msg.answer(f'🗑 Промокод <code>{code.lower()}</code> удалён.')
    else:
        await msg.answer(f'⚠️ Промокод <code>{code.lower()}</code> не найден.')


@vip.message_handler(commands=['promos'])
async def cmd_promos(msg: Message):
    """Список всех промокодов (только для админа)."""
    if not _is_admin(msg.from_user.id):
        return

    rows = Promo().list_all()
    if not rows:
        await msg.answer('📭 Промокодов пока нет.')
        return

    lines = '\n'.join(
        f'• <code>{r[0]}</code> — осталось: <b>{r[1]}</b>' for r in rows
    )
    await msg.answer(f'📋 <b>Промокоды:</b>\n\n{lines}')


# ── Команда пользователя ─────────────────────────────────────────────────────

@vip.message_handler(commands=['promo'])
async def cmd_promo(msg: Message):
    """
    /promo <код>
    Проверяет промокод и открывает Mini App с капчей.
    """
    parts = msg.text.split()
    if len(parts) != 2:
        await msg.answer(
            '❌ <b>Формат:</b> /promo &lt;код&gt;\n'
            'Пример: <code>/promo gift</code>'
        )
        return

    code = parts[1].lower()
    promo = Promo()
    row = promo.get(code)

    if not row:
        await msg.answer('❌ Промокод не найден.')
        return

    _, uses_left, _ = row
    if uses_left <= 0:
        await msg.answer('❌ Этот промокод уже исчерпан.')
        return

    if promo.already_used(code, msg.from_user.id):
        await msg.answer('⚠️ Вы уже использовали этот промокод.')
        return

    await msg.answer(
        f'✅ Промокод <code>{code}</code> найден!\n\n'
        '🛡 Для получения NFT нужно пройти проверку.\n'
        '👇 Нажмите кнопку ниже:',
        reply_markup=_captcha_kb(code)
    )
