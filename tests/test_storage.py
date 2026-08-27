"""
Storage layer unit tests
Tests for SQLiteStorage including macOS frozen app support
"""
import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.sqlite_storage import SQLiteStorage, get_storage, StorageBackend


class TestSQLiteStorageInit(unittest.TestCase):
    """Test storage initialization"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_tables(self):
        """Init should create all required tables"""
        storage = SQLiteStorage(db_path=self.db_path)
        conn = storage.get_db()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        self.assertIn('dictation_words_library', tables)
        self.assertIn('passages', tables)
        self.assertIn('system_settings', tables)
        self.assertIn('llm_providers', tables)
        self.assertIn('dictation_history', tables)
        conn.close()

    def test_init_creates_default_providers(self):
        """Init should create default LLM providers"""
        storage = SQLiteStorage(db_path=self.db_path)
        providers = storage.get_all_providers()
        self.assertGreaterEqual(len(providers), 2)

    def test_init_creates_default_settings(self):
        """Init should create default system settings"""
        storage = SQLiteStorage(db_path=self.db_path)
        settings = storage.get_llm_settings()
        self.assertIn('api_key', settings)
        self.assertIn('model', settings)


class TestSQLiteStorageWords(unittest.TestCase):
    """Test word CRUD operations"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_words(self):
        """Test adding words"""
        result = self.storage.add_words(['apple', 'banana'])
        self.assertEqual(result['added'], 2)

    def test_add_duplicate_words(self):
        """Test adding duplicate words"""
        self.storage.add_words(['apple'])
        result = self.storage.add_words(['apple'])
        self.assertEqual(result['duplicate'], 1)

    def test_get_all_words(self):
        """Test getting all words"""
        self.storage.add_words(['apple', 'banana'])
        words = self.storage.get_all_words()
        self.assertEqual(len(words), 2)

    def test_get_pending_words(self):
        """Test getting pending words"""
        self.storage.add_words(['apple', 'banana'])
        words = self.storage.get_all_words()
        self.storage.mark_word_correct(words[0]['id'])
        pending = self.storage.get_pending_words()
        self.assertEqual(len(pending), 1)

    def test_mark_word_correct(self):
        """Test marking word as correct"""
        self.storage.add_words(['apple'])
        words = self.storage.get_all_words()
        self.storage.mark_word_correct(words[0]['id'])
        words = self.storage.get_all_words()
        self.assertEqual(words[0]['status'], 'right')

    def test_mark_word_wrong(self):
        """Test marking word as wrong"""
        self.storage.add_words(['apple'])
        words = self.storage.get_all_words()
        self.storage.mark_word_wrong(words[0]['id'], 'aple')
        words = self.storage.get_all_words()
        self.assertEqual(words[0]['status'], 'wrong')
        self.assertEqual(words[0]['error_count'], 1)

    def test_error_count_accumulation(self):
        """Test error count accumulates"""
        self.storage.add_words(['apple'])
        words = self.storage.get_all_words()
        for _ in range(3):
            self.storage.mark_word_wrong(words[0]['id'], 'wrong')
        words = self.storage.get_all_words()
        self.assertEqual(words[0]['error_count'], 3)

    def test_reset_word(self):
        """Test resetting word status"""
        self.storage.add_words(['apple'])
        words = self.storage.get_all_words()
        self.storage.mark_word_wrong(words[0]['id'])
        self.storage.reset_word(words[0]['id'])
        words = self.storage.get_all_words()
        self.assertEqual(words[0]['status'], 'pending')
        self.assertEqual(words[0]['error_count'], 0)

    def test_delete_word(self):
        """Test deleting word"""
        self.storage.add_words(['apple', 'banana'])
        words = self.storage.get_all_words()
        self.storage.delete_word(words[0]['id'])
        words = self.storage.get_all_words()
        self.assertEqual(len(words), 1)

    def test_clear_all_words(self):
        """Test clearing all words"""
        self.storage.add_words(['apple', 'banana'])
        self.storage.clear_all_words()
        words = self.storage.get_all_words()
        self.assertEqual(len(words), 0)


