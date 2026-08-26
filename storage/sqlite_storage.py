"""
Storage 抽象层
定义存储接口和 SQLite 实现
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import sqlite3
import os
from datetime import datetime


class StorageBackend(ABC):
    """存储后端抽象接口"""

    @abstractmethod
    def init(self):
        """初始化存储（创建表等）"""
        pass

    @abstractmethod
    def get_db(self):
        """获取数据库连接"""
        pass

    # 单词操作
    @abstractmethod
    def add_words(self, words: List[str]) -> Dict[str, int]:
        pass

    @abstractmethod
    def get_all_words(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_pending_words(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_right_words(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_wrong_words(self) -> List[Dict]:
        pass

    @abstractmethod
    def mark_word_correct(self, word_id: int):
        pass

    @abstractmethod
    def mark_word_wrong(self, word_id: int, user_input: str = ''):
        pass

    @abstractmethod
    def record_correct_answer(self, word_id: int, user_input: str = ''):
        pass

    @abstractmethod
    def reset_word(self, word_id: int):
        pass

    @abstractmethod
    def reset_all(self):
        pass

    @abstractmethod
    def delete_word(self, word_id: int):
        pass

    @abstractmethod
    def clear_all_words(self):
        pass

    @abstractmethod
    def update_word_meaning(self, word_id: int, meaning: str, example: str = '', phonetic: str = ''):
        pass

    @abstractmethod
    def get_words_without_meanings(self) -> List[Dict]:
        pass

    # 短文操作
    @abstractmethod
    def add_passage(self, title: str, content: str, words_used: List[str],
                    difficulty: str = 'intermediate', theme: str = '') -> int:
        pass

    @abstractmethod
    def get_all_passages(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_passage_by_id(self, passage_id: int) -> Optional[Dict]:
        pass

    @abstractmethod
    def delete_passage(self, passage_id: int):
        pass

    # 统计
    @abstractmethod
    def get_statistics(self) -> Dict:
        pass

    # LLM 提供商
    @abstractmethod
    def get_all_providers(self) -> List[Dict]:
        pass

    @abstractmethod
    def get_active_provider(self) -> Optional[Dict]:
        pass

    @abstractmethod
    def get_provider_by_id(self, provider_id: int) -> Optional[Dict]:
        pass

    @abstractmethod
    def add_provider(self, name: str, provider_type: str, api_key: str = '',
                     base_url: str = '', model: str = '', max_tokens: int = 1024,
                     temperature: float = 0.7, is_active: bool = False,
                     auth_token: str = '') -> int:
        pass

    @abstractmethod
    def update_provider(self, provider_id: int, **kwargs):
        pass

    @abstractmethod
    def delete_provider(self, provider_id: int):
        pass

    @abstractmethod
    def set_active_provider(self, provider_id: int):
        pass

    # 系统设置
    @abstractmethod
    def get_llm_settings(self) -> Dict:
        pass

    @abstractmethod
    def update_llm_setting(self, key: str, value: str):
        pass

    # 历史
    @abstractmethod
    def get_recent_history(self, limit: int = 50) -> List[Dict]:
        pass


class SQLiteStorage(StorageBackend):
    """SQLite 存储实现"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'dictation.db')
        self.db_path = db_path
        self.init()

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dictation_words_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                meaning TEXT DEFAULT '',
                example TEXT DEFAULT '',
                phonetic TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                error_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS passages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                words_used TEXT DEFAULT '',
                difficulty TEXT DEFAULT 'intermediate',
                theme TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT '',
                description TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        default_settings = [
            ('api_key', '', 'Anthropic API Key'),
            ('auth_token', '', 'Anthropic Auth Token (LongCat)'),
            ('base_url', 'https://api.longcat.chat/anthropic', 'API Base URL'),
            ('model', 'LongCat-2.0', 'LLM 模型名称'),
            ('max_tokens', '1024', '最大 Token 数'),
            ('temperature', '0.7', '温度参数'),
        ]
        for key, value, desc in default_settings:
            cursor.execute(
                'INSERT OR IGNORE INTO system_settings (key, value, description) VALUES (?, ?, ?)',
                (key, value, desc)
            )

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider_type TEXT NOT NULL DEFAULT 'openai',
                api_key TEXT DEFAULT '',
                auth_token TEXT DEFAULT '',
                base_url TEXT DEFAULT '',
                model TEXT DEFAULT '',
                max_tokens INTEGER DEFAULT 1024,
                temperature REAL DEFAULT 0.7,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dictation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                user_input TEXT,
                is_correct INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (word_id) REFERENCES dictation_words_library(id)
            )
        ''')

        cursor.execute('SELECT COUNT(*) FROM llm_providers')
        if cursor.fetchone()[0] == 0:
            default_providers = [
                ('Anthropic Claude', 'anthropic', '',
                 'https://api.anthropic.com', 'claude-sonnet-4-20250514', 1024, 0.7, 0),
                ('LongCat', 'anthropic', '',
                 'https://api.longcat.ai/anthropic', 'LongCat-2.0', 1024, 0.7, 1),
            ]
            for p in default_providers:
                cursor.execute('''
                    INSERT INTO llm_providers
                    (name, provider_type, api_key, base_url, model, max_tokens, temperature, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', p)

        conn.commit()

        cursor.execute("PRAGMA table_info(passages)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'theme' not in columns:
            cursor.execute("ALTER TABLE passages ADD COLUMN theme TEXT DEFAULT ''")
            conn.commit()

        conn.close()

    def add_words(self, words: List[str]) -> Dict[str, int]:
        import re
        conn = self.get_db()
        added, duplicate = 0, 0
        for word in words:
            word = word.strip().lower()
            if not word or len(word) < 2:
                continue
            if not re.match(r'^[a-z]+$', word):
                continue
            try:
                conn.execute(
                    'INSERT INTO dictation_words_library (word, status) VALUES (?, ?)',
                    (word, 'pending')
                )
                added += 1
            except sqlite3.IntegrityError:
                duplicate += 1
        conn.commit()
        conn.close()
        return {'added': added, 'duplicate': duplicate}

    def update_word_meaning(self, word_id: int, meaning: str, example: str = '', phonetic: str = ''):
        conn = self.get_db()
        conn.execute(
            'UPDATE dictation_words_library SET meaning = ?, example = ?, phonetic = ?, updated_at = ? WHERE id = ?',
            (meaning, example, phonetic, datetime.now().isoformat(), word_id)
        )
        conn.commit()
        conn.close()

    def get_words_without_meanings(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute(
            "SELECT * FROM dictation_words_library WHERE meaning = '' OR meaning IS NULL"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_all_words(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute('SELECT * FROM dictation_words_library ORDER BY id').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_pending_words(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute(
            "SELECT * FROM dictation_words_library WHERE status != 'right' ORDER BY id"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_right_words(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute(
            "SELECT * FROM dictation_words_library WHERE status = 'right' ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_wrong_words(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute(
            "SELECT * FROM dictation_words_library WHERE error_count > 0 ORDER BY error_count DESC, updated_at DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mark_word_correct(self, word_id: int):
        conn = self.get_db()
        conn.execute(
            "UPDATE dictation_words_library SET status = 'right', error_count = 0, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), word_id)
        )
        conn.commit()
        conn.close()

    def mark_word_wrong(self, word_id: int, user_input: str = ''):
        conn = self.get_db()
        conn.execute(
            """UPDATE dictation_words_library
               SET status = 'wrong', error_count = error_count + 1, updated_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), word_id)
        )
        conn.execute(
            'INSERT INTO dictation_history (word_id, user_input, is_correct) VALUES (?, ?, 0)',
            (word_id, user_input)
        )
        conn.commit()
        conn.close()

    def record_correct_answer(self, word_id: int, user_input: str = ''):
        conn = self.get_db()
        conn.execute(
            'INSERT INTO dictation_history (word_id, user_input, is_correct) VALUES (?, ?, 1)',
            (word_id, user_input)
        )
        conn.commit()
        conn.close()

    def reset_word(self, word_id: int):
        conn = self.get_db()
        conn.execute(
            "UPDATE dictation_words_library SET status = 'pending', error_count = 0, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), word_id)
        )
        conn.commit()
        conn.close()

    def reset_all(self):
        conn = self.get_db()
        conn.execute("UPDATE dictation_words_library SET status = 'pending', error_count = 0")
        conn.commit()
        conn.close()

    def delete_word(self, word_id: int):
        conn = self.get_db()
        conn.execute('DELETE FROM dictation_history WHERE word_id = ?', (word_id,))
        conn.execute('DELETE FROM dictation_words_library WHERE id = ?', (word_id,))
        conn.commit()
        conn.close()

    def clear_all_words(self):
        conn = self.get_db()
        conn.execute('DELETE FROM dictation_history')
        conn.execute('DELETE FROM dictation_words_library')
        conn.commit()
        conn.close()

    def add_passage(self, title: str, content: str, words_used: List[str],
                    difficulty: str = 'intermediate', theme: str = '') -> int:
        conn = self.get_db()
        cursor = conn.execute(
            'INSERT INTO passages (title, content, words_used, difficulty, theme) VALUES (?, ?, ?, ?, ?)',
            (title, content, ','.join(words_used), difficulty, theme)
        )
        passage_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return passage_id

    def get_all_passages(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute('SELECT * FROM passages ORDER BY created_at DESC').fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d['words_list'] = [w for w in d['words_used'].split(',') if w]
            result.append(d)
        return result

    def get_passage_by_id(self, passage_id: int) -> Optional[Dict]:
        conn = self.get_db()
        row = conn.execute('SELECT * FROM passages WHERE id = ?', (passage_id,)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            d['words_list'] = [w for w in d['words_used'].split(',') if w]
            return d
        return None

    def delete_passage(self, passage_id: int):
        conn = self.get_db()
        conn.execute('DELETE FROM passages WHERE id = ?', (passage_id,))
        conn.commit()
        conn.close()

    def get_statistics(self) -> Dict:
        conn = self.get_db()
        total = conn.execute('SELECT COUNT(*) FROM dictation_words_library').fetchone()[0]
        right = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE status = 'right'").fetchone()[0]
        wrong = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE error_count > 0").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM dictation_words_library WHERE status = 'pending'").fetchone()[0]
        total_errors = conn.execute('SELECT COALESCE(SUM(error_count), 0) FROM dictation_words_library').fetchone()[0]
        total_attempts = conn.execute('SELECT COUNT(*) FROM dictation_history').fetchone()[0]
        correct_attempts = conn.execute('SELECT COUNT(*) FROM dictation_history WHERE is_correct = 1').fetchone()[0]
        conn.close()
        return {
            'total': total,
            'right': right,
            'wrong': wrong,
            'pending': pending,
            'total_errors': total_errors,
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'accuracy': round(correct_attempts / total_attempts * 100, 1) if total_attempts > 0 else 0
        }

    def get_all_providers(self) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute('SELECT * FROM llm_providers ORDER BY is_active DESC, id ASC').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_active_provider(self) -> Optional[Dict]:
        conn = self.get_db()
        row = conn.execute('SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1').fetchone()
        conn.close()
        return dict(row) if row else None

    def get_provider_by_id(self, provider_id: int) -> Optional[Dict]:
        conn = self.get_db()
        row = conn.execute('SELECT * FROM llm_providers WHERE id = ?', (provider_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_provider(self, name: str, provider_type: str, api_key: str = '',
                     base_url: str = '', model: str = '', max_tokens: int = 1024,
                     temperature: float = 0.7, is_active: bool = False,
                     auth_token: str = '') -> int:
        conn = self.get_db()
        if is_active:
            conn.execute('UPDATE llm_providers SET is_active = 0')
        cursor = conn.execute('''
            INSERT INTO llm_providers
            (name, provider_type, api_key, auth_token, base_url, model, max_tokens, temperature, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, provider_type, api_key, auth_token, base_url, model, max_tokens, temperature,
              1 if is_active else 0, datetime.now().isoformat()))
        provider_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return provider_id

    def update_provider(self, provider_id: int, **kwargs):
        allowed_fields = {'name', 'provider_type', 'api_key', 'auth_token', 'base_url', 'model',
                          'max_tokens', 'temperature', 'is_active'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return
        if updates.get('is_active'):
            conn = self.get_db()
            conn.execute('UPDATE llm_providers SET is_active = 0 WHERE id != ?', (provider_id,))
            conn.commit()
            conn.close()
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        set_clause += ', updated_at = ?'
        values = list(updates.values()) + [datetime.now().isoformat(), provider_id]
        conn = self.get_db()
        conn.execute(f'UPDATE llm_providers SET {set_clause} WHERE id = ?', values)
        conn.commit()
        conn.close()

    def delete_provider(self, provider_id: int):
        conn = self.get_db()
        conn.execute('DELETE FROM llm_providers WHERE id = ?', (provider_id,))
        conn.commit()
        conn.close()

    def set_active_provider(self, provider_id: int):
        conn = self.get_db()
        conn.execute('UPDATE llm_providers SET is_active = 0')
        conn.execute(
            'UPDATE llm_providers SET is_active = 1, updated_at = ? WHERE id = ?',
            (datetime.now().isoformat(), provider_id)
        )
        conn.commit()
        conn.close()

    def get_llm_settings(self) -> Dict:
        provider = self.get_active_provider()
        if not provider:
            return {}
        return {
            'api_key': {'value': provider.get('api_key', ''), 'description': 'API Key'},
            'model': {'value': provider.get('model', ''), 'description': '模型名称'},
            'max_tokens': {'value': str(provider.get('max_tokens', 1024)), 'description': '最大Token数'},
            'temperature': {'value': str(provider.get('temperature', 0.7)), 'description': '温度参数'},
            'base_url': {'value': provider.get('base_url', ''), 'description': 'API Base URL'},
            'provider_type': {'value': provider.get('provider_type', 'openai'), 'description': '提供商类型'},
        }

    def update_llm_setting(self, key: str, value: str):
        provider = self.get_active_provider()
        if not provider:
            return
        field_map = {
            'api_key': 'api_key',
            'auth_token': 'auth_token',
            'model': 'model',
            'max_tokens': 'max_tokens',
            'temperature': 'temperature',
            'base_url': 'base_url',
            'provider_type': 'provider_type',
        }
        if key in field_map:
            self.update_provider(provider['id'], **{field_map[key]: value})

    def get_recent_history(self, limit: int = 50) -> List[Dict]:
        conn = self.get_db()
        rows = conn.execute(
            '''SELECT h.*, w.word FROM dictation_history h
               JOIN dictation_words_library w ON h.word_id = w.id
               ORDER BY h.created_at DESC LIMIT ?''',
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


# 全局默认实例（兼容原有接口）
_default_storage = None


def get_storage() -> SQLiteStorage:
    global _default_storage
    if _default_storage is None:
        _default_storage = SQLiteStorage()
    return _default_storage
