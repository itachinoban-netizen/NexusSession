import sqlite3
import os


class Promo:
    def __init__(self) -> None:
        self._sql_path = os.path.join('data', 'database.db')
        self.conn = sqlite3.connect(self._sql_path)
        self.cursor = self.conn.cursor()
        self._ensure_table()

    def _ensure_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promos (
                code        TEXT PRIMARY KEY,
                uses_left   INTEGER NOT NULL,
                created_by  INTEGER NOT NULL
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS promo_used (
                code    TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (code, user_id)
            )
        ''')
        self.conn.commit()

    def add(self, code: str, uses: int, admin_id: int) -> bool:
        """Создать промокод. Возвращает False если уже существует."""
        try:
            self.cursor.execute(
                'INSERT INTO promos VALUES (?, ?, ?)',
                [code.lower(), uses, admin_id]
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete(self, code: str) -> bool:
        """Удалить промокод."""
        self.cursor.execute('DELETE FROM promos WHERE code = ?', [code.lower()])
        self.cursor.execute('DELETE FROM promo_used WHERE code = ?', [code.lower()])
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get(self, code: str):
        """Вернуть (code, uses_left, created_by) или None."""
        self.cursor.execute('SELECT * FROM promos WHERE code = ?', [code.lower()])
        return self.cursor.fetchone()

    def list_all(self):
        """Список всех промокодов."""
        self.cursor.execute('SELECT code, uses_left FROM promos ORDER BY code')
        return self.cursor.fetchall()

    def already_used(self, code: str, user_id: int) -> bool:
        """Проверить использовал ли пользователь этот промокод."""
        self.cursor.execute(
            'SELECT 1 FROM promo_used WHERE code = ? AND user_id = ?',
            [code.lower(), user_id]
        )
        return self.cursor.fetchone() is not None

    def use(self, code: str, user_id: int) -> bool:
        """
        Использовать промокод.
        Возвращает True если успешно, False если промокод не найден,
        исчерпан или уже использован этим пользователем.
        """
        row = self.get(code)
        if not row:
            return False
        _, uses_left, _ = row
        if uses_left <= 0:
            return False
        if self.already_used(code, user_id):
            return False

        self.cursor.execute(
            'UPDATE promos SET uses_left = uses_left - 1 WHERE code = ?',
            [code.lower()]
        )
        self.cursor.execute(
            'INSERT INTO promo_used VALUES (?, ?)',
            [code.lower(), user_id]
        )
        self.conn.commit()
        return True
