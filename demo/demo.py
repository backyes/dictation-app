
import flet as ft
import random

SAMPLE_WORDS = [
    {"word": "apple", "meaning": "apple", "phonetic": "/ˈæpl/", "example": "I eat an apple every day.", "status": "pending", "error_count": 0},
    {"word": "banana", "meaning": "banana", "phonetic": "/bəˈnːnə/", "example": "The banana is yellow.", "status": "pending", "error_count": 0},
    {"word": "beautiful", "meaning": "beautiful", "phonetic": "/ˈbjuːtɪfl/", "example": "She has a beautiful voice.", "status": "wrong", "error_count": 3},
    {"word": "challenge", "meaning": "challenge", "phonetic": "/ˈtʃælɪndʒ/", "example": "This is a big challenge.", "status": "right", "error_count": 1},
    {"word": "discover", "meaning": "discover", "phonetic": "/dɪˈskʌvər/", "example": "Scientists discover new things.", "status": "wrong", "error_count": 2},
    {"word": "elephant", "meaning": "elephant", "phonetic": "/ˈelɪfənt/", "example": "The elephant is very big.", "status": "pending", "error_count": 0},
    {"word": "knowledge", "meaning": "knowledge", "phonetic": "/ˈnɒlɪdʒ/", "example": "Knowledge is power.", "status": "right", "error_count": 0},
]

