"""Common business logic - dictation session generation"""
from typing import List, Dict, Any
import random


def generate_clue(word: str) -> Dict[str, Any]:
    """Generate word clue (fill-in-the-blank mode)"""
    length = len(word)

    if length <= 2:
        clue = word[0] + ' _ ' * (length - 1)
        pattern = 'first_only'
    elif length <= 4:
        clue = word[0] + ' _ ' * (length - 2) + word[-1]
        pattern = 'first_last'
    else:
        pattern_type = random.choice(['first_last', 'first_middle_last', 'scattered'])

        if pattern_type == 'first_last':
            clue = word[0] + ' _ ' * (length - 2) + word[-1]
            pattern = 'first_last'
        elif pattern_type == 'first_middle_last':
            mid = length // 2
            clue_chars = [' _ '] * length
            clue_chars[0] = word[0]
            clue_chars[mid] = word[mid]
            clue_chars[-1] = word[-1]
            clue = ''.join(clue_chars)
            pattern = 'first_middle_last'
        else:
            num_reveal = max(2, length // 3)
            reveal_positions = sorted(random.sample(range(length), num_reveal))
            clue_chars = [' _ '] * length
            for pos in reveal_positions:
                clue_chars[pos] = word[pos]
            clue = ''.join(clue_chars)
            pattern = 'scattered'

    return {'clue': clue, 'length': length, 'pattern': pattern}


def check_answer(user_input: str, correct_word: str) -> bool:
    """Check if user answer is correct"""
    return user_input.strip().lower() == correct_word.lower()


def generate_dictation_session(words: List[Dict], wrong_words: List[Dict]) -> List[Dict]:
    """
    Generate dictation session - focus on wrong + pending words with probability mixing
    """
    session_words = []
    word_ids_added = set()

    # First ensure all wrong words appear at least once
    for w in wrong_words:
        if w['id'] not in word_ids_added:
            clue_info = generate_clue(w['word'])
            session_words.append({
                'id': w['id'], 'word': w['word'], 'clue': clue_info['clue'],
                'length': clue_info['length'], 'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''), 'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''), 'error_count': w.get('error_count', 0),
                'priority': 'high' if w.get('error_count', 0) >= 3 else 'normal'
            })
            word_ids_added.add(w['id'])

    # High-frequency wrong words get extra occurrences
    high_freq_wrong = [w for w in wrong_words if w.get('error_count', 0) >= 3]
    for w in high_freq_wrong:
        extra_count = min(w['error_count'], 3)
        for _ in range(extra_count - 1):
            clue_info = generate_clue(w['word'])
            session_words.append({
                'id': w['id'], 'word': w['word'], 'clue': clue_info['clue'],
                'length': clue_info['length'], 'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''), 'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''), 'error_count': w.get('error_count', 0),
                'priority': 'high'
            })

    # Build pending word pool
    pending_pool = []
    for w in words:
        if w['id'] not in word_ids_added:
            clue_info = generate_clue(w['word'])
            pending_pool.append({
                'id': w['id'], 'word': w['word'], 'clue': clue_info['clue'],
                'length': clue_info['length'], 'pattern': clue_info['pattern'],
                'meaning': w.get('meaning', ''), 'example': w.get('example', ''),
                'phonetic': w.get('phonetic', ''), 'error_count': w.get('error_count', 0),
                'priority': 'normal'
            })

    # Mix pending words with ~40% probability
    for pending_word in pending_pool:
        if random.random() < 0.4:
            insert_pos = random.randint(0, len(session_words))
            session_words.insert(insert_pos, pending_word)

    if not session_words:
        session_words = pending_pool

    random.shuffle(session_words)
    return session_words


def generate_full_library_session(all_words: List[Dict]) -> List[Dict]:
    """Generate session with ALL words"""
    session_words = []
    for w in all_words:
        clue_info = generate_clue(w['word'])
        session_words.append({
            'id': w['id'], 'word': w['word'], 'clue': clue_info['clue'],
            'length': clue_info['length'], 'pattern': clue_info['pattern'],
            'meaning': w.get('meaning', ''), 'example': w.get('example', ''),
            'phonetic': w.get('phonetic', ''), 'error_count': w.get('error_count', 0),
            'priority': 'high' if w.get('error_count', 0) >= 3 else 'normal'
        })
    random.shuffle(session_words)
    return session_words
