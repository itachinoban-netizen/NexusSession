from aiogram import executor

import modules
from loader import vip

if __name__ == '__main__':
    print("Бот запущен")
    executor.start_polling(vip, skip_updates=True)


    