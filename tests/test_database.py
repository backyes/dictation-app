"""
数据库模块单元测试
测试 dictation_words_library 和 llm_providers 的 CRUD 操作
"""
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import (
    init_db, get_db,
    add_words, get_all_words, get_pending_words, get_right_words, get_wrong_words,
    mark_word_correct, mark_word_wrong, record_correct_answer,
    reset_word, reset_all, delete_word, clear_all_words,
    get_statistics, get_recent_history, get_word_history,
    get_all_providers, get_active_provider, get_provider_by_id,
    add_provider, update_provider, delete_provider, set_active_provider
)
from common.config import Config


class TestDatabase(unittest.TestCase):
    """测试数据库操作"""

    @classmethod
    def setUpClass(cls):
        """使用临时数据库进行测试"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.original_db_path = Config.DATABASE_PATH
        Config.DATABASE_PATH = os.path.join(cls.temp_dir, 'test_dictation.db')
        init_db()

    @classmethod
    def tearDownClass(cls):
        """清理临时数据库"""
        Config.DATABASE_PATH = cls.original_db_path
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        """每个测试前清空数据并重置自增ID"""
        conn = get_db()
        conn.execute('DELETE FROM dictation_history')
        conn.execute('DELETE FROM dictation_words_library')
        conn.execute("DELETE FROM sqlite_sequence WHERE name='dictation_words_library'")
        conn.commit()
        conn.close()

    # ==================== 单词操作测试 ====================

    def test_add_words(self):
        """测试添加单词"""
        result = add_words(['apple', 'banana', 'cherry'])
        self.assertEqual(result['added'], 3)
        self.assertEqual(result['duplicate'], 0)

        words = get_all_words()
        self.assertEqual(len(words), 3)
        self.assertEqual(words[0]['word'], 'apple')

    def test_add_duplicate_words(self):
        """测试添加重复单词"""
        add_words(['apple', 'banana'])
        result = add_words(['apple', 'cherry'])
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['duplicate'], 1)

    def test_add_words_lowercase(self):
        """测试单词自动转小写"""
        add_words(['APPLE', 'Banana'])
        words = get_all_words()
        self.assertEqual(words[0]['word'], 'apple')
        self.assertEqual(words[1]['word'], 'banana')

    def test_add_words_filter_invalid(self):
        """测试过滤无效输入（空字符串、单字母、非字母）"""
        result = add_words(['apple', '', '  ', 'a', 'banana', '123', 'hello!'])
        self.assertEqual(result['added'], 2)  # 只有 apple 和 banana

    def test_get_pending_words(self):
        """测试获取待默写单词"""
        add_words(['apple', 'banana', 'cherry'])
        words = get_all_words()
        mark_word_correct(words[0]['id'])  # 第一个标记为正确

        pending = get_pending_words()
        self.assertEqual(len(pending), 2)

    def test_get_right_words(self):
        """测试获取正确单词"""
        add_words(['apple', 'banana'])
        words = get_all_words()
        mark_word_correct(words[0]['id'])

        right = get_right_words()
        self.assertEqual(len(right), 1)
        self.assertEqual(right[0]['word'], 'apple')

    def test_get_wrong_words(self):
        """测试获取错误单词"""
        add_words(['apple', 'banana'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')

        wrong = get_wrong_words()
        self.assertEqual(len(wrong), 1)
        self.assertEqual(wrong[0]['error_count'], 1)

    def test_mark_word_correct(self):
        """测试标记正确"""
        add_words(['apple'])
        words = get_all_words()
        mark_word_correct(words[0]['id'])

        result = get_all_words()
        self.assertEqual(result[0]['status'], 'right')

    def test_mark_word_wrong(self):
        """测试标记错误"""
        add_words(['apple'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')
        mark_word_wrong(words[0]['id'], 'applee')

        result = get_all_words()
        self.assertEqual(result[0]['status'], 'wrong')
        self.assertEqual(result[0]['error_count'], 2)

    def test_record_correct_answer(self):
        """测试记录正确回答"""
        add_words(['apple'])
        words = get_all_words()
        record_correct_answer(words[0]['id'], 'apple')

        history = get_word_history(words[0]['id'])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['is_correct'], 1)

    def test_reset_word(self):
        """测试重置单词"""
        add_words(['apple'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')
        reset_word(words[0]['id'])

        result = get_all_words()
        self.assertEqual(result[0]['status'], 'pending')
        self.assertEqual(result[0]['error_count'], 0)

    def test_reset_all(self):
        """测试重置所有单词"""
        add_words(['apple', 'banana'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')
        mark_word_correct(words[1]['id'])
        reset_all()

        result = get_all_words()
        for w in result:
            self.assertEqual(w['status'], 'pending')
            self.assertEqual(w['error_count'], 0)

    def test_delete_word(self):
        """测试删除单词"""
        add_words(['apple', 'banana'])
        words = get_all_words()
        delete_word(words[0]['id'])

        result = get_all_words()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['word'], 'banana')

    def test_clear_all_words(self):
        """测试清空所有单词"""
        add_words(['apple', 'banana'])
        clear_all_words()

        result = get_all_words()
        self.assertEqual(len(result), 0)

    def test_get_statistics(self):
        """测试统计数据"""
        add_words(['apple', 'banana', 'cherry'])
        words = get_all_words()
        mark_word_correct(words[0]['id'])
        mark_word_wrong(words[1]['id'], 'bananna')

        stats = get_statistics()
        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['right'], 1)
        self.assertEqual(stats['wrong'], 1)
        self.assertEqual(stats['pending'], 1)
        self.assertEqual(stats['total_errors'], 1)

    def test_get_word_history(self):
        """测试获取单词历史"""
        add_words(['apple'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')
        record_correct_answer(words[0]['id'], 'apple')

        history = get_word_history(words[0]['id'])
        self.assertEqual(len(history), 2)

    def test_get_recent_history(self):
        """测试获取最近历史"""
        add_words(['apple', 'banana'])
        words = get_all_words()
        mark_word_wrong(words[0]['id'], 'aple')
        mark_word_wrong(words[1]['id'], 'bananna')

        recent = get_recent_history(10)
        self.assertEqual(len(recent), 2)

    def test_error_count_accumulation(self):
        """测试错误次数累加"""
        add_words(['apple'])
        words = get_all_words()
        word_id = words[0]['id']

        for i in range(5):
            mark_word_wrong(word_id, f'wrong{i}')

        result = get_all_words()
        self.assertEqual(result[0]['error_count'], 5)

    def test_word_status_flow(self):
        """测试单词状态流转: pending -> wrong -> right"""
        add_words(['apple'])
        words = get_all_words()
        word_id = words[0]['id']

        # 初始状态 pending
        self.assertEqual(get_all_words()[0]['status'], 'pending')

        # 错误后变为 wrong
        mark_word_wrong(word_id, 'aple')
        self.assertEqual(get_all_words()[0]['status'], 'wrong')

        # 正确后变为 right
        mark_word_correct(word_id)
        self.assertEqual(get_all_words()[0]['status'], 'right')


class TestLLMProviders(unittest.TestCase):
    """测试 LLM 提供商数据库操作"""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.original_db_path = Config.DATABASE_PATH
        Config.DATABASE_PATH = os.path.join(cls.temp_dir, 'test_dictation.db')
        init_db()

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH = cls.original_db_path
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        """清空提供商表"""
        conn = get_db()
        conn.execute('DELETE FROM llm_providers')
        conn.commit()
        conn.close()

    def test_add_provider(self):
        """测试添加提供商"""
        pid = add_provider(
            name='Test OpenAI',
            provider_type='openai',
            api_key='sk-test123',
            base_url='https://api.openai.com/v1',
            model='gpt-4o-mini',
            is_active=True
        )
        self.assertIsNotNone(pid)

        provider = get_provider_by_id(pid)
        self.assertEqual(provider['name'], 'Test OpenAI')
        self.assertEqual(provider['provider_type'], 'openai')

    def test_get_all_providers(self):
        """测试获取所有提供商"""
        add_provider(name='Provider1', provider_type='openai')
        add_provider(name='Provider2', provider_type='anthropic')

        providers = get_all_providers()
        self.assertGreaterEqual(len(providers), 2)

    def test_get_active_provider(self):
        """测试获取激活的提供商"""
        add_provider(name='Active', provider_type='openai', is_active=True)
        add_provider(name='Inactive', provider_type='openai', is_active=False)

        active = get_active_provider()
        self.assertIsNotNone(active)
        self.assertEqual(active['name'], 'Active')

    def test_update_provider(self):
        """测试更新提供商"""
        pid = add_provider(name='Old Name', provider_type='openai')
        update_provider(pid, name='New Name', model='gpt-4')

        provider = get_provider_by_id(pid)
        self.assertEqual(provider['name'], 'New Name')
        self.assertEqual(provider['model'], 'gpt-4')

    def test_delete_provider(self):
        """测试删除提供商"""
        pid = add_provider(name='To Delete', provider_type='openai')
        delete_provider(pid)

        provider = get_provider_by_id(pid)
        self.assertIsNone(provider)

    def test_set_active_provider(self):
        """测试激活提供商"""
        pid1 = add_provider(name='P1', provider_type='openai', is_active=True)
        pid2 = add_provider(name='P2', provider_type='openai', is_active=False)

        set_active_provider(pid2)

        active = get_active_provider()
        self.assertEqual(active['id'], pid2)

    def test_active_provider_unique(self):
        """测试激活状态唯一性"""
        pid1 = add_provider(name='P1', provider_type='openai', is_active=True)
        pid2 = add_provider(name='P2', provider_type='openai')

        # 激活第二个，第一个应该自动取消激活
        update_provider(pid2, is_active=True)

        # 检查只有一个激活
        providers = get_all_providers()
        active_count = sum(1 for p in providers if p['is_active'])
        self.assertEqual(active_count, 1)

    def test_provider_with_all_fields(self):
        """测试完整字段的提供商"""
        pid = add_provider(
            name='Full Provider',
            provider_type='anthropic',
            api_key='sk-ant-xxx',
            base_url='https://api.anthropic.com',
            model='claude-sonnet-4-20250514',
            max_tokens=2048,
            temperature=0.5,
            is_active=True
        )

        provider = get_provider_by_id(pid)
        self.assertEqual(provider['api_key'], 'sk-ant-xxx')
        self.assertEqual(provider['max_tokens'], 2048)
        self.assertEqual(provider['temperature'], 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
