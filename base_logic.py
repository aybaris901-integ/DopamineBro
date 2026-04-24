import flet as ft
import re
import random
import time
import threading
import queue
from datetime import datetime
from plyer import notification
import joblib
import asyncio
import os
import sys

# Импорты для NLP и CDP
from setfit import SetFitModel


try:
    import pyperclip
except ImportError:
    print("Ошибка: установите pyperclip: pip install pyperclip")
    exit(1)
from pynput import keyboard
class InputMonitor:
    """Глобальный перехватчик нажатий клавиш"""
    def __init__(self, on_text_captured_callback):
        self.current_line = []
        self.on_text_captured = on_text_captured_callback
        self.running = True
        self.listener = None

    def on_press(self, key):
        try:
            if hasattr(key, 'char') and key.char is not None:
                self.current_line.append(key.char)
            elif key == keyboard.Key.enter:
                if self.current_line:
                    text = ''.join(self.current_line)
                    # Вызываем ваш детектор дофамина
                    self.on_text_captured(text)
                    self.current_line = []
            elif key == keyboard.Key.backspace and self.current_line:
                self.current_line.pop()
            elif key == keyboard.Key.space:
                self.current_line.append(' ')
        except Exception as e:
            print(f"Ошибка в обработчике клавиш: {e}")

    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
        self.running = False

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

        self.msg_queue = queue.Queue()
        self.nlp_model = None
        self.label_encoder = None


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
        self.input_monitor = None
    # ---------- ИСПРАВЛЕННЫЙ ОТСТУП ----------

    async def _update_loop(self):
        """Асинхронный цикл, который запускается в главном потоке Flet"""
        while self.running:
            self.check_queue()  # обрабатываем очередь
            await asyncio.sleep(0.3)
    def load_nlp_model(self):
        import os
        model_path = os.path.abspath("dopamine_model")
        try:
            # Проверяем, существует ли папка
            if not os.path.isdir(model_path):
                raise FileNotFoundError(f"Папка модели не найдена: {model_path}")

            self.nlp_model = SetFitModel.from_pretrained(model_path, local_files_only=True)
            self.label_encoder = joblib.load(os.path.join(model_path, "label_encoder.pkl"))
            print("✅ NLP модель загружена")
            return True
        except Exception as e:
            print(f"⚠️ Не удалось загрузить NLP модель: {e}")
            print("   Будет использован fallback на RegEx")
            self.nlp_model = None
            self.label_encoder = None
            return False

    # ---------------------------------------

    def detect_dopamine(self, text: str):
        """Анализирует текст с помощью NLP, при неудаче использует RegEx"""
        if not text or len(text) < 5:
            return None

        if self.nlp_model is not None and self.label_encoder is not None:
            try:
                pred_idx = self.nlp_model.predict([text])[0]
                label_str = self.label_encoder.inverse_transform([pred_idx])[0]
                dopamine_labels = [
                    "Self-validation", "Unearned praise", "Validation fishing",
                    "Praise request", "Comparison trap", "Looks validation",
                    "Age validation", "Unearned genius", "Desperate validation"
                ]
                if label_str in dopamine_labels:
                    return label_str
            except Exception as e:
                print(f"NLP error: {e}")

        # Fallback RegEx
        text_lower = text.lower()
        for pattern, category in self.dopamine_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return category
        return None

    def start_keyboard_monitor(self):
        """Запускает глобальный перехват клавиатуры"""
        self.msg_queue.put({"type": "status", "text": "Keyboard monitor active"})

        def on_text(text):
            if not self.running:
                return
            category = self.detect_dopamine(text)
            if category:
                self.show_bro_notification(text, category)
                print(f"\n[!] Dopamine trap detected: {category}")
                print(f"    Text: {text[:100]}")

        self.input_monitor = InputMonitor(on_text)
        self.input_monitor.start()
        print("⌨️ Keyboard monitor started")

    def show_bro_notification(self, text: str, category: str):
        """Отправляет уведомление и кладёт событие нарушения в очередь"""
        if not self.running:
            return

        raw_msg = random.choice(self.bro_messages)
        msg = raw_msg.format(text=text[:60], category=category)
        self.msg_queue.put({
            "type": "show_notification",
            "text": text,
            "category": category
        })





    def reset_streak(self, e):
        self.msg_queue.put({"type": "reset_streak"})
        print(">>> reset_streak called")
        """Сбрасывает streak (вызывается из главного потока)"""
        #self.streak_start = datetime.now()
        #self.violations = 0
        #self.violation_text.value = f"⚠️ Violations: {self.violations}"
        #self.status_text.value = "Streak reset"
        #self.status_text.color = ft.Colors.YELLOW_400
        #self.page.update()

        # Возвращаем статус через 2 секунды
        def restore():
            if self.running and self.status_text:
                self.status_text.value = "🖳 Monitoring..."
                self.status_text.color = ft.Colors.GREEN_400
                self.page.update()
        threading.Timer(2.0, restore).start()  # restore уже в главном потоке

    def update_streak_display(self):
        last_min = -1
        while self.running:
            minutes = int((datetime.now() - self.streak_start).total_seconds() / 60)
            if minutes != last_min:
                self.msg_queue.put({"type": "streak_update", "minutes": minutes})
                last_min = minutes
            time.sleep(1.0)

    def _send_notification(self, title, message):
        """Кроссплатформенная отправка уведомлений"""
        try:
            if sys.platform == "win32":
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5, threaded=True)
            elif sys.platform == "darwin":  # macOS
                os.system(f"osascript -e 'display notification \"{message}\" with title \"{title}\"'")
            else:  # Linux
                os.system(f'notify-send "{title}" "{message}" -t 5000')
        except Exception as e:
            print(f"Notification fallback error: {e}")
            # Если ничего не работает, хотя бы напечатаем в консоль
            print(f"\n🔔 {title}\n{message}\n")

    # Внутри check_queue замените блок с notification.notify на вызов этого метода:


    def check_queue(self):

        updated = False
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg["type"] == "status" and self.status_text:
                    self.status_text.value = msg["text"]
                    updated = True
                elif msg["type"] == "show_notification":
                    # Увеличиваем счётчик нарушений
                    self.violations += 1
                    self.violation_text.value = f"⚠️ Violations: {self.violations}"
                    # Отправляем уведомление
                    raw_msg = random.choice(self.bro_messages)
                    msg_text = raw_msg.format(text=msg["text"][:60], category=msg["category"])
                    try:
                        notification.notify(
                            title="Sinapster – Dopamine Trap",
                            message=msg_text,
                            app_name="Sinapster",
                            timeout=5,
                        )
                    except Exception as e:
                        print(f"Notification error: {e}")
                    # Сбрасываем статус через 3 секунды (через очередь)
                    threading.Timer(3.0, lambda: self.msg_queue.put({"type": "restore_status"})).start()
                    updated = True
                elif msg["type"] == "streak_update" and self.streak_text:
                    self.streak_text.value = f"⏱️ Clean streak: {msg['minutes']} min"
                    updated = True
                elif msg["type"] == "reset_streak":
                    self.streak_start = datetime.now()
                    self.violations = 0
                    self.violation_text.value = f"⚠️ Violations: {self.violations}"
                    self.status_text.value = "Streak reset"
                    self.status_text.color = ft.Colors.YELLOW_400
                    updated = True
                    threading.Timer(2.0, lambda: self.msg_queue.put({"type": "restore_status"})).start()
                elif msg["type"] == "restore_status":
                    self.status_text.value = "🖳 Monitoring..."
                    self.status_text.color = ft.Colors.GREEN_400
                    updated = True
                # Внутри check_queue замените блок с notification.notify на вызов этого метода:
                elif msg["type"] == "show_notification":
                    self.violations += 1
                    self.violation_text.value = f"⚠️ Violations: {self.violations}"
                    raw_msg = random.choice(self.bro_messages)
                    msg_text = raw_msg.format(text=msg["text"][:60], category=msg["category"])
                    self._send_notification("Sinapster – Dopamine Trap", msg_text)
                    threading.Timer(3.0, lambda: self.msg_queue.put({"type": "restore_status"})).start()
                    updated = True
        except queue.Empty:
            pass
        if updated and self.page:
            self.page.update()


    def main(self, page: ft.Page):
        self.page = page
        page.title = "Sinapster - AI Dopamine Guard"
        page.window.width = 300
        page.window.height = 250
        page.window.resizable = True
        page.window.always_on_top = True
        page.window.opacity = 0.8
        page.bgcolor = ft.Colors.GREY_900
        page.theme_mode = ft.ThemeMode.DARK

        # Splash и загрузка модели
        page.splash = ft.ProgressBar()
        page.update()
        self.load_nlp_model()
        page.splash = None

        title = ft.Text("Sinapster", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.PINK_400,
                            text_align=ft.TextAlign.CENTER)
        self.status_text = ft.Text("🖳 Monitoring...", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.violation_text = ft.Text(f"⚠️ Violations: {self.violations}", size=14, color=ft.Colors.RED_300)
        self.streak_text = ft.Text("⏱️ Clean streak: 0 min", size=14, color=ft.Colors.GREEN_300)

        reset_btn = ft.Button("Reset Streak", on_click=self.reset_streak, bgcolor=ft.Colors.GREY_800,
                                  color=ft.Colors.WHITE)

        page.add(ft.Column([title, ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                            self.status_text, self.violation_text, self.streak_text,
                            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                            ft.Row([reset_btn], alignment=ft.MainAxisAlignment.CENTER)],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

        self.running = True
        self.start_keyboard_monitor()
        threading.Thread(target=self.update_streak_display, daemon=True).start()
        page.on_close = self.on_close

        # ЗАПУСКАЕМ АСИНХРОННЫЙ ЦИКЛ ОБНОВЛЕНИЯ (вместо page.on_interval)
        page.run_task(self._update_loop)

        # Остальные методы (detect_dopamine, start_keyboard_monitor, reset_streak, update_streak_display, on_close) остаются как у вас
    def on_close(self, e):
        self.running = False
        if self.input_monitor:
            self.input_monitor.stop()

    def run(self):
        ft.app(target=self.main)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║  Sinapster - AI Dopamine Guard (▀̿Ĺ̯▀̿ ̿) ║
    ║   "Stop seeking validation from AI"      ║
    ╚══════════════════════════════════════════╝

    [*] Monitoring AI chat via Chrome DevTools Protocol
    [*] Then open ChatGPT/Gemini/Claude and start typing
    """)

    app = SinapsterFlet()
    app.run()

