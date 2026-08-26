"""Flet UI implementation - OpenAI dark theme"""
import flet as ft
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.sqlite_storage import SQLiteStorage
from core.dictation import generate_clue, check_answer, generate_dictation_session, generate_full_library_session


# OpenAI-style dark theme colors
BG_DARK = "#000000"
BG_CARD = "#1a1a1a"
BG_HOVER = "#2a2a2a"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#888888"
ACCENT_GREEN = "#10a37f"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"
BORDER = "#333333"


class DictationApp:
    """Flet Dictation App - OpenAI dark theme"""

    def __init__(self, storage: SQLiteStorage = None):
        self.storage = storage or SQLiteStorage()
        self.page = None
        self.current_tab = 0

        # Dictation state
        self.session_words = []
        self.current_index = 0
        self.session_stats = {"correct": 0, "wrong": 0, "total": 0}
        self.answer_submitted = False

        # UI refs
        self.word_input = None
        self.extract_result = None
        self.word_list = None
        self.stats_text = None
        self.clue_text = None
        self.phonetic_text = None
        self.meaning_text = None
        self.example_text = None
        self.answer_input = None
        self.feedback_text = None
        self.progress_text = None
        self.hint_text = None
        self.content_container = None
        self.passage_loading = None
        self.passage_card = None
        self.p_title = None
        self.p_content = None
        self.p_trans = None
        self.auth_token = None
        self.model_f = None
        self.max_t = None
        self.temp_f = None
        self.base_url = None

    def init_ui(self, page: ft.Page):
        """Initialize all UI components"""
        self.page = page
        page.title = "Dictation Practice"
        page.window_width = 400
        page.window_height = 780
        page.bgcolor = BG_DARK
        page.theme_mode = ft.ThemeMode.DARK

        # Create UI components
        self.word_input = ft.TextField(
            multiline=True, min_lines=3, max_lines=6,
            border_radius=8, filled=True, bgcolor=BG_CARD, color=TEXT_PRIMARY,
            border_color=BORDER, hint_text="Enter words...", hint_style=ft.TextStyle(color=TEXT_SECONDARY)
        )
        self.extract_result = ft.Column(spacing=6, visible=False)
        self.word_list = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=280)
        self.stats_text = ft.Text("0 words", size=12, color=TEXT_SECONDARY)

        self.clue_text = ft.Text("", size=44, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER, color=TEXT_PRIMARY)
        self.phonetic_text = ft.Text("", size=15, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)
        self.meaning_text = ft.Text("", size=17, text_align=ft.TextAlign.CENTER, color=TEXT_PRIMARY)
        self.example_text = ft.Text("", size=14, italic=True, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)
        self.answer_input = ft.TextField(
            hint_text="Type...", text_align=ft.TextAlign.CENTER, text_size=18,
            on_submit=self._submit_answer, on_change=self._on_answer_change,
            bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER,
            hint_style=ft.TextStyle(color=TEXT_SECONDARY)
        )
        self.feedback_text = ft.Text("", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        self.progress_text = ft.Text("", size=11, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)
        self.hint_text = ft.Text("", size=12, color=TEXT_SECONDARY, text_align=ft.TextAlign.CENTER)

        self.passage_loading = ft.Container(
            content=ft.Column([ft.ProgressRing(color=ACCENT_GREEN), ft.Text("Generating...", size=13, color=TEXT_SECONDARY)],
                              spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center, expand=True
        )
        self.passage_card = ft.Column(visible=False)
        self.p_title = ft.Text("", size=17, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)
        self.p_content = ft.Text("", size=14, color=TEXT_PRIMARY)
        self.p_trans = ft.Text("", size=13, color=TEXT_SECONDARY)

        self.auth_token = ft.TextField(hint_text="ak_...", password=True, border_radius=8, bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER)
        self.model_f = ft.TextField(hint_text="model", border_radius=8, value="LongCat-2.0", bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER)
        self.max_t = ft.TextField(hint_text="1024", border_radius=8, value="1024", bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER)
        self.temp_f = ft.TextField(hint_text="0.7", border_radius=8, value="0.7", bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER)
        self.base_url = ft.TextField(hint_text="https://...", border_radius=8, bgcolor=BG_CARD, color=TEXT_PRIMARY, border_color=BORDER)

        # Build main content area
        self.content_container = ft.Column([self._build_home()], expand=True)

        # Navigation
        page.navigation_bar = ft.NavigationBar(
            selected_index=0,
            bgcolor=BG_CARD,
            destinations=[
                ft.NavigationDestination(icon=ft.icons.HOME, selected_icon=ft.icons.HOME, label="Home"),
                ft.NavigationDestination(icon=ft.icons.EDIT, selected_icon=ft.icons.EDIT, label="Dictation"),
                ft.NavigationDestination(icon=ft.icons.ARTICLE, selected_icon=ft.icons.ARTICLE, label="Reading"),
                ft.NavigationDestination(icon=ft.icons.ANALYTICS, selected_icon=ft.icons.ANALYTICS, label="Stats"),
                ft.NavigationDestination(icon=ft.icons.SETTINGS, selected_icon=ft.icons.SETTINGS, label="Settings"),
            ],
            on_change=self._on_nav_change,
        )

        page.add(self.content_container)
        self._refresh_word_list()

    def _refresh_word_list(self):
        """Refresh word list display"""
        words = self.storage.get_all_words()
        self.word_list.controls.clear()
        for i, w in enumerate(words):
            sc, si = TEXT_SECONDARY, "📝"
            if w["status"] == "right":
                sc, si = ACCENT_GREEN, "✓"
            elif w["status"] == "wrong":
                sc, si = ACCENT_RED, "✗"
            self.word_list.controls.append(ft.Container(content=ft.Row([
                ft.Text(f"{i + 1}.", size=11, width=28, color=TEXT_SECONDARY),
                ft.Text(w["word"], size=14, weight=ft.FontWeight.BOLD, expand=True, color=TEXT_PRIMARY),
                ft.Text(w.get("meaning", ""), size=11, color=TEXT_SECONDARY, expand=True),
                ft.Text(f"{si} {w.get('error_count', 0)}", size=11, color=sc, width=48),
            ]), padding=ft.padding.symmetric(horizontal=10, vertical=6), border_radius=8, bgcolor=BG_CARD))
        r = sum(1 for w in words if w["status"] == "right")
        wr = sum(1 for w in words if w["status"] == "wrong")
        self.stats_text.value = f"{len(words)} words | {r} mastered | {wr} wrong"
        if self.page:
            self.page.update()

    def _on_nav_change(self, e):
        """Handle navigation tab change"""
        idx = e.control.selected_index
        self.current_tab = idx
        self.content_container.controls.clear()
        self.page.snack_bar = None
        if idx == 0:
            self.content_container.controls.append(self._build_home())
        elif idx == 1:
            self.content_container.controls.append(self._build_dictation())
            self._start_session()
        elif idx == 2:
            self.content_container.controls.append(self._build_passage())
        elif idx == 3:
            self.content_container.controls.append(self._build_stats())
        elif idx == 4:
            self.content_container.controls.append(self._build_settings())
        self.page.update()

    def _build_home(self):
        """Build home tab"""
        return ft.Container(content=ft.Column([
            ft.Text("Enter Words", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            self.word_input,
            ft.Row([ft.ElevatedButton("Extract", on_click=self._do_extract,
                                      style=ft.ButtonStyle(bgcolor=ACCENT_GREEN, color=TEXT_PRIMARY))],
                   spacing=10),
            self.extract_result,
            ft.Divider(height=16, color=BORDER),
            ft.Row([ft.Text("Word Library", size=16, weight=ft.FontWeight.BOLD, expand=True, color=TEXT_PRIMARY), self.stats_text]),
            self.word_list,
        ], spacing=10, scroll=ft.ScrollMode.AUTO), padding=16)

    def _build_dictation(self):
        """Build dictation tab with FAB for full library review"""
        return ft.Container(content=ft.Stack([
            ft.Column([
                ft.Text("Dictation", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Divider(height=12, color=BORDER),
                self.clue_text, self.phonetic_text, self.meaning_text, self.example_text,
                self.answer_input, self.feedback_text, self.hint_text, self.progress_text,
            ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.FloatingActionButton(
                icon=ft.icons.REFRESH,
                on_click=self._start_full_library_session,
                bgcolor=ACCENT_GREEN,
                mini=True,
                bottom=16,
                right=16,
            ),
        ]), padding=16, expand=True)

    def _build_passage(self):
        """Build passage tab"""
        self.passage_card.controls = [self.p_title, ft.Divider(height=8, color=BORDER), self.p_content,
                                      ft.Divider(height=8, color=BORDER), self.p_trans]
        return ft.Container(content=ft.Column([
            ft.Text("Reading", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            self.passage_loading, self.passage_card,
            ft.ElevatedButton("Generate", on_click=self._gen_passage,
                              style=ft.ButtonStyle(bgcolor=ACCENT_GREEN, color=TEXT_PRIMARY, padding=16)),
        ], spacing=12, scroll=ft.ScrollMode.AUTO), padding=16)

    def _build_stats(self):
        """Build stats tab"""
        stats = self.storage.get_statistics()
        t = stats["total"]
        r = stats["right"]
        w2 = stats["wrong"]
        a = stats["accuracy"]

        wrong_words = self.storage.get_wrong_words()

        return ft.Container(content=ft.Column([
            ft.Text("Dashboard", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Row([
                ft.Container(
                    content=ft.Column([ft.Text(str(t), size=26, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                                       ft.Text("Total", size=11, color=TEXT_SECONDARY)],
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=14, bgcolor=BG_CARD, border_radius=10, expand=True),
                ft.Container(
                    content=ft.Column([ft.Text(str(r), size=26, weight=ft.FontWeight.BOLD, color=ACCENT_GREEN),
                                       ft.Text("Mastered", size=11, color=TEXT_SECONDARY)],
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=14, bgcolor=BG_CARD, border_radius=10, expand=True),
                ft.Container(
                    content=ft.Column([ft.Text(str(w2), size=26, weight=ft.FontWeight.BOLD, color=ACCENT_RED),
                                       ft.Text("Wrong", size=11, color=TEXT_SECONDARY)],
                                      horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=14, bgcolor=BG_CARD, border_radius=10, expand=True),
            ], spacing=6),
            ft.Container(
                content=ft.Column([ft.Text(f"{a}%", size=26, weight=ft.FontWeight.BOLD, color=ACCENT_BLUE),
                                   ft.Text("Accuracy", size=11, color=TEXT_SECONDARY)],
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=14, bgcolor=BG_CARD, border_radius=10, margin=ft.margin.only(top=6)),
            ft.Divider(height=16, color=BORDER),
            ft.Text("Wrong Words", size=15, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Column([
                ft.Container(
                    content=ft.Row([ft.Text(w["word"], size=14, weight=ft.FontWeight.BOLD, expand=True, color=TEXT_PRIMARY),
                                    ft.Text(f"x{w.get('error_count', 0)}", size=12, color=ACCENT_RED)]),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    bgcolor=BG_CARD, border_radius=8, margin=ft.margin.only(bottom=4)
                ) for w in wrong_words
            ]),
        ], spacing=6, scroll=ft.ScrollMode.AUTO), padding=16)

    def _build_settings(self):
        """Build settings tab - load existing config from database"""
        provider = self.storage.get_active_provider()
        if provider:
            auth_value = provider.get('auth_token', '') or provider.get('api_key', '')
            self.auth_token.value = auth_value
            self.model_f.value = provider.get('model', 'LongCat-2.0')
            self.max_t.value = str(provider.get('max_tokens', 1024))
            self.temp_f.value = str(provider.get('temperature', 0.7))
            self.base_url.value = provider.get('base_url', '')

        return ft.Container(content=ft.Column([
            ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Text("Auth Token", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY), self.auth_token,
            ft.Text("Model", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY), self.model_f,
            ft.Text("Max Tokens", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY), self.max_t,
            ft.Text("Temperature", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY), self.temp_f,
            ft.Text("Base URL", size=12, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY), self.base_url,
            ft.Row([
                ft.ElevatedButton("Save", on_click=self._save_settings,
                                  style=ft.ButtonStyle(bgcolor=ACCENT_GREEN, color=TEXT_PRIMARY)),
                ft.ElevatedButton("Test", on_click=self._test_connection,
                                  style=ft.ButtonStyle(bgcolor=BG_HOVER, color=TEXT_PRIMARY)),
            ], spacing=10),
        ], spacing=6, scroll=ft.ScrollMode.AUTO), padding=16)

    def _do_extract(self, e):
        """Extract words from input text"""
        text = self.word_input.value.strip()
        if not text:
            return
        self.extract_result.controls.clear()
        words = [t.strip().lower() for t in text.replace(",", "\n").split("\n")
                 if t.strip().isalpha() and len(t.strip()) >= 2]
        words = list(dict.fromkeys(words))
        self.extract_result.controls.append(ft.Text(f"Found {len(words)} words:", size=12, color=TEXT_PRIMARY))
        self.extract_result.controls.append(ft.Row([
            ft.Chip(label=ft.Text(w, size=11, color=TEXT_PRIMARY), bgcolor=BG_HOVER) for w in words[:15]
        ], wrap=True, spacing=4))
        self.extract_result.controls.append(
            ft.ElevatedButton("Add to Library", on_click=lambda e: self._add_words(words),
                              style=ft.ButtonStyle(bgcolor=ACCENT_GREEN, color=TEXT_PRIMARY))
        )
        self.extract_result.visible = True
        self.page.update()

    def _add_words(self, words):
        """Add extracted words to library"""
        result = self.storage.add_words(words)
        self.extract_result.visible = False
        self.word_input.value = ""
        self._refresh_word_list()
        self.page.snack_bar = ft.SnackBar(content=ft.Text(f"Added {result['added']} words!"))
        self.page.snack_bar.open = True
        self.page.update()

    def _start_session(self):
        """Start a new dictation session - focus on wrong + pending words"""
        pending = self.storage.get_pending_words()
        wrong = self.storage.get_wrong_words()
        self.session_words = generate_dictation_session(pending, wrong)
        self._begin_session()

    def _start_full_library_session(self, e):
        """Start a full library review session"""
        all_words = self.storage.get_all_words()
        self.session_words = generate_full_library_session(all_words)
        self._begin_session()

    def _begin_session(self):
        """Common session initialization"""
        if not self.session_words:
            self.clue_text.value = "No words to practice"
            self.phonetic_text.value = self.meaning_text.value = ""
            self.example_text.value = self.feedback_text.value = ""
            self.hint_text.value = ""
            self.answer_input.disabled = True
            self.progress_text.value = "Add words first!"
            self.page.update()
            return

        self.current_index = 0
        self.session_stats = {"correct": 0, "wrong": 0, "total": len(self.session_words)}
        self._show_word()

    def _show_word(self):
        """Show current word in dictation session"""
        if self.current_index >= len(self.session_words):
            self._show_done()
            return
        w = self.session_words[self.current_index]
        self.answer_submitted = False
        self.clue_text.value = generate_clue(w["word"])["clue"]
        self.phonetic_text.value = w.get("phonetic", "")
        self.meaning_text.value = w.get("meaning", "")
        self.example_text.value = w.get("example", "")
        self.answer_input.value = ""
        self.answer_input.disabled = False
        self.feedback_text.value = ""
        self.hint_text.value = ""
        self.progress_text.value = f"{self.current_index + 1} / {len(self.session_words)}"
        self.page.update()

    def _on_answer_change(self, e):
        """Auto-submit when user types the last letter"""
        if self.answer_submitted or not self.session_words:
            return

        w = self.session_words[self.current_index]
        correct_word = w["word"].lower()
        user_input = self.answer_input.value.strip().lower()

        if len(user_input) >= len(correct_word):
            self._submit_answer()

    def _submit_answer(self, e=None):
        """Submit answer for current word - triggered by Enter key"""
        if self.answer_submitted:
            self.current_index += 1
            self._show_word()
            return

        ui = self.answer_input.value.strip().lower()
        if not ui:
            return

        self.answer_submitted = True
        w = self.session_words[self.current_index]
        correct_word = w["word"].lower()

        if ui == correct_word:
            self.session_stats["correct"] += 1
            self.storage.mark_word_correct(w["id"])
            self.feedback_text.value = "Correct!"
            self.feedback_text.color = ACCENT_GREEN
        else:
            self.session_stats["wrong"] += 1
            self.storage.mark_word_wrong(w["id"], ui)
            self.feedback_text.value = f"Wrong: {w['word']}"
            self.feedback_text.color = ACCENT_RED
            self.hint_text.value = f"Meaning: {w.get('meaning', '')}"

        self.answer_input.disabled = True
        self.page.update()

        # Auto-advance to next word after a short delay
        import time
        time.sleep(1.0)
        self.current_index += 1
        self._show_word()

    def _show_done(self):
        """Show session completion screen"""
        self.clue_text.value = ""
        self.phonetic_text.value = self.meaning_text.value = self.example_text.value = ""
        acc = round(self.session_stats["correct"] / max(self.session_stats["total"], 1) * 100)
        self.progress_text.value = (f"Done! {self.session_stats['total']} words | "
                                    f"Correct {self.session_stats['correct']} | "
                                    f"Wrong {self.session_stats['wrong']} | {acc}%")
        self.feedback_text.value = "✅ Session Complete!"
        self.feedback_text.color = ACCENT_BLUE
        self.hint_text.value = "Tap Dictation tab to practice again"
        self.page.update()

    def _gen_passage(self, e):
        """Generate passage using LLM based on wrong and untested words"""
        self.passage_loading.visible = True
        self.passage_card.visible = False
        self.page.update()

        # Get wrong words and pending words
        wrong_words = self.storage.get_wrong_words()
        pending = self.storage.get_pending_words()

        wrong_word_list = [w['word'] for w in wrong_words if w.get('error_count', 0) >= 2]
        pending_word_list = [w['word'] for w in pending if w.get('status') == 'pending'][:5]

        # Combine: prioritize wrong words, fill with pending
        all_words = wrong_word_list + pending_word_list
        if len(all_words) < 3:
            all_words_data = self.storage.get_all_words()
            all_words = [w['word'] for w in all_words_data if w.get('meaning')][:10]

        if len(all_words) < 3:
            self.passage_loading.visible = False
            self.passage_card.visible = True
            self.p_title.value = "Need more words"
            self.p_content.value = "Please add at least 3 words to generate a passage."
            self.p_trans.value = ""
            self.page.update()
            return

        # Call LLM service in background thread
        import threading

        def generate():
            try:
                from llm_service import generate_passage
                result = generate_passage(all_words, difficulty='intermediate')

                self.passage_loading.visible = False
                self.passage_card.visible = True
                self.p_title.value = result.get('title', 'Generated Passage')
                self.p_content.value = result.get('content', '')
                self.p_trans.value = result.get('translation', '')
                self.page.update()
            except Exception as ex:
                self.passage_loading.visible = False
                self.passage_card.visible = True
                self.p_title.value = "Generation Failed"
                self.p_content.value = f"Error: {str(ex)}"
                self.p_trans.value = ""
                self.page.update()

        thread = threading.Thread(target=generate, daemon=True)
        thread.start()

    def _save_settings(self, e):
        """Save LLM settings to database"""
        provider = self.storage.get_active_provider()
        if not provider:
            self.storage.add_provider(
                name='Default',
                provider_type='anthropic',
                auth_token=self.auth_token.value,
                model=self.model_f.value,
                max_tokens=int(self.max_t.value or 1024),
                temperature=float(self.temp_f.value or 0.7),
                base_url=self.base_url.value,
                is_active=True
            )
        else:
            self.storage.update_provider(
                provider['id'],
                auth_token=self.auth_token.value,
                model=self.model_f.value,
                max_tokens=int(self.max_t.value or 1024),
                temperature=float(self.temp_f.value or 0.7),
                base_url=self.base_url.value
            )

        self.page.snack_bar = ft.SnackBar(content=ft.Text("Settings saved!"))
        self.page.snack_bar.open = True
        self.page.update()

    def _test_connection(self, e):
        """Test LLM by sending a simple prompt"""
        self.page.snack_bar = ft.SnackBar(content=ft.Text("Testing LLM..."))
        self.page.snack_bar.open = True
        self.page.update()

        try:
            from llm_service import test_connection
            result = test_connection()
            if result.get('success'):
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"LLM OK: {result.get('message', 'Connected')}"))
            else:
                self.page.snack_bar = ft.SnackBar(content=ft.Text(f"LLM Failed: {result.get('message', 'Error')}"))
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(content=ft.Text(f"LLM Error: {str(ex)}"))

        self.page.snack_bar.open = True
        self.page.update()


def run_app(page: ft.Page):
    """Entry point for Flet app"""
    app = DictationApp()
    app.init_ui(page)


if __name__ == "__main__":
    ft.app(target=run_app, view=ft.AppView.WEB_BROWSER, port=8501)
