"""
LLM service module unit tests
Tests for test_connection, generate_passage, and other service functions
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.services.llm import test_connection as _test_connection, generate_passage, get_active_client


class TestTestConnection(unittest.TestCase):
    """Test test_connection function"""

    @patch('common.llm.providers.create_provider')
    @patch('common.services.llm.get_storage')
    def test_test_connection_success(self, mock_get_storage, mock_create):
        """Test successful connection"""
        mock_get_storage.return_value.get_active_provider.return_value = {
            'name': 'Test',
            'model': 'test-model',
            'api_key': 'test-key'
        }
        mock_client = MagicMock()
        mock_client.test_connection.return_value = {
            'success': True,
            'message': 'Connected!',
            'model': 'test-model'
        }
        mock_create.return_value = mock_client

        result = _test_connection()
        self.assertTrue(result['success'])
        self.assertIn('Connected!', result['message'])

    @patch('common.services.llm.get_storage')
    def test_test_connection_no_provider(self, mock_get_storage):
        """Test connection with no provider configured"""
        mock_get_storage.return_value.get_active_provider.return_value = None
        result = _test_connection()
        self.assertFalse(result['success'])
        self.assertIn('没有配置', result['message'])

    @patch('common.llm.providers.create_provider')
    @patch('common.services.llm.get_storage')
    def test_test_connection_exception(self, mock_get_storage, mock_create):
        """Test connection with exception"""
        mock_get_storage.return_value.get_active_provider.return_value = {
            'name': 'Test',
            'model': 'test-model',
            'api_key': 'test-key'
        }
        mock_create.side_effect = Exception('Connection failed')
        result = _test_connection()
        self.assertFalse(result['success'])
        self.assertIn('Connection failed', result['message'])

    @patch('common.llm.providers.create_provider')
    def test_test_connection_with_config(self, mock_create):
        """Test connection with provided config"""
        mock_client = MagicMock()
        mock_client.test_connection.return_value = {
            'success': True,
            'message': 'OK',
            'model': 'custom-model'
        }
        mock_create.return_value = mock_client

        config = {'model': 'custom-model', 'api_key': 'test'}
        result = _test_connection(config)
        self.assertTrue(result['success'])


class TestGetActiveClient(unittest.TestCase):
    """Test get_active_client function"""

    @patch('common.llm.providers.create_provider')
    @patch('common.services.llm.get_storage')
    def test_get_active_client_success(self, mock_get_storage, mock_create):
        """Test getting active client"""
        mock_get_storage.return_value.get_active_provider.return_value = {
            'name': 'Test',
            'model': 'test-model',
            'api_key': 'test-key'
        }
        mock_create.return_value = MagicMock()

        client = get_active_client()
        self.assertIsNotNone(client)

    @patch('common.services.llm.get_storage')
    def test_get_active_client_no_provider(self, mock_get_storage):
        """Test getting client with no provider"""
        mock_get_storage.return_value.get_active_provider.return_value = None
        with self.assertRaises(Exception):
            get_active_client()

    @patch('common.services.llm.get_storage')
    def test_get_active_client_no_auth(self, mock_get_storage):
        """Test getting client with no auth"""
        mock_get_storage.return_value.get_active_provider.return_value = {'name': 'Test'}
        with self.assertRaises(Exception):
            get_active_client()


class TestGeneratePassage(unittest.TestCase):
    """Test generate_passage function"""

    @patch('common.llm.passage_generator.PassageGenerator')
    def test_generate_passage(self, mock_generator_class):
        """Test passage generation"""
        mock_generator = MagicMock()
        mock_generator.generate.return_value = {
            'title': 'Test Story',
            'content': 'Story content',
            'translation': 'Translation',
            'words_used': ['apple', 'banana']
        }
        mock_generator_class.return_value = mock_generator

        result = generate_passage(['apple', 'banana'])
        self.assertIn('content', result)
        self.assertIn('translation', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