class TestSQLiteStorageProviders(unittest.TestCase):
    """Test LLM provider CRUD operations"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_provider(self):
        """Test adding provider"""
        pid = self.storage.add_provider(
            name='Test', provider_type='openai', api_key='test-key'
        )
        self.assertIsNotNone(pid)

    def test_get_active_provider(self):
        """Test getting active provider"""
        self.storage.add_provider(
            name='Test', provider_type='openai', is_active=True
        )
        active = self.storage.get_active_provider()
        self.assertIsNotNone(active)

    def test_update_provider(self):
        """Test updating provider"""
        pid = self.storage.add_provider(name='Old', provider_type='openai')
        self.storage.update_provider(pid, name='New')
        provider = self.storage.get_provider_by_id(pid)
        self.assertEqual(provider['name'], 'New')

    def test_delete_provider(self):
        """Test deleting provider"""
        pid = self.storage.add_provider(name='Test', provider_type='openai')
        self.storage.delete_provider(pid)
        provider = self.storage.get_provider_by_id(pid)
        self.assertIsNone(provider)

    def test_set_active_provider(self):
        """Test setting active provider"""
        pid1 = self.storage.add_provider(name='P1', provider_type='openai', is_active=True)
        pid2 = self.storage.add_provider(name='P2', provider_type='openai')
        self.storage.set_active_provider(pid2)
        active = self.storage.get_active_provider()
        self.assertEqual(active['id'], pid2)


class TestSQLiteStoragePassages(unittest.TestCase):
    """Test passage CRUD operations"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_passage(self):
        """Test adding passage"""
        pid = self.storage.add_passage(
            title='Test', content='Content', words_used=['apple', 'banana']
        )
        self.assertIsNotNone(pid)

    def test_get_all_passages(self):
        """Test getting all passages"""
        self.storage.add_passage(title='Test', content='Content', words_used=['apple'])
        passages = self.storage.get_all_passages()
        self.assertEqual(len(passages), 1)

    def test_get_passage_by_id(self):
        """Test getting passage by ID"""
        pid = self.storage.add_passage(title='Test', content='Content', words_used=['apple'])
        passage = self.storage.get_passage_by_id(pid)
        self.assertIsNotNone(passage)
        self.assertEqual(passage['title'], 'Test')

    def test_delete_passage(self):
        """Test deleting passage"""
        pid = self.storage.add_passage(title='Test', content='Content', words_used=['apple'])
        self.storage.delete_passage(pid)
        passage = self.storage.get_passage_by_id(pid)
        self.assertIsNone(passage)


class TestSQLiteStorageStatistics(unittest.TestCase):
    """Test statistics"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test.db')
        self.storage = SQLiteStorage(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_statistics(self):
        """Test getting statistics"""
        self.storage.add_words(['apple', 'banana', 'cherry'])
        words = self.storage.get_all_words()
        self.storage.mark_word_correct(words[0]['id'])
        self.storage.mark_word_wrong(words[1]['id'])
        stats = self.storage.get_statistics()
        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['right'], 1)
        self.assertEqual(stats['wrong'], 1)
        self.assertEqual(stats['pending'], 1)


class TestMacOSFrozenMode(unittest.TestCase):
    """Test macOS frozen app database path handling"""

    def test_frozen_app_uses_app_support_dir(self):
        """Frozen macOS app should use ~/Library/Application Support"""
        import sys as real_sys
        original_frozen = getattr(real_sys, 'frozen', None)
        original_platform = real_sys.platform
        
        try:
            real_sys.frozen = True
            real_sys.platform = 'darwin'
            
            path = SQLiteStorage._default_db_path()
            self.assertIn('Application Support', path)
            self.assertIn('DictationPractice', path)
        finally:
            if original_frozen is None:
                if hasattr(real_sys, 'frozen'):
                    delattr(real_sys, 'frozen')
            else:
                real_sys.frozen = original_frozen
            real_sys.platform = original_platform

    def test_non_frozen_uses_local_dir(self):
        """Non-frozen app should use local instance dir"""
        import sys as real_sys
        original_frozen = getattr(real_sys, 'frozen', None)
        
        try:
            real_sys.frozen = False
            
            path = SQLiteStorage._default_db_path()
            self.assertNotIn('Application Support', path)
        finally:
            if original_frozen is None:
                if hasattr(real_sys, 'frozen'):
                    delattr(real_sys, 'frozen')
            else:
                real_sys.frozen = original_frozen


class TestGetStorageSingleton(unittest.TestCase):
    """Test get_storage singleton pattern"""

    def test_get_storage_returns_same_instance(self):
        """get_storage should return the same instance"""
        s1 = get_storage()
        s2 = get_storage()
        self.assertIs(s1, s2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
