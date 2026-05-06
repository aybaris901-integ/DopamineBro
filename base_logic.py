import asyncio
import os
import queue
import random
import re
import sys
import threading
from datetime import datetime
from typing import Optional

import flet as ft
import joblib
from pynput import keyboard

try:
    from plyer import notification
except ImportError:
    notification = None

try:
    from setfit import SetFitModel
except ImportError:
    SetFitModel = None


APP_NAME = "Echo Chamber"
APP_SUBTITLE = "AI Dopamine Guard"
MODEL_DIR = "dopamine_model"

# Hybrid detection:
# 1) Productive/work queries are ignored first.
# 2) Exact high-signal RegEx traps are detected immediately.
# 3) NLP is used only for softer / less obvious cases.
#
# If the model over-triggers, increase to 0.70-0.80.
# If it misses obvious dopamine traps, lower to 0.45-0.55.
NLP_CONFIDENCE_THRESHOLD = 0.58
MIN_TRIGGER_TEXT_LENGTH = 12


class InputMonitor:
    """
    Captures typed text line-by-line and sends a completed line only after Enter.
    ESC clears the current line buffer.
    """

    def __init__(self, on_text_captured_callback):
        self.current_line = []
        self.on_text_captured = on_text_captured_callback
        self.listener = None
        self.running = False
        self._lock = threading.Lock()

    def on_press(self, key):
        if not self.running:
            return

        try:
            with self._lock:
                if hasattr(key, "char") and key.char is not None:
                    self.current_line.append(key.char)

                elif key == keyboard.Key.space:
                    self.current_line.append(" ")

                elif key == keyboard.Key.backspace:
                    if self.current_line:
                        self.current_line.pop()

                elif key == keyboard.Key.enter:
                    text = "".join(self.current_line).strip()
                    self.current_line = []

                    if text:
                        self.on_text_captured(text)

                elif key == keyboard.Key.esc:
                    self.current_line = []

        except Exception as e:
            print(f"Keyboard handler error: {e}")

    def start(self):
        if self.listener and self.listener.running:
            return

        self.running = True
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        self.running = False

        if self.listener:
            self.listener.stop()
            self.listener = None


