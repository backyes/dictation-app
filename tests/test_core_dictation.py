"""
Core business logic unit tests
Tests for generate_clue, check_answer, session generation algorithms
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dictation import (
    generate_clue, generate_scattered_clue, check_answer,
    generate_dictation_session, generate_full_library_session
)


class TestGenerateClue(unittest.TestCase):
    """Test clue generation logic"""

    def test_two_letter_word(self):
        """2-letter words: show first letter only"""
        clue = generate_clue('an')
        self.assertEqual(clue['length'], 2)
        self.assertEqual(clue['pattern'], 'first_only')
        self.assertTrue(clue['clue'].startswith('a'))

    def test_three_letter_word(self):
        """3-letter words: show first and last letters"""
        clue = generate_clue('cat')
        self.assertEqual(clue['length'], 3)
        self.assertEqual(clue['pattern'], 'first_last')
        self.assertTrue(clue['clue'].startswith('c'))
        self.assertTrue(clue['clue'].endswith('t'))

    def test_four_letter_word(self):
        """4-letter words: show first and last letters"""
        clue = generate_clue('book')
        self.assertEqual(clue['length'], 4)
        self.assertEqual(clue['pattern'], 'first_last')

    def test_five_plus_letter_word(self):
        """5+ letter words: random pattern"""
        clue = generate_clue('apple')
        self.assertEqual(clue['length'], 5)
        self.assertIn(clue['pattern'], ['first_last', 'first_middle_last', 'scattered'])

    def test_clue_length_matches_word(self):
        """Clue length should match word length"""
        for word in ['hi', 'cat', 'book', 'apple', 'banana', 'elephant']:
            clue = generate_clue(word)
            self.assertEqual(clue['length'], len(word))

    def test_clue_contains_underscores(self):
        """Clue should contain underscores for hidden letters"""
        clue = generate_clue('banana')
        self.assertIn('_', clue['clue'])

    def test_clue_reveals_correct_letters(self):
        """Revealed letters should come from the original word"""
        for _ in range(50):
            clue = generate_clue('testing')
            for char in clue['clue'].replace(' ', ''):
                if char != '_':
                    self.assertIn(char, 'testing')

    def test_first_middle_last_pattern(self):
        """Test first_middle_last pattern has correct structure"""
        # Test multiple times since pattern is random
        found_pattern = False
        for _ in range(100):
            clue = generate_clue('elephant')
            if clue['pattern'] == 'first_middle_last':
                found_pattern = True
                # First letter should be 'e'
                self.assertTrue(clue['clue'].startswith('e'))
                # Last letter should be 't'
                self.assertTrue(clue['clue'].endswith('t'))
                break
        # Should find this pattern at least once in 100 tries
        self.assertTrue(found_pattern)

    def test_scattered_pattern(self):
        """Test scattered pattern reveals correct positions"""
        for _ in range(50):
            clue = generate_clue('beautiful')
            if clue['pattern'] == 'scattered':
                # All revealed letters should be from the word
                for char in clue['clue'].replace(' ', ''):
                    if char != '_':
                        self.assertIn(char, 'beautiful')


class TestGenerateScatteredClue(unittest.TestCase):
    """Test scattered clue generation"""

    def test_default_ratio(self):
        """Default reveal ratio is 60%"""
        clue = generate_scattered_clue('elephant')
        letters = clue.replace(' ', '').replace('_', '')
        # 60% of 8 letters ≈ 4-5 letters revealed
        self.assertGreaterEqual(len(letters), 3)
        self.assertLessEqual(len(letters), 6)

    def test_custom_ratio(self):
        """Custom reveal ratio"""
        clue = generate_scattered_clue('elephant', reveal_ratio=0.3)
        letters = clue.replace(' ', '').replace('_', '')
        # 30% of 8 letters ≈ 2 letters
        self.assertGreaterEqual(len(letters), 1)
        self.assertLessEqual(len(letters), 4)

    def test_all_letters_revealed(self):
        """100% ratio reveals all letters"""
        clue = generate_scattered_clue('cat', reveal_ratio=1.0)
        letters = clue.replace(' ', '').replace('_', '')
        self.assertEqual(len(letters), 3)

    def test_revealed_letters_are_correct(self):
        """Revealed letters should match word positions"""
        for _ in range(30):
            clue = generate_scattered_clue('banana', reveal_ratio=0.5)
            chars = clue.split(' ')
            for i, c in enumerate(chars):
                if c != '_':
                    self.assertEqual(c, 'banana'[i])


class TestCheckAnswer(unittest.TestCase):
    """Test answer checking logic"""

    def test_correct_answer(self):
        self.assertTrue(check_answer('apple', 'apple'))

    def test_incorrect_answer(self):
        self.assertFalse(check_answer('aple', 'apple'))

    def test_case_insensitive(self):
        self.assertTrue(check_answer('APPLE', 'apple'))
        self.assertTrue(check_answer('Apple', 'apple'))

    def test_whitespace_trimmed(self):
        self.assertTrue(check_answer('  apple  ', 'apple'))

    def test_empty_input(self):
        self.assertFalse(check_answer('', 'apple'))


class TestGenerateDictationSession(unittest.TestCase):
    """Test dictation session generation algorithm"""

    def test_all_wrong_words_included(self):
        """All wrong words should appear at least once"""
        wrong = [
            {'id': 1, 'word': 'apple', 'error_count': 2},
            {'id': 2, 'word': 'banana', 'error_count': 1},
        ]
        pending = [{'id': 3, 'word': 'cherry', 'error_count': 0}]
        session = generate_dictation_session(pending, wrong)
        session_ids = [w['id'] for w in session]
        self.assertIn(1, session_ids)
        self.assertIn(2, session_ids)

    def test_high_freq_wrong_word_appears_three_times(self):
        """High-frequency wrong words (>=3 errors) should appear at least 3 times"""
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 5}]
        pending = []
        session = generate_dictation_session(pending, wrong)
        apple_count = sum(1 for w in session if w['id'] == 1)
        self.assertGreaterEqual(apple_count, 3)

    def test_empty_session(self):
        """Empty word lists should return empty session"""
        session = generate_dictation_session([], [])
        self.assertEqual(session, [])

    def test_session_contains_required_fields(self):
        """Session words should contain all required fields"""
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 2, 'meaning': '苹果', 'example': 'I eat apple', 'phonetic': '/æpəl/'}]
        pending = []
        session = generate_dictation_session(pending, wrong)
        for w in session:
            self.assertIn('id', w)
            self.assertIn('word', w)
            self.assertIn('clue', w)
            self.assertIn('length', w)
            self.assertIn('pattern', w)
            self.assertIn('meaning', w)
            self.assertIn('example', w)
            self.assertIn('phonetic', w)
            self.assertIn('error_count', w)
            self.assertIn('priority', w)

    def test_high_freq_priority_marked(self):
        """High-frequency wrong words should be marked as 'high' priority"""
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 4}]
        pending = []
        session = generate_dictation_session(pending, wrong)
        for w in session:
            if w['id'] == 1:
                self.assertEqual(w['priority'], 'high')

    def test_normal_priority_marked(self):
        """Normal wrong words should be marked as 'normal' priority"""
        wrong = [{'id': 1, 'word': 'apple', 'error_count': 1}]
        pending = []
        session = generate_dictation_session(pending, wrong)
        for w in session:
            if w['id'] == 1:
                self.assertEqual(w['priority'], 'normal')


class TestGenerateFullLibrarySession(unittest.TestCase):
    """Test full library session generation"""

    def test_all_words_included(self):
        """All words should be included in full library session"""
        words = [
            {'id': 1, 'word': 'apple'},
            {'id': 2, 'word': 'banana'},
            {'id': 3, 'word': 'cherry'},
        ]
        session = generate_full_library_session(words)
        session_ids = [w['id'] for w in session]
        self.assertEqual(set(session_ids), {1, 2, 3})

    def test_empty_library(self):
        """Empty library should return empty session"""
        session = generate_full_library_session([])
        self.assertEqual(session, [])

    def test_session_contains_required_fields(self):
        """Session words should contain all required fields"""
        words = [{'id': 1, 'word': 'apple', 'meaning': '苹果'}]
        session = generate_full_library_session(words)
        for w in session:
            self.assertIn('id', w)
            self.assertIn('word', w)
            self.assertIn('clue', w)
            self.assertIn('length', w)
            self.assertIn('pattern', w)
            self.assertIn('priority', w)


if __name__ == '__main__':
    unittest.main(verbosity=2)
