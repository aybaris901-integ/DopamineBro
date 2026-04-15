import flet as ft
import re
import random
import time
import threading
from datetime import datetime
from plyer import notification

try:
    import pyperclip
except ImportError:
    print("Ошибка: установите модуль pyperclip командой: pip install pyperclip")
    exit(1)


class SinapsterFlet:
    def __init__(self):
        self.streak_start = datetime.now()
        self.violations = 0
        self.last_text = ""
        self.running = True

        self.dopamine_patterns = [
            (r"(am i|am I)\s+(good|smart|beautiful|pretty|handsome|talented|genius)", "Self-validation"),
            (r"tell me (i'?m|i am)\s+(doing great|awesome|perfect|the best)", "Unearned praise"),
            (r"is my (age|looks|design|code)\s+(impressive|good|okay)", "Validation fishing"),
            (r"compliment my", "Praise request"),
            (r"am i better than", "Comparison trap"),
            (r"do i look (good|okay|fine)", "Looks validation"),
            (r"for a \d+\-year\-old", "Age validation"),
            (r"is my (progress|work|idea) genius", "Unearned genius"),
            (r"tell me something positive about me", "Desperate validation"),
        ]

        self.bro_messages = [
            "Bro, you just asked: \"{text}...\"\nType: {category}\n\n"
            "⚠️ Your brain is asking for cheap dopamine.\n"
            "The neural network's opinion is NOT real.\n"
            "Go do real work, get real results.",

            "Stop. You're looking for praise from a machine.\n"
            "\"{text}...\" — seriously?\n\n"
            "This is a cognitive trap.\n"
            "Close the chat and do at least one useful thing.",

            "⚡ DOPAMINE TRASH DETECTED ⚡\n\n"
            "You asked: \"{text}...\"\n"
            "AI is programmed to flatter you.\n"
            "This is NOT real feedback.\n"
            "Your progress comes only from real actions."
        ]


        self.status_text = None
        self.violation_text = None
        self.streak_text = None
        self.page = None

    def detect_dopamine(self, text: str):
        if not text or len(text) < 5:
            return None
        text_lower = text.lower()
        for pattern, category in self.dopamine_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return category
        return None



    def show_bro_notification(self, text: str, category: str):
        # plyer.notification можно вызывать из любого потока (он потокобезопасен)
        if not self.running:
            return

        raw_msg = random.choice(self.bro_messages)
        msg = raw_msg.format(text=text[:60], category=category)

        try:
            notification.notify(
                title="Sinapster – Dopamine Trap",
                message=msg,
                app_name="Sinapster",
                timeout=5,  # секунд показа
                # app_icon="path/to/icon.ico"  # можно указать свою иконку
            )
        except Exception as e:
            print(f"Notification error: {e}")

        # Обновляем UI внутри главного окна (опционально)
        def update_ui():
            if self.page and self.running:
                self.violations += 1
                self.violation_text.value = f"⚠️ Violations: {self.violations}"
                self.streak_start = datetime.now()
                self.status_text.value = "⚠️ DOPAMINE TRAP DETECTED!"
                self.status_text.color = ft.Colors.RED_400
                self.page.update()

                # Возврат статуса через 3 секунды
                def restore_status():
                    if self.running and self.status_text:
                        self.status_text.value = "✓ Monitoring..."
                        self.status_text.color = ft.Colors.GREEN_400
                        self.page.update()

                threading.Timer(3.0, lambda: self.page.run_thread(restore_status)).start()

        if self.page:
            self.page.run_thread(update_ui)


    def reset_streak(self, e):
        # Вызывается из главного потока, можно обновлять напрямую
        self.streak_start = datetime.now()
        self.violations = 0
        self.violation_text.value = f" Violations: {self.violations}"
        self.status_text.value = "Streak reset"
        self.status_text.color = ft.Colors.YELLOW_400
        self.page.update()

        def restore():
                if self.running and self.status_text:
                    self.status_text.value = "🖳 Monitoring..."
                self.status_text.color = ft.Colors.GREEN_400
                self.page.update()
        threading.Timer(2.0, lambda: self.page.run_thread(restore)).start()

    def update_streak_display(self):
        """Фоновый поток – обновляет таймер чистого времени"""
        while self.running:
            if self.streak_text:
                minutes = int((datetime.now() - self.streak_start).total_seconds() / 60)
                # Обновляем UI в главном потоке через run_thread
                def update():
                    if self.streak_text:
                        self.streak_text.value = f"⏱️ Clean streak: {minutes} min"
                        self.page.update()
                if self.page:
                    self.page.run_thread(update)
            time.sleep(1.0)

    def monitor_clipboard(self):
        """Фоновый мониторинг буфера обмена"""
        time.sleep(1)
        while self.running:
            try:
                current_text = pyperclip.paste()
                if current_text and current_text != self.last_text:
                    self.last_text = current_text
                    category = self.detect_dopamine(current_text)
                    if category:
                        self.show_bro_notification(current_text, category)
                        print(f"\n[!] Dopamine trap detected: {category}")
                        print(f"    Text: {current_text[:100]}")
            except Exception as e:
                print(f"Clipboard error: {e}")
            time.sleep(1.5)



    def main(self, page: ft.Page):
        self.page = page
        page.title = "Sinapster - AI Dopamine Guard"
        page.window.width = 250
        page.window.height = 200
        page.window.resizable = True
        page.window.always_on_top = True
        page.window.opacity = 0.6
        page.bgcolor = ft.Colors.GREY_900
        page.theme_mode = ft.ThemeMode.DARK




        title = ft.Text(
            "Sinapster",
            size=28,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.PINK_400,
            text_align=ft.TextAlign.CENTER,
        )

        self.status_text = ft.Text(
            "🖳 Monitoring...",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_400,
        )

        self.violation_text = ft.Text(
            f"⚠️ Violations: {self.violations}",
            size=14,
            color=ft.Colors.RED_300,
        )

        self.streak_text = ft.Text(
            "⏱️ Clean streak: 0 min",
            size=14,
            color=ft.Colors.GREEN_300,
        )

        # Используем ft.Button вместо устаревшего ElevatedButton
        reset_btn = ft.Button(
            "Reset Streak",
            on_click=self.reset_streak,
            bgcolor=ft.Colors.GREY_800,
            color=ft.Colors.WHITE,
        )

        page.add(
            ft.Column(
                [
                    title,
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    self.status_text,
                    self.violation_text,
                    self.streak_text,
                    ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                    ft.Row([reset_btn], alignment=ft.MainAxisAlignment.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            )
        )

        self.running = True
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        threading.Thread(target=self.update_streak_display, daemon=True).start()

        page.on_close = self.on_close

    def on_close(self, e):
        self.running = False

    def run(self):
        ft.app(target=self.main)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║  Sinapster - AI Dopamine Guard (▀̿Ĺ̯▀̿ ̿) ║
    ║   "Stop seeking validation from AI"      ║
    ╚══════════════════════════════════════════╝

    [*] Monitoring clipboard...
    [*] Copy any text to AI chat for analysis
    [*] Close window to stop
    """)

    app = SinapsterFlet()
    app.run()