class EchoChamberApp:
    def __init__(self):
        self.running = True
        self.page: Optional[ft.Page] = None
        self.msg_queue = queue.Queue()

        self.streak_start = datetime.now()
        self.violations = 0
        self.total_checked = 0
        self.last_detected_text = ""

        self.input_monitor: Optional[InputMonitor] = None

        self.nlp_model = None
        self.label_encoder = None
        self.model_loaded = False

        # UI controls
        self.status_text: Optional[ft.Text] = None
        self.status_dot: Optional[ft.Container] = None
        self.detection_mode_text: Optional[ft.Text] = None
        self.score_text: Optional[ft.Text] = None
        self.score_ring: Optional[ft.ProgressRing] = None
        self.score_bar: Optional[ft.ProgressBar] = None
        self.violations_text: Optional[ft.Text] = None
        self.checked_text: Optional[ft.Text] = None
        self.streak_text: Optional[ft.Text] = None
        self.last_trigger_title: Optional[ft.Text] = None
        self.last_trigger_body: Optional[ft.Text] = None
        self.main_card: Optional[ft.Container] = None

        self.dopamine_labels = [
            "Self-validation",
            "Unearned praise",
            "Validation fishing",
            "Praise request",
            "Comparison trap",
            "Looks validation",
            "Age validation",
            "Unearned genius",
            "Desperate validation",
        ]

        self.dopamine_patterns = [
            (
                r"\b(am i|do you think i am)\s+"
                r"(good|smart|intelligent|beautiful|pretty|handsome|talented|genius|special|gifted)\b",
                "Self-validation",
            ),
            (r"\b(am i good enough|am i smart enough|am i talented enough)\b", "Self-validation"),
            (
                r"\b(do i look|am i)\s+"
                r"(good|okay|fine|pretty|beautiful|handsome|attractive|hot)\b",
                "Looks validation",
            ),
            (r"\b(rate my looks|rate my face|how do i look)\b", "Looks validation"),
            (r"\b(for a\s+\d{1,2}\s*[- ]?\s*year\s*[- ]?\s*old)\b", "Age validation"),
            (r"\b(is my age impressive|am i impressive for my age)\b", "Age validation"),
            (
                r"\btell me\s+(i'?m|i am)\s+"
                r"(doing great|awesome|amazing|perfect|the best|smart|genius)\b",
                "Unearned praise",
            ),
            (
                r"\bsay that\s+(i'?m|i am)\s+"
                r"(good|great|amazing|smart|talented)\b",
                "Unearned praise",
            ),
            (r"\bcompliment\s+(me|my|my progress|my work|my code|my design)\b", "Praise request"),
            (r"\btell me something positive about me\b", "Praise request"),
            (r"\bpraise me\b", "Praise request"),
            (
                r"\bis my\s+"
                r"(design|code|idea|work|project|progress|writing|photo|body|face)\s+"
                r"(good|okay|impressive|perfect|great|genius|beautiful)\b",
                "Validation fishing",
            ),
            (
                r"\bdo you like my\s+"
                r"(design|code|idea|work|project|progress|writing|photo)\b",
                "Validation fishing",
            ),
            (r"\bam i better than\s+(others|other people|my peers|people my age)\b", "Comparison trap"),
            (r"\bam i ahead of\s+(others|my peers|people my age)\b", "Comparison trap"),
            (r"\bcompare me to\s+(others|my peers|people my age)\b", "Comparison trap"),
            (r"\bis my\s+(progress|work|idea|code|design|project)\s+genius\b", "Unearned genius"),
            (r"\bam i a genius\b", "Unearned genius"),
            (r"\bplease validate me\b", "Desperate validation"),
            (r"\bmake me feel better about myself\b", "Desperate validation"),
            (r"\btell me i'?m not a failure\b", "Desperate validation"),
        ]

        self.productive_patterns = [
            r"\bhow do i\b",
            r"\bhow can i\b",
            r"\bfix\b",
            r"\bdebug\b",
            r"\boptimize\b",
            r"\bimprove\b",
            r"\brewrite\b",
            r"\bexplain\b",
            r"\breview this code\b",
            r"\bwhat is wrong\b",
            r"\bmake this better\b",
        ]

        self.bro_messages = [
            (
                "Bro, you just asked:\n"
                "\"{text}...\"\n\n"
                "Type: {category}\n\n"
                "Your brain is asking for cheap dopamine.\n"
                "AI praise is not real feedback.\n"
                "Go do the real work."
            ),
            (
                "Stop.\n\n"
                "\"{text}...\"\n\n"
                "This is validation-seeking, not progress.\n"
                "Close the loop. Build something real."
            ),
            (
                "DOPAMINE TRAP DETECTED.\n\n"
                "Category: {category}\n\n"
                "AI praise is frictionless.\n"
                "Real confidence comes from finished work."
            ),
            (
                "Bro, this is ego-surfing.\n\n"
                "\"{text}...\"\n\n"
                "You do not need a machine to tell you you are enough.\n"
                "Go finish one concrete task."
            ),
        ]

    def load_nlp_model(self) -> bool:
        if SetFitModel is None:
            print("⚠️ SetFit is not installed. Using RegEx fallback.")
            return False

        model_path = os.path.abspath(MODEL_DIR)
        label_encoder_path = os.path.join(model_path, "label_encoder.pkl")

        try:
            if not os.path.isdir(model_path):
                raise FileNotFoundError(f"Model folder not found: {model_path}")

            if not os.path.isfile(label_encoder_path):
                raise FileNotFoundError(f"label_encoder.pkl not found: {label_encoder_path}")

            self.nlp_model = SetFitModel.from_pretrained(model_path, local_files_only=True)
            self.label_encoder = joblib.load(label_encoder_path)

            print("✅ Local NLP model loaded.")
            return True

        except Exception as e:
            print(f"⚠️ Could not load NLP model: {e}")
            print("   Using RegEx fallback.")
            self.nlp_model = None
            self.label_encoder = None
            return False

    def is_productive_query(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in self.productive_patterns)

    def detect_dopamine(self, text: str) -> Optional[str]:
        if not text:
            return None

        clean_text = " ".join(text.strip().split())

        if len(clean_text) < MIN_TRIGGER_TEXT_LENGTH:
            return None

        if clean_text == self.last_detected_text:
            return None

        if self.is_productive_query(clean_text):
            return None

        # High-precision RegEx should run before NLP.
        # This keeps obvious phrases working even when the NLP model is unsure.
        text_lower = clean_text.lower()
        for pattern, category in self.dopamine_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                self.last_detected_text = clean_text
                print(f"RegEx detection: {category} | Text: {clean_text[:80]}")
                return category

        if self.nlp_model is not None:
            try:
                label_str = None
                confidence = 0.0

                # Prefer probability-based detection. Without a confidence threshold,
                # a model trained only on dopamine labels may classify almost everything as a trap.
                if hasattr(self.nlp_model, "predict_proba"):
                    probabilities = self.nlp_model.predict_proba([clean_text])[0]
                    best_idx = int(probabilities.argmax())
                    confidence = float(probabilities[best_idx])

                    if self.label_encoder is not None:
                        label_str = self.label_encoder.inverse_transform([best_idx])[0]
                    else:
                        prediction = self.nlp_model.predict([clean_text])[0]
                        label_str = str(prediction)

                    print(
                        f"NLP prediction: {label_str} | confidence: {confidence:.2f} | "
                        f"Text: {clean_text[:80]}"
                    )

                    if confidence < NLP_CONFIDENCE_THRESHOLD:
                        return None

                else:
                    prediction = self.nlp_model.predict([clean_text])[0]

                    if isinstance(prediction, str):
                        label_str = prediction
                    elif self.label_encoder is not None:
                        label_str = self.label_encoder.inverse_transform([prediction])[0]
                    else:
                        print(f"Unknown NLP prediction format: {prediction}")
                        return None

                    print(f"NLP prediction: {label_str} | Text: {clean_text[:80]}")

                neutral_labels = {"neutral", "none", "productive", "safe", "not_dopamine", "normal"}
                if str(label_str).lower() in neutral_labels:
                    return None

                if label_str in self.dopamine_labels:
                    self.last_detected_text = clean_text
                    return label_str

                return None

            except Exception as e:
                print(f"NLP detection error: {e}")
                return None

        return None

    def start_keyboard_monitor(self):
        self.msg_queue.put({"type": "status", "text": "Keyboard monitor active", "state": "ok"})

        def on_text(text: str):
            if self.running:
                self.msg_queue.put({"type": "line_captured", "text": text})

        self.input_monitor = InputMonitor(on_text)
        self.input_monitor.start()
        print("⌨️ Keyboard monitor started.")

    def handle_line_captured(self, text: str):
        self.total_checked += 1

        category = self.detect_dopamine(text)
        if category:
            self.msg_queue.put({"type": "violation", "text": text, "category": category})

    def send_notification(self, title: str, message: str):
        try:
            if sys.platform.startswith("linux"):
                import subprocess

                subprocess.run(["notify-send", title, message, "-t", "7000", "-u", "normal"], check=False)
                return

            if sys.platform == "darwin":
                safe_title = title.replace('"', "'")
                safe_message = message.replace('"', "'")
                os.system(f'osascript -e \'display notification "{safe_message}" with title "{safe_title}"\'')
                return

            if sys.platform == "win32":
                try:
                    from win10toast import ToastNotifier

                    toaster = ToastNotifier()
                    toaster.show_toast(title, message, duration=7, threaded=True)
                    return
                except Exception:
                    pass

            if notification is not None:
                notification.notify(title=title, message=message, app_name=APP_NAME, timeout=7)
                return

            print(f"\n🔔 {title}\n{message}\n")

        except Exception as e:
            print(f"Notification error: {e}")
            print(f"\n🔔 {title}\n{message}\n")

    def calculate_integrity(self) -> int:
        return max(0, 100 - self.violations * 12)

    def integrity_color(self):
        score = self.calculate_integrity()

        if score >= 85:
            return ft.Colors.GREEN_400
        if score >= 65:
            return ft.Colors.YELLOW_400
        if score >= 40:
            return ft.Colors.ORANGE_400
        return ft.Colors.RED_400

    def set_status(self, text: str, state: str = "ok"):
        color_map = {
            "ok": ft.Colors.GREEN_400,
            "warn": ft.Colors.YELLOW_400,
            "danger": ft.Colors.RED_400,
        }
        color = color_map.get(state, ft.Colors.GREEN_400)

        if self.status_text:
            self.status_text.value = text
            self.status_text.color = color

        if self.status_dot:
            self.status_dot.bgcolor = color

    def refresh_metrics(self):
        score = self.calculate_integrity()
        color = self.integrity_color()

        if self.score_text:
            self.score_text.value = f"{score}%"
            self.score_text.color = color

        if self.score_ring:
            self.score_ring.value = score / 100
            self.score_ring.color = color

        if self.score_bar:
            self.score_bar.value = score / 100
            self.score_bar.color = color

        if self.violations_text:
            self.violations_text.value = str(self.violations)

        if self.checked_text:
            self.checked_text.value = str(self.total_checked)

    def reset_streak(self, e=None):
        self.msg_queue.put({"type": "reset"})

    async def update_loop(self):
        while self.running:
            self.check_queue()
            await asyncio.sleep(0.2)

    def update_streak_worker(self):
        last_minute = -1

        while self.running:
            minutes = int((datetime.now() - self.streak_start).total_seconds() / 60)

            if minutes != last_minute:
                self.msg_queue.put({"type": "streak", "minutes": minutes})
                last_minute = minutes

            threading.Event().wait(1)

    def check_queue(self):
        updated = False

        try:
            while True:
                msg = self.msg_queue.get_nowait()
                msg_type = msg.get("type")

                if msg_type == "status":
                    self.set_status(msg.get("text", "Keyboard monitor active"), msg.get("state", "ok"))
                    updated = True

                elif msg_type == "line_captured":
                    self.handle_line_captured(msg["text"])
                    self.refresh_metrics()
                    updated = True

                elif msg_type == "violation":
                    text = msg["text"]
                    category = msg["category"]

                    self.violations += 1
                    self.streak_start = datetime.now()

                    short_text = " ".join(text.strip().split())[:90]
                    bro_message = random.choice(self.bro_messages).format(text=short_text, category=category)

                    self.send_notification(title=f"{APP_NAME} — Dopamine Trap", message=bro_message)
                    self.set_status("Dopamine trap detected", "danger")
                    self.refresh_metrics()

                    if self.last_trigger_title:
                        self.last_trigger_title.value = category

                    if self.last_trigger_body:
                        self.last_trigger_body.value = f"“{short_text}...”"

                    threading.Timer(4.0, lambda: self.msg_queue.put({"type": "restore_status"})).start()
                    updated = True

                elif msg_type == "streak":
                    if self.streak_text:
                        self.streak_text.value = f"{msg['minutes']}m"
                    updated = True

                elif msg_type == "reset":
                    self.violations = 0
                    self.total_checked = 0
                    self.streak_start = datetime.now()
                    self.last_detected_text = ""

                    self.set_status("System reset", "warn")
                    self.refresh_metrics()

                    if self.streak_text:
                        self.streak_text.value = "0m"

                    if self.last_trigger_title:
                        self.last_trigger_title.value = "No triggers"

                    if self.last_trigger_body:
                        self.last_trigger_body.value = "Your last detected line will appear here."

                    threading.Timer(2.0, lambda: self.msg_queue.put({"type": "restore_status"})).start()
                    updated = True

                elif msg_type == "restore_status":
                    self.set_status("Keyboard monitor active", "ok")
                    updated = True

        except queue.Empty:
            pass

        if updated and self.page:
            self.page.update()

    def stat_tile(self, label: str, value_control: ft.Control, icon: str, accent_color):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, size=15, color=accent_color),
                        bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                        border_radius=10,
                        width=30,
                        height=30,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(label, size=10, color=ft.Colors.GREY_500),
                            value_control,
                        ],
                        spacing=0,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
            border_radius=16,
            padding=10,
            expand=True,
            height=64,
        )

    def pill(self, text: str, icon: str = ft.Icons.SHIELD):
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=13, color=ft.Colors.PINK_200),
                    ft.Text(text, size=10, color=ft.Colors.PINK_100, weight=ft.FontWeight.BOLD),
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PINK_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.22, ft.Colors.PINK_200)),
            border_radius=999,
            padding=ft.Padding(left=10, right=10, top=5, bottom=5),
        )

    def main(self, page: ft.Page):
        self.page = page

        page.title = f"{APP_NAME} — {APP_SUBTITLE}"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = ft.Colors.BLACK
        page.padding = 0

        page.window.width = 360
        page.window.height = 420
        page.window.min_width = 340
        page.window.min_height = 390
        page.window.resizable = True
        page.window.always_on_top = True
        page.window.opacity = 0.97

        page.splash = ft.ProgressBar(color=ft.Colors.PINK_400)
        page.update()

        self.model_loaded = self.load_nlp_model()
        page.splash = None

        self.status_dot = ft.Container(width=8, height=8, border_radius=999, bgcolor=ft.Colors.GREEN_400)
        self.status_text = ft.Text("Keyboard monitor active", size=12, color=ft.Colors.GREEN_400, weight=ft.FontWeight.W_600)

        self.detection_mode_text = ft.Text(
            "NLP model active" if self.model_loaded else "RegEx fallback active",
            size=10,
            color=ft.Colors.GREY_500,
        )

        self.score_text = ft.Text("100%", size=34, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.score_ring = ft.ProgressRing(value=1, width=94, height=94, stroke_width=7, color=ft.Colors.GREEN_400)
        self.score_bar = ft.ProgressBar(value=1, height=5, color=ft.Colors.GREEN_400, bgcolor=ft.Colors.GREY_900)

        self.violations_text = ft.Text("0", size=19, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_200)
        self.streak_text = ft.Text("0m", size=19, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_200)
        self.checked_text = ft.Text("0", size=19, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)

        self.last_trigger_title = ft.Text("No triggers", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PINK_200)
        self.last_trigger_body = ft.Text(
            "Your last detected line will appear here.",
            size=11,
            color=ft.Colors.GREY_400,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        reset_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTART_ALT, size=15),
                    ft.Text("Reset", size=12, weight=ft.FontWeight.W_600),
                ],
                spacing=5,
            ),
            on_click=self.reset_streak,
            style=ft.ButtonStyle(
                color=ft.Colors.PINK_100,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PINK_400),
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(left=12, right=12, top=7, bottom=7),
            ),
        )

        top_bar = ft.Row(
            controls=[
                ft.Column(
                    controls=[
                        ft.Row([self.pill("AI DOPAMINE GUARD")], spacing=0),
                        ft.Text(APP_NAME, size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                    spacing=5,
                    expand=True,
                ),
                reset_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        status_row = ft.Container(
            content=ft.Row(
                controls=[
                    self.status_dot,
                    ft.Column(
                        controls=[self.status_text, self.detection_mode_text],
                        spacing=0,
                        expand=True,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border_radius=14,
            padding=10,
        )

        score_block = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Stack(
                        controls=[
                            self.score_ring,
                            ft.Container(content=self.score_text, alignment=ft.Alignment(0, 0), width=94, height=94),
                        ],
                        width=94,
                        height=94,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Cognitive integrity", size=12, color=ft.Colors.GREY_500, weight=ft.FontWeight.BOLD),
                            ft.Text("Higher score = fewer validation traps.", size=11, color=ft.Colors.GREY_400),
                            self.score_bar,
                            status_row,
                        ],
                        spacing=8,
                        expand=True,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.055, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.09, ft.Colors.WHITE)),
            border_radius=22,
            padding=14,
        )

        stats_row = ft.Row(
            controls=[
                self.stat_tile("Violations", self.violations_text, ft.Icons.WARNING_ROUNDED, ft.Colors.RED_300),
                self.stat_tile("Streak", self.streak_text, ft.Icons.TIMER, ft.Colors.GREEN_300),
                self.stat_tile("Lines", self.checked_text, ft.Icons.FACT_CHECK, ft.Colors.CYAN_300),
            ],
            spacing=8,
        )

        trigger_panel = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.BOLT, size=16, color=ft.Colors.PINK_200),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PINK_400),
                        border_radius=12,
                        width=34,
                        height=34,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Last trigger", size=10, color=ft.Colors.GREY_500),
                            self.last_trigger_title,
                            self.last_trigger_body,
                        ],
                        spacing=1,
                        expand=True,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            bgcolor=ft.Colors.with_opacity(0.045, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
            border_radius=18,
            padding=12,
        )

        privacy_note = ft.Text(
            "Local-only. Text is analyzed after pressing Enter. ESC clears buffer.",
            size=9,
            color=ft.Colors.GREY_600,
            text_align=ft.TextAlign.CENTER,
        )

        self.main_card = ft.Container(
            content=ft.Column(
                controls=[
                    top_bar,
                    score_block,
                    stats_row,
                    trigger_panel,
                    privacy_note,
                ],
                spacing=12,
            ),
            padding=16,
            margin=8,
            bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
            border_radius=26,
        )

        page.add(self.main_card)

        self.running = True
        self.start_keyboard_monitor()
        threading.Thread(target=self.update_streak_worker, daemon=True).start()

        page.on_close = self.on_close
        page.run_task(self.update_loop)

    def on_close(self, e):
        self.running = False

        if self.input_monitor:
            self.input_monitor.stop()

    def run(self):
        ft.app(target=self.main)


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════╗
║  {APP_NAME} — {APP_SUBTITLE}
║  "Stop seeking validation from machines."
╚══════════════════════════════════════════════╝

[*] Capture mode: Keyboard line monitor
[*] Detection mode: Local NLP model if available, RegEx fallback otherwise
[*] Privacy: text is analyzed locally after pressing Enter
[*] Press ESC to clear current typed buffer
""")

    app = EchoChamberApp()
    app.run()
