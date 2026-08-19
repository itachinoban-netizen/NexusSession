from telethon import TelegramClient

from utils import config


class ClientTG:
    client: TelegramClient
    phone: str

    def __init__(self, phone: str = None):
        self.client = TelegramClient(
            session=f'./session/{phone[1:]}.session',
            api_id=config('api_id'),
            api_hash=config('api_hash'),
            device_model="Iphone",
            system_version="6.12.0",
            app_version="10 P (28)")

        if phone is not None:
            self.phone = phone
