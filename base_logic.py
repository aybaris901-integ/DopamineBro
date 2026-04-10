import tkinter as tk
from tkinter import ttk
import pyperclip
import time
import threading
import re
from datetime import datetime
from plyer import notification
from tkinter import messagebox


class Sinapster:
    def __init__(self):
        self.streak_start = datetime.now()
        self.violations = 0
        self.last_text = ""
        self.running = True

        # patterns of cheepy dopamine
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

        self.setup_gui()

        # monitoring
        self.monitor_clipboard()

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Sinapster - AI Dopamine Guard")
        self.root.geometry("300x180")
        self.root.attributes('-topmost', True)  # on the top win
        self.root.attributes('-alpha', 0.5)  # opacity

        # color schemas
        self.root.configure(bg='#334155')

        # title
        title = tk.Label(self.root, text="Sinapster",
                         font=('JetBrains Mono', 24, 'bold'),
                         bg='#334155', fg='#FF1493')
        title.pack(pady=5)

        # status
        self.status_label = tk.Label(self.root, text="( ͠° ͟ʖ ͡°)   Monitoring...",
                                     font=('Arial', 10, 'bold'),
                                     bg='#334155', fg='#a6e3a1')
        self.status_label.pack(pady=5)

        # Violation counter
        self.violation_label = tk.Label(self.root, text=f"ಠ_ಠ   Violations: {self.violations}",
                                        font=('Arial', 10),
                                        bg='#334155', fg='#f38ba8')
        self.violation_label.pack(pady=5)

        # Streak timer
        self.streak_label = tk.Label(self.root, text="� Clean streak: 0 min",
                                     font=('Arial', 10),
                                     bg='#334155', fg='#a6e3a1')
        self.streak_label.pack(pady=5)

        # Btn reset
        reset_btn = tk.Button(self.root, text="Reset Streak",
                              command=self.reset_streak,
                              bg='#313244', fg='#cdd6f4',
                              activebackground='#45475a')
        reset_btn.pack(pady=10)

        # timer's update
        self.update_streak_display()

    def detect_dopamine(self, text):
        """Analyzes text for dopamine addiction patterns"""
        if not text or len(text) < 5:
            return None

        text_lower = text.lower()

        for pattern, category in self.dopamine_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return category
        return None

    def show_bro_notification(self, text, category):
        """Shows a strong Bro notification"""
        bro_messages = [
            f"Bro, you just asked: \"{text[:50]}...\"\n"
            f"Type: {category}\n\n"
            "� Your brain is asking for cheap dopamine.\n"
            "The neural network's opinion is NOT real..\n"
            "Go do real work, get real results.",

            f"Stop. You're looking for praise from a machine.\n"
            f"\"{text[:40]}...\" — seriously?haha\n\n"
            "This is a cognitive trap.\n"
            "Close the chat and do at least one useful thing.",

            "⚡ DOPAMINE TRASH DETECTED ⚡\n\n"
            f"Your asked: \"{text[:60]}...\"\n"
            "AI is programmed to flatter you.\n"
            "This is NOT real feedback\n"
            "Your progress comes only from real actions"
        ]

        import random
        msg = random.choice(bro_messages)

        def show_warning():
            messagebox.showinfo(f"Sinapster", msg)

        root = tk.Tk()

        btn = tk.Button(root, text=msg, command=show_warning)

        btn.pack(pady=20)
        root.mainloop()




        # Updating the GUI
        self.violations += 1
        self.violation_label.config(text=f"⚠️ Violations: {self.violations}")

        # Resetting the streak when a violation occurs
        self.streak_start = datetime.now()

        # Change the status color to red for a couple of seconds
        self.status_label.config(text="� DOPAMINE TRAP DETECTED!", fg='#f38ba8')
        self.root.after(3000, lambda: self.status_label.config(text="� Monitoring...", fg='#a6e3a1'))

    def reset_streak(self):
        """Manual streak reset"""
        self.streak_start = datetime.now()
        self.violations = 0
        self.violation_label.config(text=f"⚠️ Violations: {self.violations}")
        self.status_label.config(text="� Streak reset", fg='#f9e2af')
        self.root.after(2000, lambda: self.status_label.config(text="� Monitoring...", fg='#a6e3a1'))

    def update_streak_display(self):
        """Updates the net time display"""
        if self.running:
            minutes = int((datetime.now() - self.streak_start).total_seconds() / 60)
            self.streak_label.config(text=f"� Clean streak: {minutes} min")
            self.root.after(1000, self.update_streak_display)

    def monitor_clipboard(self):
        """Monitors the clipboard in a separate thread"""

        def check():
            while self.running:
                try:
                    current_text = pyperclip.paste()

                    if current_text and current_text != self.last_text:
                        self.last_text = current_text

                        # Analyzes text
                        category = self.detect_dopamine(current_text)
                        if category:
                            # Show notification
                            self.show_bro_notification(current_text, category)

                            # Дополнительно выводим в консоль
                            print(f"\n[!] Dopamine trap detected: {category}")
                            print(f"    Text: {current_text[:100]}")

                except Exception as e:
                    print(f"Error: {e}")

                time.sleep(1.5)  # Check the every 1.5 sec

        thread = threading.Thread(target=check, daemon=True)
        thread.start()

    def run(self):
        """Starting GUI APP"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.running = False
            print("\nSinapster stopped. Stay hard, bro.")
        finally:
            self.running = False


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

    app = Sinapster()
    app.run()