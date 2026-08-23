"""
听写逻辑模块单元测试
测试填空生成、会话生成算法、答案检查等
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestClueGeneration(unittest.TestCase):
    """测试填空线索生成"""

    def setUp(self):
        """导入 generate_clue 函数"""
        from app import generate_clue
        self.generate_clue = generate_clue

    def test_short_word_two_letters(self):
        """测试2字母单词 - 只显示首字母"""
        clue = self.generate_clue('an')
        self.assertEqual(clue['length'], 2)
        self.assertEqual(clue['pattern'], 'first_only')
        # 首字母 + 空格 + 下划线
        self.assertTrue(clue['clue'].startswith('a'))

    def test_short_word_three_letters(self):
        """测试3字母单词 - 显示首尾字母"""
        clue = self.generate_clue('cat')
        self.assertEqual(clue['length'], 3)
        self.assertEqual(clue['pattern'], 'first_last')
        # 首字母 c + 中间下划线 + 尾字母 t
        self.assertTrue(clue['clue'].startswith('c'))
        self.assertTrue(clue['clue'].endswith('t'))

    def test_short_word_four_letters(self):
        """测试4字母单词 - 显示首尾字母"""
        clue = self.generate_clue('book')
        self.assertEqual(clue['length'], 4)
        self.assertEqual(clue['pattern'], 'first_last')
        self.assertTrue(clue['clue'].startswith('b'))
        self.assertTrue(clue['clue'].endswith('k'))

    def test_long_word_five_plus(self):
        """测试5字母以上单词 - 随机模式"""
        clue = self.generate_clue('apple')
        self.assertEqual(clue['length'], 5)
        self.assertIn(clue['pattern'], ['first_last', 'first_middle_last', 'scattered'])

    def test_clue_length_matches_word(self):
        """测试线索长度与单词匹配"""
        words = ['hi', 'cat', 'book', 'apple', 'banana', 'cherry', 'elephant']
        for word in words:
            clue = self.generate_clue(word)
            self.assertEqual(clue['length'], len(word))

    def test_clue_contains_underscores(self):
        """测试线索包含下划线"""
        clue = self.generate_clue('banana')
        self.assertIn('_', clue['clue'])

    def test_clue_reveals_correct_letters(self):
        """测试线索显示的字母是正确的"""
        # 多次测试以确保覆盖不同模式
        for _ in range(50):
            clue = self.generate_clue('testing')
            # 线索中显示的非下划线字符应该来自原词
            for i, char in enumerate(clue['clue'].replace(' ', '')):
                if char != '_':
                    # 找到这个字符在原词中的位置
                    self.assertIn(char, 'testing')


class TestDictationSession(unittest.TestCase):
    """测试听写会话生成算法"""

    @patch('app.get_pending_words')
    @patch('app.get_wrong_words')
    def test_session_covers_all_wrong_words(self, mock_wrong, mock_pending):
        """测试会话覆盖所有错误单词"""
        from app import api_dictation_session

        mock_wrong.return_value = [
            {'id': 1, 'word': 'apple', 'error_count': 2},
            {'id': 2, 'word': 'banana', 'error_count': 1},
        ]
        mock_pending.return_value = [
            {'id': 3, 'word': 'cherry', 'error_count': 0},
        ]

        # 模拟 Flask request context
        from app import app
        with app.test_client() as client:
            response = client.get('/api/dictation/session')
            data = response.get_json()

            self.assertTrue(data['success'])
            # 提取会话中的单词ID
            session_ids = [w['id'] for w in data['session']]

            # 确保所有错误单词都出现
            self.assertIn(1, session_ids)  # apple
            self.assertIn(2, session_ids)  # banana
            # 确保pending单词出现
            self.assertIn(3, session_ids)  # cherry

    @patch('app.get_pending_words')
    @patch('app.get_wrong_words')
    def test_high_frequency_wrong_word_appears_three_times(self, mock_wrong, mock_pending):
        """测试高频错误单词至少出现3次"""
        from app import app

        mock_wrong.return_value = [
            {'id': 1, 'word': 'apple', 'error_count': 5},  # 高频错误
        ]
        mock_pending.return_value = []

        with app.test_client() as client:
            response = client.get('/api/dictation/session')
            data = response.get_json()

            self.assertTrue(data['success'])
            # 统计 apple 出现次数
            apple_count = sum(1 for w in data['session'] if w['id'] == 1)
            self.assertGreaterEqual(apple_count, 3)

    @patch('app.get_pending_words')
    @patch('app.get_wrong_words')
    def test_empty_session(self, mock_wrong, mock_pending):
        """测试无单词时会话为空"""
        from app import app

        mock_wrong.return_value = []
        mock_pending.return_value = []

        with app.test_client() as client:
            response = client.get('/api/dictation/session')
            data = response.get_json()

            self.assertFalse(data['success'])
            self.assertIn('没有', data['message'])


class TestAnswerCheck(unittest.TestCase):
    """测试答案检查逻辑"""

    def test_correct_answer(self):
        """测试正确答案"""
        from app import app
        from database import init_db, add_words, get_all_words, clear_all_words

        with app.test_client() as client:
            # 先添加测试单词
            clear_all_words()
            add_words(['apple'])
            words = get_all_words()
            word_id = words[0]['id']

            response = client.post('/api/dictation/check', json={
                'word_id': word_id,
                'user_input': 'apple'
            })
            data = response.get_json()

            self.assertTrue(data['success'])
            self.assertTrue(data['is_correct'])
            self.assertEqual(data['correct_word'], 'apple')

    def test_incorrect_answer(self):
        """测试错误答案"""
        from app import app
        from database import add_words, get_all_words, clear_all_words

        with app.test_client() as client:
            clear_all_words()
            add_words(['banana'])
            words = get_all_words()
            word_id = words[0]['id']

            response = client.post('/api/dictation/check', json={
                'word_id': word_id,
                'user_input': 'bananna'
            })
            data = response.get_json()

            self.assertTrue(data['success'])
            self.assertFalse(data['is_correct'])
            self.assertEqual(data['correct_word'], 'banana')
            self.assertEqual(data['user_input'], 'bananna')
            # 错误时应该有 hint
            self.assertIn('hint', data)

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        from app import app
        from database import add_words, get_all_words, clear_all_words

        with app.test_client() as client:
            clear_all_words()
            add_words(['cherry'])
            words = get_all_words()
            word_id = words[0]['id']

            response = client.post('/api/dictation/check', json={
                'word_id': word_id,
                'user_input': 'CHERRY'
            })
            data = response.get_json()

            self.assertTrue(data['is_correct'])

    def test_nonexistent_word(self):
        """测试不存在的单词"""
        from app import app

        with app.test_client() as client:
            response = client.post('/api/dictation/check', json={
                'word_id': 99999,
                'user_input': 'test'
            })
            data = response.get_json()

            self.assertFalse(data['success'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
