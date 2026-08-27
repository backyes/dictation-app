"""
Common services unit tests
Tests for dictation and passage service modules
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.services.dictation import (
    generate_clue as common_generate_clue,
    check_answer as common_check_answer,
    generate_dictation_session as common_generate_session,
    generate_full_library_session as common_generate_full_session
)


class TestCommonDictationClue(unittest.TestCase):
    """Test common dictation clue generation"""

    def test_two_letter_word(self):
        clue = common_generate_clue('an')
        self.assertEqual(clue['length'], 2)
        self.assertEqual(clue['pattern'], 'first_only')

    def test_three_letter_word(self):
        clue = common_generate_clue('cat')
        self.assertEqual(clue['length'], 3)
        self.assertEqual(clue['pattern'], 'first_last')

    def test_five_plus_letter_word(self):
        clue = common_generate_clue('apple')
        self.assertEqual(clue['length'], 5)
        self.assertIn(clue['pattern'], ['first_last', 'first_middle_last', 'scattered'])

    def test_clue_length_matches_word(self):
        for word in ['hi', 'cat', 'book', 'apple', 'banana']:
            clue = common_generate_clue(word)
            self.assertEqual(clue['length'], len(word))


class TestCommonCheckAnswer(unittest.TestCase):
    """Test common answer checking"""

    def test_correct(self):
        self.assertTrue(common_check_answer('apple', 'apple'))

    def test_incorrect(self):
        self.assertFalse(common_check_answer('aple', 'apple'))

    def test_case_insensitive(self):
        self.assertTrue(common_check_answer('APPLE', 'apple'))

    def test_whitespace_trimmed(self):
        self.assertTrue(common_check_answer('  apple  ', 'apple'))


class TestCommonDictationSession(unittest.TestCase):
    """Test common dictation session generation"""

    def test_all_wrong_words_included(self):
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 2}]
        pending = [{'id': 2, 'word': 'banana', 'error_count': 0}]
        session = common_generate_session(pending, wrong)
        ids = [w['id'] for w in session]
        self.assertIn(1, ids)

    def test_empty_session(self):
        session = common_generate_session([], [])
        self.assertEqual(session, [])

    def test_session_fields(self):
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 2}]
        session = common_generate_session([], wrong)
        for w in session:
            self.assertIn('id', w)
            self.assertIn('word', w)
            self.assertIn('clue', w)
            self.assertIn('priority', w)


class TestCommonFullLibrarySession(unittest.TestCase):
    """Test common full library session"""

    def test_all_words_included(self):
        words = [{'id': 1, 'word': 'apple'}, {'id': 2, 'word': 'banana'}]
        session = common_generate_full_session(words)
        ids = [w['id'] for w in session]
        self.assertEqual(set(ids), {1, 2})

    def test_empty_library(self):
        session = common_generate_full_session([])
        self.assertEqual(session, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
