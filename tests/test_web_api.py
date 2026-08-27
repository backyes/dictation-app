"""
Web API unit tests
Tests for Flask app endpoints - words, dictation, providers, passages
"""
import os
import sys
import unittest
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWebAPI(unittest.TestCase):
    """Test Flask web API endpoints"""

    @classmethod
    def setUpClass(cls):
        """Create test app with temporary database"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.original_db_path = os.environ.get('DATABASE_PATH')
        os.environ['DATABASE_PATH'] = os.path.join(cls.temp_dir, 'test.db')
        
        # Override Config.DATABASE_PATH BEFORE importing app
        from common.config import Config
        Config.DATABASE_PATH = os.path.join(cls.temp_dir, 'test.db')
        
        # Import after setting env
        from platforms.web.app import app
        app.config['TESTING'] = True
        cls.app = app
        cls.client = app.test_client()
        
        # Init database
        from storage.database import init_db
        init_db()

    @classmethod
    def tearDownClass(cls):
        """Cleanup"""
        if cls.original_db_path:
            os.environ['DATABASE_PATH'] = cls.original_db_path
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        """Clear data before each test"""
        from storage.database import get_db
        conn = get_db()
        conn.execute('DELETE FROM dictation_history')
        conn.execute('DELETE FROM dictation_words_library')
        conn.execute("DELETE FROM sqlite_sequence WHERE name='dictation_words_library'")
        conn.commit()
        conn.close()

    # ==================== Page Routes ====================

    def test_index_page(self):
        """Test index page returns 200"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_dictation_page(self):
        """Test dictation page returns 200"""
        response = self.client.get('/dictation')
        self.assertEqual(response.status_code, 200)

    def test_settings_page(self):
        """Test settings page returns 200"""
        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 200)

    def test_passages_page(self):
        """Test passages page returns 200"""
        response = self.client.get('/passages')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_page(self):
        """Test dashboard page returns 200"""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)

    # ==================== Word API ====================

    def test_add_words(self):
        """Test adding words via API"""
        response = self.client.post('/api/words/add',
            json={'words': ['apple', 'banana', 'cherry']})
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['added'], 3)

    def test_add_words_empty(self):
        """Test adding empty word list returns 400"""
        response = self.client.post('/api/words/add', json={'words': []})
        self.assertEqual(response.status_code, 400)

    def test_get_all_words(self):
        """Test getting all words"""
        self.client.post('/api/words/add', json={'words': ['apple', 'banana']})
        response = self.client.get('/api/words')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['words']), 2)

    def test_get_pending_words(self):
        """Test getting pending words"""
        self.client.post('/api/words/add', json={'words': ['apple', 'banana']})
        response = self.client.get('/api/words/pending')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['words']), 2)

    def test_get_wrong_words(self):
        """Test getting wrong words"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        response = self.client.get('/api/words/wrong')
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_get_right_words(self):
        """Test getting right words"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        response = self.client.get('/api/words/right')
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_delete_word(self):
        """Test deleting a word"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        words = self.client.get('/api/words').get_json()['words']
        word_id = words[0]['id']
        response = self.client.post(f'/api/words/delete/{word_id}')
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_reset_word(self):
        """Test resetting a word"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        words = self.client.get('/api/words').get_json()['words']
        word_id = words[0]['id']
        response = self.client.post(f'/api/words/reset/{word_id}')
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_clear_words(self):
        """Test clearing all words"""
        self.client.post('/api/words/add', json={'words': ['apple', 'banana']})
        response = self.client.post('/api/words/clear')
        data = response.get_json()
        self.assertTrue(data['success'])
        words = self.client.get('/api/words').get_json()['words']
        self.assertEqual(len(words), 0)

    # ==================== Dictation API ====================

    def test_dictation_session_empty(self):
        """Test dictation session with no words"""
        response = self.client.get('/api/dictation/session')
        data = response.get_json()
        self.assertFalse(data['success'])

    def test_dictation_session_with_words(self):
        """Test dictation session with words"""
        self.client.post('/api/words/add', json={'words': ['apple', 'banana']})
        response = self.client.get('/api/dictation/session')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total'], 0)

    def test_dictation_check_correct(self):
        """Test correct answer check"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        words = self.client.get('/api/words').get_json()['words']
        word_id = words[0]['id']
        response = self.client.post('/api/dictation/check',
            json={'word_id': word_id, 'user_input': 'apple'})
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_correct'])

    def test_dictation_check_incorrect(self):
        """Test incorrect answer check"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        words = self.client.get('/api/words').get_json()['words']
        word_id = words[0]['id']
        response = self.client.post('/api/dictation/check',
            json={'word_id': word_id, 'user_input': 'aple'})
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['is_correct'])

    def test_dictation_check_case_insensitive(self):
        """Test case insensitive answer check"""
        self.client.post('/api/words/add', json={'words': ['apple']})
        words = self.client.get('/api/words').get_json()['words']
        word_id = words[0]['id']
        response = self.client.post('/api/dictation/check',
            json={'word_id': word_id, 'user_input': 'APPLE'})
        data = response.get_json()
        self.assertTrue(data['is_correct'])

    def test_dictation_check_nonexistent_word(self):
        """Test check with nonexistent word ID"""
        response = self.client.post('/api/dictation/check',
            json={'word_id': 99999, 'user_input': 'test'})
        self.assertEqual(response.status_code, 404)

    def test_dictation_check_missing_word_id(self):
        """Test check with missing word ID"""
        response = self.client.post('/api/dictation/check',
            json={'user_input': 'test'})
        self.assertEqual(response.status_code, 400)

    # ==================== Provider API ====================

    def test_get_providers(self):
        """Test getting all providers"""
        response = self.client.get('/api/providers')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(len(data['providers']), 0)

    def test_get_provider_presets(self):
        """Test getting provider presets"""
        response = self.client.get('/api/providers/presets')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('anthropic', data['presets'])
        self.assertIn('longcat', data['presets'])

    def test_add_provider(self):
        """Test adding a provider"""
        response = self.client.post('/api/providers', json={
            'name': 'Test Provider',
            'provider_type': 'openai',
            'api_key': 'sk-test',
            'model': 'gpt-4',
            'base_url': 'https://api.openai.com/v1'
        })
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_update_provider(self):
        """Test updating a provider"""
        resp = self.client.post('/api/providers', json={
            'name': 'Test', 'provider_type': 'openai'
        })
        provider_id = resp.get_json()['id']
        response = self.client.put(f'/api/providers/{provider_id}',
            json={'name': 'Updated'})
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_delete_provider(self):
        """Test deleting a provider"""
        resp = self.client.post('/api/providers', json={
            'name': 'Test', 'provider_type': 'openai'
        })
        provider_id = resp.get_json()['id']
        response = self.client.delete(f'/api/providers/{provider_id}')
        data = response.get_json()
        self.assertTrue(data['success'])

    def test_activate_provider(self):
        """Test activating a provider"""
        resp = self.client.post('/api/providers', json={
            'name': 'Test', 'provider_type': 'openai'
        })
        provider_id = resp.get_json()['id']
        response = self.client.post(f'/api/providers/{provider_id}/activate')
        data = response.get_json()
        self.assertTrue(data['success'])

    # ==================== Passage API ====================

    def test_get_passages(self):
        """Test getting all passages"""
        response = self.client.get('/api/passages')
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['passages'], [])

    def test_get_passage_not_found(self):
        """Test getting nonexistent passage"""
        response = self.client.get('/api/passages/99999')
        self.assertEqual(response.status_code, 404)

    def test_delete_passage(self):
        """Test deleting a passage (even nonexistent returns success)"""
        response = self.client.delete('/api/passages/99999')
        data = response.get_json()
        # API returns success=True even for nonexistent passage
        self.assertTrue(data['success'])

    def test_clear_passages(self):
        """Test clearing all passages"""
        response = self.client.post('/api/passages/clear')
        data = response.get_json()
        self.assertTrue(data['success'])

    # ==================== Statistics API ====================

    def test_get_statistics(self):
        """Test getting statistics"""
        response = self.client.get('/api/statistics')
        data = response.get_json()
        self.assertTrue(data['success'])
        # Stats are nested under 'stats' key
        stats = data.get('stats', data)
        self.assertIn('total', stats)
        self.assertIn('right', stats)
        self.assertIn('wrong', stats)
        self.assertIn('pending', stats)
        self.assertIn('accuracy', stats)


if __name__ == '__main__':
    unittest.main(verbosity=2)
