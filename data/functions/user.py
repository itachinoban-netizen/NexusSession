import sqlite3
from datetime import datetime


class User:
    user_id: int

    def __init__(self, user_id: int = None) -> None:
        self._sql_path = './/data//database.db'

        self.conn = sqlite3.connect(database=self._sql_path)
        self.cursor = self.conn.cursor()

        if user_id is not None:
            self.cursor.execute(
                'SELECT * FROM users WHERE user_id = ?', [user_id]
            )
            user = self.cursor.fetchone()

            self.user_id = user[0]
            self.username = user[1]
            self.phone = user[2]
            self.date = user[3]

    def join_users(self, user_id: int, username: str) -> bool:
        """
        Запись пользователя в базу данных
        :param user_id: int
        :param username: str
        :return status: bool
        """
        status = False
        self.cursor.execute(
            "SELECT * FROM users WHERE user_id = ?", [user_id]
        )
        row = self.cursor.fetchall()

        if len(row) == 0:
            user_data = [user_id, f"{username}", 'NOT', datetime.now()]
            self.cursor.execute(
                "INSERT INTO users VALUES (?,?,?,?)", user_data
            )
            self.conn.commit()

            status = True

        return status

    def update_phone(self, phone: str) -> bool:
        """
        Запись пользователя в базу данных
        :param phone: int
        :return: bool
        """
        self.cursor.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?", [phone, self.user_id]
        )
        self.conn.commit()

        return True
















