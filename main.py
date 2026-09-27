import json
import os
import threading
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
LIBRARY = os.path.join(ROOT, "scripts")
os.makedirs(LIBRARY, exist_ok=True)

SYSTEM_PROMPT = """You are Bruce Script AI, an assistant for creating scripts for Bruce firmware on ESP32-based devices such as the T-Embed CC1101 Plus.
Use only APIs and syntax supported by the Bruce documentation supplied in the project context. Do not invent APIs.
Return a complete script when the user asks for one.
If required Bruce API information is missing, clearly say what information is needed instead of hallucinating.
Keep generated actions limited to devices and networks the user owns or is authorized to test.
"""

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def ollama_generate(prompt):
    cfg = load_config()
    payload = {
        "model": cfg["model"],
        "prompt": SYSTEM_PROMPT + "\n\nUSER REQUEST:\n" + prompt,
        "stream": False,
        "options": {"temperature": cfg.get("temperature", 0.2)}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg["ollama_url"].rstrip("/") + "/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=cfg.get("timeout_seconds", 180)) as r:
        result = json.loads(r.read().decode("utf-8"))
    return result.get("response", "").strip()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bruce Script AI")
        self.geometry("1100x700")
        self.minsize(850, 550)
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Bruce Script AI", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status = ttk.Label(top, text="Ready")
        self.status.pack(side="right")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0,10))

        left = ttk.Frame(body, padding=8)
        right = ttk.Frame(body, padding=8)
        body.add(left, weight=1)
        body.add(right, weight=2)

        ttk.Label(left, text="What should the script do?").pack(anchor="w")
        self.request = tk.Text(left, height=15, wrap="word")
        self.request.pack(fill="both", expand=True, pady=6)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        self.generate_btn = ttk.Button(buttons, text="Generate Script", command=self.generate)
        self.generate_btn.pack(side="left")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left", padx=6)
        ttk.Button(buttons, text="Load", command=self.load).pack(side="left")

        ttk.Label(right, text="Generated Bruce script").pack(anchor="w")
        self.output = tk.Text(right, wrap="none", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True, pady=6)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Copy", command=self.copy).pack(side="left")
        ttk.Button(bottom, text="Clear", command=lambda: self.output.delete("1.0", "end")).pack(side="left", padx=6)

    def set_status(self, text):
        self.after(0, lambda: self.status.config(text=text))

    def generate(self):
        prompt = self.request.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("Bruce Script AI", "Describe what you want the script to do.")
            return
        self.generate_btn.config(state="disabled")
        self.set_status("Generating...")
        threading.Thread(target=self._generate_worker, args=(prompt,), daemon=True).start()

    def _generate_worker(self, prompt):
        try:
            result = ollama_generate(prompt)
            self.after(0, lambda: self.output.delete("1.0", "end"))
            self.after(0, lambda: self.output.insert("1.0", result))
            self.set_status("Done")
        except Exception as e:
            self.set_status("Error")
            self.after(0, lambda: messagebox.showerror("Generation failed", str(e)))
        finally:
            self.after(0, lambda: self.generate_btn.config(state="normal"))

    def save(self):
        text = self.output.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            initialdir=LIBRARY,
            defaultextension=".txt",
            filetypes=[("Bruce script/text", "*.txt *.ino"), ("All files", "*.*")]
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.set_status("Saved")

    def load(self):
        path = filedialog.askopenfilename(initialdir=LIBRARY)
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.output.delete("1.0", "end")
                self.output.insert("1.0", f.read())
            self.set_status("Loaded")

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self.output.get("1.0", "end"))
        self.set_status("Copied")

if __name__ == "__main__":
    App().mainloop()