def main(page: ft.Page):
    page.title = "Dictation Demo"
    page.window_width = 400
    page.window_height = 780

    current_idx = [0]
    answer_submitted = [False]
    session = []
    stats = {"correct": 0, "wrong": 0, "total": 0}

    word_input = ft.TextField(multiline=True, min_lines=3, max_lines=6, border_radius=10, filled=True, hint_text="Enter words...")
    extract_result = ft.Column(spacing=6, visible=False)
    word_list = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=280)
    stats_text = ft.Text("0 words", size=12, color=ft.colors.GREY_600)

    clue = ft.Text("", size=44, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    phonetic = ft.Text("", size=15, color=ft.colors.GREY_600, text_align=ft.TextAlign.CENTER)
    meaning = ft.Text("", size=17, text_align=ft.TextAlign.CENTER)
    example = ft.Text("", size=14, italic=True, color=ft.colors.GREY_700, text_align=ft.TextAlign.CENTER)
    answer = ft.TextField(hint_text="Type...", text_align=ft.TextAlign.CENTER, size=18)
    feedback = ft.Text("", size=18, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    progress = ft.Text("", size=11, color=ft.colors.GREY_500, text_align=ft.TextAlign.CENTER)
    hint = ft.Text("", size=12, color=ft.colors.GREY_600, text_align=ft.TextAlign.CENTER)

    passage_loading = ft.Container(content=ft.Column([ft.ProgressRing(), ft.Text("Generating...", size=13, color=ft.colors.GREY_600)], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER), alignment=ft.alignment.center, expand=True)
    passage_card = ft.Column(visible=False)
    p_title = ft.Text("", size=17, weight=ft.FontWeight.BOLD)
    p_content = ft.Text("", size=14, color=ft.colors.GREY_800)
    p_trans = ft.Text("", size=13, color=ft.colors.GREY_600)

    auth_token = ft.TextField(hint_text="ak_...", password=True, border_radius=8)
    model_f = ft.TextField(hint_text="model", border_radius=8, value="LongCat-2.0")
    max_t = ft.TextField(hint_text="1024", border_radius=8, value="1024")
    temp_f = ft.TextField(hint_text="0.7", border_radius=8, value="0.7")
    base_url = ft.TextField(hint_text="https://...", border_radius=8)

    def refresh():
        word_list.controls.clear()
        for i, w in enumerate(SAMPLE_WORDS):
            sc, si = ft.colors.GREY, "📝"
            if w["status"] == "right": sc, si = ft.colors.GREEN, "✓"
            elif w["status"] == "wrong": sc, si = ft.colors.RED, "✗"
            word_list.controls.append(ft.Container(content=ft.Row([
                ft.Text(f"{i+1}.", size=11, width=28),
                ft.Text(w["word"], size=14, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(w["meaning"], size=11, color=ft.colors.GREY_600, expand=True),
                ft.Text(f"{si} {w['error_count']}", size=11, color=sc, width=48),
            ]), padding=ft.padding.symmetric(horizontal=10, vertical=6), border_radius=8, bgcolor=ft.colors.GREY_50))
        r = sum(1 for w in SAMPLE_WORDS if w["status"]=="right")
        wr = sum(1 for w in SAMPLE_WORDS if w["status"]=="wrong")
        stats_text.value = f"{len(SAMPLE_WORDS)} words | {r} mastered | {wr} wrong"
        page.update()

    def do_extract(e):
        text = word_input.value.strip()
        if not text: return
        extract_result.controls.clear()
        words = [t.strip().lower() for t in text.replace(",","\n").split("\n") if t.strip().isalpha()]
        extract_result.controls.append(ft.Text(f"Found {len(words)} words:", size=12))
        extract_result.controls.append(ft.Row([ft.Chip(label=ft.Text(w, size=11), bgcolor=ft.colors.BLUE_50) for w in words[:15]], wrap=True, spacing=4))
        extract_result.visible = True
        page.update()

    def do_clue(word):
        L = len(word)
        if L <= 3: return word[0] + " _ " * (L-1)
        if L <= 5:
            mid = L//2
            c = [" _ "]*L; c[0]=word[0]; c[mid]=word[mid]; c[-1]=word[-1]
            return "".join(c)
        pos = sorted(random.sample(range(L), max(2, L//3)))
        c = [" _ "]*L
        for p in pos: c[p]=word[p]
        return "".join(c)

    def start_session():
        pending = [w for w in SAMPLE_WORDS if w["status"]=="pending"]
        wrong = [w for w in SAMPLE_WORDS if w["status"]=="wrong"]
        session.clear()
        session.extend(wrong)
        for w in pending:
            if w not in session: session.append(w)
        random.shuffle(session)
        if not session:
            clue.value = "No words to practice"
            phonetic.value = meaning.value = example.value = feedback.value = hint.value = ""
            answer.disabled = True
            progress.value = "Add words first!"
            page.update(); return
        current_idx[0] = 0
        stats["correct"] = stats["wrong"] = 0
        stats["total"] = len(session)
        show_word()

    def show_word():
        if current_idx[0] >= len(session):
            show_done(); return
        w = session[current_idx[0]]
        answer_submitted[0] = False
        clue.value = do_clue(w["word"])
        phonetic.value = w.get("phonetic","")
        meaning.value = w.get("meaning","")
        example.value = w.get("example","")
        answer.value = ""
        answer.disabled = False
        feedback.value = hint.value = ""
        progress.value = f"{current_idx[0]+1} / {len(session)}"
        page.update()

    def submit(e):
        if answer_submitted[0]:
            current_idx[0] += 1
            show_word(); return
        ui = answer.value.strip().lower()
        if not ui: return
        answer_submitted[0] = True
        w = session[current_idx[0]]
        if ui == w["word"].lower():
            stats["correct"] += 1
            w["status"] = "right"
            w["error_count"] = 0
            feedback.value = "Correct!"
            feedback.color = ft.colors.GREEN
        else:
            stats["wrong"] += 1
            w["status"] = "wrong"
            w["error_count"] = w.get("error_count",0)+1
            feedback.value = f"Wrong: {w['word']}"
            feedback.color = ft.colors.RED
            hint.value = f"Meaning: {w.get(\'meaning','')}"
        answer.disabled = True
        page.update()

    def show_done():
        clue.value = ""
        phonetic.value = meaning.value = example.value = ""
        acc = round(stats["correct"]/max(stats["total"],1)*100)
        progress.value = f"Done! {stats['total']} words | Correct {stats['correct']} | Wrong {stats['wrong']} | {acc}%"
        feedback.value = "✅ Session Complete!"
        feedback.color = ft.colors.BLUE
        hint.value = "Tap Dictation tab to practice again"
        page.update()

    answer.on_submit = submit

    def gen_passage(e):
        passage_loading.visible = True
        passage_card.visible = False
        page.update()
        import time; time.sleep(0.8)
        p_title.value = "A Day at the Zoo"
        p_content.value = "Yesterday, I went to the zoo with my family. We saw a big elephant eating bananas. The monkey was very beautiful with its golden fur."
        p_trans.value = "Yesterday, I went to the zoo with my family. We saw a big elephant eating bananas."
        passage_loading.visible = False
        passage_card.visible = True
        page.update()

    def save_s(e):
        page.snack_bar = ft.SnackBar(content=ft.Text("Settings saved!")); page.snack_bar.open = True; page.update()

    def test_c(e):
        page.snack_bar = ft.SnackBar(content=ft.Text("Connection: OK")); page.snack_bar.open = True; page.update()

    # Build tabs
    tab_home = ft.Container(content=ft.Column([
        ft.Text("Enter Words", size=20, weight=ft.FontWeight.BOLD),
        word_input,
        ft.Row([ft.ElevatedButton("Extract", on_click=do_extract, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_400, color=ft.colors.WHITE))], spacing=10),
        extract_result,
        ft.Divider(height=16),
        ft.Row([ft.Text("Word Library", size=16, weight=ft.FontWeight.BOLD, expand=True), stats_text]),
        word_list,
    ], spacing=10, scroll=ft.ScrollMode.AUTO), padding=16)

    tab_dict = ft.Container(content=ft.Column([
        ft.Text("Dictation", size=20, weight=ft.FontWeight.BOLD),
        ft.Divider(height=12),
        clue, phonetic, meaning, example, answer, feedback, hint, progress,
        ft.ElevatedButton("Submit", on_click=submit, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_400, color=ft.colors.WHITE, padding=16)),
    ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=16, expand=True)

    passage_card.controls = [p_title, ft.Divider(height=8), p_content, ft.Divider(height=8), p_trans]
    tab_passage = ft.Container(content=ft.Column([
        ft.Text("Reading", size=20, weight=ft.FontWeight.BOLD),
        passage_loading, passage_card,
        ft.ElevatedButton("Generate", on_click=gen_passage, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_400, color=ft.colors.WHITE, padding=16)),
    ], spacing=12, scroll=ft.ScrollMode.AUTO), padding=16)

    def build_stats():
        t = len(SAMPLE_WORDS)
        r = sum(1 for w in SAMPLE_WORDS if w["status"]=="right")
        w2 = sum(1 for w in SAMPLE_WORDS if w["status"]=="wrong")
        a = round(r/max(t,1)*100)
        return ft.Column([
            ft.Text("Dashboard", size=20, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Container(content=ft.Column([ft.Text(str(t), size=26, weight=ft.FontWeight.BOLD), ft.Text("Total", size=11, color=ft.colors.GREY_600)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=14, bgcolor=ft.colors.GREY_50, border_radius=10, expand=True),
                ft.Container(content=ft.Column([ft.Text(str(r), size=26, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN), ft.Text("Mastered", size=11, color=ft.colors.GREY_600)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=14, bgcolor=ft.colors.GREEN_50, border_radius=10, expand=True),
                ft.Container(content=ft.Column([ft.Text(str(w2), size=26, weight=ft.FontWeight.BOLD, color=ft.colors.RED), ft.Text("Wrong", size=11, color=ft.colors.GREY_600)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=14, bgcolor=ft.colors.RED_50, border_radius=10, expand=True),
            ], spacing=6),
            ft.Container(content=ft.Column([ft.Text(f"{a}%", size=26, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE), ft.Text("Accuracy", size=11, color=ft.colors.GREY_600)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), padding=14, bgcolor=ft.colors.BLUE_50, border_radius=10, margin=ft.margin.only(top=6)),
            ft.Divider(height=16),
            ft.Text("Wrong Words", size=15, weight=ft.FontWeight.BOLD),
            ft.Column([ft.Container(content=ft.Row([ft.Text(w["word"], size=14, weight=ft.FontWeight.BOLD, expand=True), ft.Text(f"x{w['error_count']}", size=12, color=ft.colors.RED)]), padding=ft.padding.symmetric(horizontal=10, vertical=6), bgcolor=ft.colors.RED_50, border_radius=8, margin=ft.margin.only(bottom=4)) for w in SAMPLE_WORDS if w["status"]=="wrong"]),
        ], spacing=6, scroll=ft.ScrollMode.AUTO)

    tab_stats = ft.Container(content=build_stats(), padding=16)

    tab_settings = ft.Container(content=ft.Column([
        ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Auth Token", size=12, weight=ft.FontWeight.BOLD), auth_token,
        ft.Text("Model", size=12, weight=ft.FontWeight.BOLD), model_f,
        ft.Text("Max Tokens", size=12, weight=ft.FontWeight.BOLD), max_t,
        ft.Text("Temperature", size=12, weight=ft.FontWeight.BOLD), temp_f,
        ft.Text("Base URL", size=12, weight=ft.FontWeight.BOLD), base_url,
        ft.Row([ft.ElevatedButton("Save", on_click=save_s, style=ft.ButtonStyle(bgcolor=ft.colors.BLUE_400, color=ft.colors.WHITE)), ft.ElevatedButton("Test", on_click=test_c, style=ft.ButtonStyle(bgcolor=ft.colors.GREY_300, color=ft.colors.BLACK87))], spacing=10),
    ], spacing=6, scroll=ft.ScrollMode.AUTO), padding=16)

    content = ft.Column([tab_home], expand=True)

    def on_nav(e):
        idx = e.control.selected_index
        content.controls.clear()
        if idx == 0: content.controls.append(tab_home)
        elif idx == 1: content.controls.append(tab_dict); start_session()
        elif idx == 2: content.controls.append(tab_passage)
        elif idx == 3: content.controls.append(tab_stats)
        elif idx == 4: content.controls.append(tab_settings)
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.HOME, label="Home"),
            ft.NavigationBarDestination(icon=ft.icons.EDIT_NOTES, label="Dictation"),
            ft.NavigationBarDestination(icon=ft.icons.ARTICLE, label="Reading"),
            ft.NavigationBarDestination(icon=ft.icons.ANALYTICS, label="Stats"),
            ft.NavigationBarDestination(icon=ft.icons.SETTINGS, label="Settings"),
        ],
        on_change=on_nav,
    )

    page.add(content)
    refresh()

ft.app(target=main)
