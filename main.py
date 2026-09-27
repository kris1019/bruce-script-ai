import json
import queue
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_NAME = "Bruce Script AI"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"

PROFILES = {
    "Bruce BadUSB": (
        "Write a benign, authorized DuckyScript-style BadUSB keyboard script. "
        "Use recognizable DuckyScript commands such as DELAY, STRING, and ENTER "
        "where appropriate. Do not output Python or JavaScript for this profile."
    ),
    "Bruce BadBLE": (
        "Write a benign, authorized DuckyScript-style BadBLE keyboard script. "
        "Use recognizable DuckyScript commands such as DELAY, STRING, and ENTER "
        "where appropriate. Do not output Python or JavaScript for this profile."
    ),
    "Bruce JS App": (
        "Write JavaScript for a Bruce JS app. The output must be JavaScript, not Lua "
        "and not DuckyScript. Use only Bruce JS APIs that are explicitly known from "
        "the user's request; do not invent hardware APIs. If a device-specific API "
        "is unclear, provide a clearly marked JavaScript scaffold and explain the "
        "uncertainty in code comments."
    ),
    "Arduino/ESP32": (
        "Write an Arduino-compatible sketch for the requested board, using C++ "
        "and common Arduino conventions. State any assumptions in brief comments."
    ),
    "Python Utility": (
        "Write a Python 3 utility using the standard library unless the user asks "
        "otherwise. Include practical error handling and a short usage comment."
    ),
}


def data_directory():
    path = Path.home() / ".bruce_script_ai"
    path.mkdir(parents=True, exist_ok=True)
    return path


class BruceScriptAI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1120x800")
        self.root.minsize(850, 620)

        self.data_dir = data_directory()
        self.library_path = self.data_dir / "library.json"
        self.settings_path = self.data_dir / "settings.json"

        self.settings = self.load_settings()
        self.library = self.load_library()

        self.events = queue.Queue()
        self.stop_event = None
        self.active_response = None
        self.response_lock = threading.Lock()
        self.worker = None
        self.busy = False

        self.configure_theme()
        self.build_ui()
        self.refresh_library()
        self.root.after(100, self.process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_theme(self):
        self.bg = "#17191e"
        self.panel = "#20232a"
        self.input_bg = "#121419"
        self.fg = "#e5e7eb"
        self.muted = "#a0a6b3"
        self.accent = "#59a6ff"

        self.root.configure(bg=self.bg)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=self.bg,
            foreground=self.fg,
            fieldbackground=self.input_bg,
            troughcolor=self.panel,
            bordercolor="#383d48",
            lightcolor=self.panel,
            darkcolor=self.panel,
            focuscolor=self.accent,
            font=("TkDefaultFont", 10),
        )
        style.configure("TFrame", background=self.bg)
        style.configure("Panel.TFrame", background=self.panel)
        style.configure("TLabel", background=self.bg, foreground=self.fg)
        style.configure("Muted.TLabel", background=self.bg, foreground=self.muted)
        style.configure("Panel.TLabel", background=self.panel, foreground=self.fg)
        style.configure("TButton", padding=(10, 6))
        style.map(
            "TButton",
            background=[("active", "#343a46"), ("disabled", "#292c33")],
            foreground=[("disabled", "#777d88")],
        )
        style.configure("Accent.TButton", background="#2563a8", foreground="white")
        style.map("Accent.TButton", background=[("active", "#347bc2")])
        style.configure("TNotebook", background=self.bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 8), background=self.panel)
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#303642"), ("active", "#292e38")],
            foreground=[("selected", self.fg)],
        )
        style.configure("TCombobox", padding=5)
        style.configure("Treeview", background=self.input_bg, fieldbackground=self.input_bg)
        style.configure("Treeview.Heading", background=self.panel, foreground=self.fg)

    def load_settings(self):
        defaults = {"endpoint": DEFAULT_ENDPOINT, "model": DEFAULT_MODEL}
        try:
            with self.settings_path.open("r", encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                defaults.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
        return defaults

    def save_settings_to_disk(self):
        self.settings["endpoint"] = self.endpoint_var.get().strip()
        self.settings["model"] = self.model_var.get().strip()
        try:
            with self.settings_path.open("w", encoding="utf-8") as handle:
                json.dump(self.settings, handle, indent=2)
            self.set_status("Settings saved.")
        except OSError as exc:
            messagebox.showerror("Settings", f"Could not save settings:\n{exc}", parent=self.root)

    def load_library(self):
        try:
            with self.library_path.open("r", encoding="utf-8") as handle:
                items = json.load(handle)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    def save_library_to_disk(self):
        try:
            with self.library_path.open("w", encoding="utf-8") as handle:
                json.dump(self.library, handle, indent=2, ensure_ascii=False)
            return True
        except OSError as exc:
            messagebox.showerror("Library", f"Could not save the library:\n{exc}", parent=self.root)
            return False

    def build_ui(self):
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill="x", pady=(0, 12))
        ttk.Label(heading, text=APP_NAME, font=("TkDefaultFont", 18, "bold")).pack(side="left")
        ttk.Label(
            heading,
            text="Local Ollama script assistant",
            style="Muted.TLabel",
        ).pack(side="left", padx=(12, 0), pady=(5, 0))

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        self.workspace_tab = ttk.Frame(self.notebook, padding=12)
        self.library_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.workspace_tab, text="Workspace")
        self.notebook.add(self.library_tab, text="Library")
        self.notebook.add(self.settings_tab, text="Settings")

        self.build_workspace()
        self.build_library()
        self.build_settings()

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(10, 0))
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        ttk.Label(
            footer,
            text="Use scripts only on devices and systems you own or are authorized to test.",
            style="Muted.TLabel",
        ).pack(side="right")

    def make_text(self, parent, height=8, wrap="word"):
        return tk.Text(
            parent,
            height=height,
            wrap=wrap,
            bg=self.input_bg,
            fg=self.fg,
            insertbackground=self.fg,
            selectbackground="#355b87",
            selectforeground="white",
            relief="flat",
            padx=10,
            pady=8,
            undo=True,
            font=("TkFixedFont", 10),
        )

    def build_workspace(self):
        tab = self.workspace_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)

        profile_row = ttk.Frame(tab)
        profile_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(profile_row, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar(value="Bruce BadUSB")
        self.profile_combo = ttk.Combobox(
            profile_row,
            textvariable=self.profile_var,
            values=list(PROFILES),
            state="readonly",
            width=22,
        )
        self.profile_combo.pack(side="left", padx=(8, 18))
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_changed)
        ttk.Label(
            profile_row,
            text="The selected profile guides the output language and format.",
            style="Muted.TLabel",
        ).pack(side="left")

        ttk.Label(tab, text="Goal / instructions").grid(row=1, column=0, sticky="w", pady=(0, 5))
        self.goal_text = self.make_text(tab, height=6)
        self.goal_text.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.goal_text.insert(
            "1.0",
            "Describe the benign task, target board or app context, and any constraints.",
        )

        output_frame = ttk.Frame(tab)
        output_frame.grid(row=3, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        output_header = ttk.Frame(output_frame)
        output_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(output_header, text="Generated script").pack(side="left")
        self.output_info_var = tk.StringVar(value="")
        ttk.Label(output_header, textvariable=self.output_info_var, style="Muted.TLabel").pack(
            side="right"
        )

        output_wrap = ttk.Frame(output_frame)
        output_wrap.grid(row=1, column=0, sticky="nsew")
        output_wrap.columnconfigure(0, weight=1)
        output_wrap.rowconfigure(0, weight=1)
        self.output_text = self.make_text(output_wrap, height=18, wrap="none")
        self.output_text.grid(row=0, column=0, sticky="nsew")
        output_scroll_y = ttk.Scrollbar(output_wrap, orient="vertical", command=self.output_text.yview)
        output_scroll_y.grid(row=0, column=1, sticky="ns")
        output_scroll_x = ttk.Scrollbar(output_wrap, orient="horizontal", command=self.output_text.xview)
        output_scroll_x.grid(row=1, column=0, sticky="ew")
        self.output_text.configure(yscrollcommand=output_scroll_y.set, xscrollcommand=output_scroll_x.set)

        buttons = ttk.Frame(tab)
        buttons.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.generate_button = ttk.Button(
            buttons, text="Generate", style="Accent.TButton", command=self.generate
        )
        self.generate_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop_generation, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Copy", command=self.copy_output).pack(side="left", padx=(18, 0))
        ttk.Button(buttons, text="Save as…", command=self.save_output).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Add to Library…", command=self.add_to_library).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(buttons, text="Clear output", command=self.clear_output).pack(side="right")

    def build_library(self):
        tab = self.library_tab
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(1, weight=1)

        ttk.Label(tab, text="Search saved scripts").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.search_var = tk.StringVar()
        search = ttk.Entry(tab, textvariable=self.search_var)
        search.grid(row=0, column=1, sticky="ew", pady=(0, 5), padx=(10, 0))
        self.search_var.trace_add("write", lambda *_: self.refresh_library())

        left = ttk.Frame(tab)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.library_list = tk.Listbox(
            left,
            bg=self.input_bg,
            fg=self.fg,
            selectbackground="#355b87",
            selectforeground="white",
            relief="flat",
            highlightthickness=0,
            activestyle="none",
        )
        self.library_list.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=self.library_list.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.library_list.configure(yscrollcommand=list_scroll.set)
        self.library_list.bind("<<ListboxSelect>>", self.on_library_select)

        right = ttk.Frame(tab)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self.library_detail_var = tk.StringVar(value="Select a saved script to preview it.")
        ttk.Label(right, textvariable=self.library_detail_var, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        self.library_preview = self.make_text(right, height=20, wrap="none")
        self.library_preview.grid(row=1, column=0, sticky="nsew")
        self.library_preview.configure(state="disabled")

        actions = ttk.Frame(tab)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Load into Workspace", command=self.load_selected_script).pack(side="left")
        ttk.Button(actions, text="Delete selected", command=self.delete_selected_script).pack(
            side="left", padx=(8, 0)
        )

    def build_settings(self):
        tab = self.settings_tab
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text="Ollama settings", font=("TkDefaultFont", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14)
        )
        ttk.Label(tab, text="Server URL").grid(row=1, column=0, sticky="w", pady=6)
        self.endpoint_var = tk.StringVar(value=self.settings.get("endpoint", DEFAULT_ENDPOINT))
        ttk.Entry(tab, textvariable=self.endpoint_var).grid(
            row=1, column=1, sticky="ew", pady=6, padx=(12, 0)
        )

        ttk.Label(tab, text="Model").grid(row=2, column=0, sticky="w", pady=6)
        self.model_var = tk.StringVar(value=self.settings.get("model", DEFAULT_MODEL))
        ttk.Entry(tab, textvariable=self.model_var).grid(
            row=2, column=1, sticky="ew", pady=6, padx=(12, 0)
        )

        ttk.Button(tab, text="Save settings", command=self.save_settings_to_disk).grid(
            row=3, column=1, sticky="w", pady=(12, 4), padx=(12, 0)
        )
        ttk.Label(
            tab,
            text=(
                "Generation uses Ollama's streaming /api/chat endpoint. "
                "Make sure Ollama is running and the selected model is available locally."
            ),
            style="Muted.TLabel",
            wraplength=700,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(16, 0))

    def set_status(self, text):
        self.status_var.set(text)

    def on_profile_changed(self, _event=None):
        self.output_info_var.set(self.profile_var.get())

    def get_goal(self):
        return self.goal_text.get("1.0", "end-1c").strip()

    def get_output(self):
        return self.output_text.get("1.0", "end-1c")

    def generate(self):
        if self.busy:
            return
        goal = self.get_goal()
        if not goal or goal == "Describe the benign task, target board or app context, and any constraints.":
            messagebox.showinfo("Goal needed", "Enter a goal or instructions first.", parent=self.root)
            return

        endpoint = self.endpoint_var.get().strip().rstrip("/")
        model = self.model_var.get().strip()
        if not endpoint or not model:
            messagebox.showerror("Settings needed", "Enter both an Ollama URL and model.", parent=self.root)
            return

        profile = self.profile_var.get()
        self.settings.update({"endpoint": endpoint, "model": model})
        self.save_settings_to_disk_quietly()

        prompt = (
            f"Profile: {profile}\n"
            f"Output requirements: {PROFILES[profile]}\n\n"
            "Safety and response requirements:\n"
            "- Help with benign, authorized use only. Do not include credential theft, "
            "evasion, destructive actions, or covert persistence.\n"
            "- Return the requested script with concise comments where useful. "
            "Avoid markdown fences unless the user specifically requests them.\n"
            "- If essential details are missing, make safe assumptions and state them "
            "briefly in comments, or ask a concise clarification.\n\n"
            f"User goal:\n{goal}"
        )

        self.output_text.delete("1.0", "end")
        self.output_info_var.set(f"{profile} · {model}")
        self.stop_event = threading.Event()
        self.busy = True
        self.generate_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.set_status("Connecting to Ollama…")

        self.worker = threading.Thread(
            target=self.request_generation,
            args=(endpoint, model, prompt, self.stop_event),
            daemon=True,
        )
        self.worker.start()

    def save_settings_to_disk_quietly(self):
        try:
            with self.settings_path.open("w", encoding="utf-8") as handle:
                json.dump(self.settings, handle, indent=2)
        except OSError:
            pass

    def request_generation(self, endpoint, model, prompt, stop_event):
        response = None
        try:
            url = endpoint if endpoint.endswith("/api/chat") else endpoint + "/api/chat"
            payload = {
                "model": model,
                "stream": True,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a careful coding assistant. Follow the requested "
                            "profile's programming language and format exactly."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            }
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            response = urllib.request.urlopen(request, timeout=300)
            with self.response_lock:
                self.active_response = response
            self.events.put(("status", "Generating…"))

            for raw_line in response:
                if stop_event.is_set():
                    break
                if not raw_line.strip():
                    continue
                try:
                    item = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

                error = item.get("error")
                if error:
                    raise RuntimeError(str(error))

                message = item.get("message") or {}
                content = message.get("content", "")
                if content:
                    self.events.put(("chunk", content))
                if item.get("done"):
                    break

            self.events.put(("done", "stopped" if stop_event.is_set() else "complete"))
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = str(exc)
            self.events.put(("error", f"Ollama HTTP error {exc.code}: {detail or exc.reason}"))
        except urllib.error.URLError as exc:
            self.events.put(("error", f"Could not connect to Ollama: {exc.reason}"))
        except Exception as exc:
            if stop_event.is_set():
                self.events.put(("done", "stopped"))
            else:
                self.events.put(("error", str(exc)))
        finally:
            with self.response_lock:
                if self.active_response is response:
                    self.active_response = None
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    def process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "chunk":
                    self.output_text.insert("end", payload)
                    self.output_text.see("end")
                elif kind == "status":
                    self.set_status(payload)
                elif kind == "error":
                    self.busy = False
                    self.generate_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.set_status("Generation failed.")
                    messagebox.showerror("Generation error", payload, parent=self.root)
                elif kind == "done":
                    self.busy = False
                    self.generate_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    if payload == "stopped":
                        self.set_status("Generation stopped.")
                    else:
                        self.set_status("Generation complete.")
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)

    def stop_generation(self):
        if not self.busy or self.stop_event is None:
            return
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.set_status("Stopping…")
        with self.response_lock:
            response = self.active_response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def clear_output(self):
        if self.busy:
            messagebox.showinfo("Generation in progress", "Stop generation before clearing output.", parent=self.root)
            return
        self.output_text.delete("1.0", "end")
        self.output_info_var.set("")

    def copy_output(self):
        content = self.get_output()
        if not content.strip():
            self.set_status("Nothing to copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.set_status("Copied to clipboard.")

    def save_output(self):
        content = self.get_output()
        if not content.strip():
            messagebox.showinfo("Save script", "There is no output to save.", parent=self.root)
            return
        extension = {
            "Bruce BadUSB": ".txt",
            "Bruce BadBLE": ".txt",
            "Bruce JS App": ".js",
            "Arduino/ESP32": ".ino",
            "Python Utility": ".py",
        }.get(self.profile_var.get(), ".txt")
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save script",
            defaultextension=extension,
            filetypes=[
                ("Script files", "*.txt *.js *.ino *.py"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8")
            self.set_status(f"Saved {Path(path).name}.")
        except OSError as exc:
            messagebox.showerror("Save script", f"Could not save file:\n{exc}", parent=self.root)

    def add_to_library(self):
        content = self.get_output().strip()
        if not content:
            messagebox.showinfo("Library", "Generate or enter a script before adding it.", parent=self.root)
            return
        title = simpledialog.askstring(
            "Add to Library",
            "Name this script:",
            initialvalue=f"{self.profile_var.get()} script",
            parent=self.root,
        )
        if title is None:
            return
        title = title.strip() or "Untitled script"
        self.library.insert(
            0,
            {
                "title": title,
                "profile": self.profile_var.get(),
                "goal": self.get_goal(),
                "code": content,
                "created": datetime.now().isoformat(timespec="seconds"),
            },
        )
        if self.save_library_to_disk():
            self.refresh_library()
            self.set_status("Added script to library.")
            self.notebook.select(self.library_tab)

    def refresh_library(self):
        if not hasattr(self, "library_list"):
            return
        query = self.search_var.get().strip().lower()
        self.filtered_library_indices = []
        self.library_list.delete(0, "end")
        for index, item in enumerate(self.library):
            searchable = " ".join(
                str(item.get(key, "")) for key in ("title", "profile", "goal", "code")
            ).lower()
            if query and query not in searchable:
                continue
            self.filtered_library_indices.append(index)
            title = str(item.get("title", "Untitled"))
            profile = str(item.get("profile", "Unknown profile"))
            created = str(item.get("created", ""))[:10]
            self.library_list.insert("end", f"{title}  ·  {profile}  ·  {created}")

    def selected_library_index(self):
        selection = self.library_list.curselection()
        if not selection:
            return None
        visible_index = selection[0]
        if visible_index >= len(self.filtered_library_indices):
            return None
        return self.filtered_library_indices[visible_index]

    def on_library_select(self, _event=None):
        index = self.selected_library_index()
        if index is None:
            return
        item = self.library[index]
        details = f"{item.get('profile', 'Unknown profile')} · {item.get('created', '')}"
        self.library_detail_var.set(details)
        self.library_preview.configure(state="normal")
        self.library_preview.delete("1.0", "end")
        self.library_preview.insert("1.0", item.get("code", ""))
        self.library_preview.configure(state="disabled")

    def load_selected_script(self):
        index = self.selected_library_index()
        if index is None:
            messagebox.showinfo("Library", "Select a script first.", parent=self.root)
            return
        item = self.library[index]
        profile = item.get("profile", "Bruce BadUSB")
        if profile in PROFILES:
            self.profile_var.set(profile)
        self.goal_text.delete("1.0", "end")
        self.goal_text.insert("1.0", item.get("goal", ""))
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", item.get("code", ""))
        self.output_info_var.set(f"Loaded from library · {profile}")
        self.notebook.select(self.workspace_tab)
        self.set_status("Loaded script into Workspace.")

    def delete_selected_script(self):
        index = self.selected_library_index()
        if index is None:
            messagebox.showinfo("Library", "Select a script first.", parent=self.root)
            return
        item = self.library[index]
        if not messagebox.askyesno(
            "Delete script",
            f"Delete “{item.get('title', 'Untitled')}” from the library?",
            parent=self.root,
        ):
            return
        del self.library[index]
        if self.save_library_to_disk():
            self.refresh_library()
            self.library_detail_var.set("Select a saved script to preview it.")
            self.library_preview.configure(state="normal")
            self.library_preview.delete("1.0", "end")
            self.library_preview.configure(state="disabled")
            self.set_status("Script deleted from library.")

    def on_close(self):
        if self.busy and self.stop_event is not None:
            self.stop_event.set()
            with self.response_lock:
                response = self.active_response
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
        self.root.destroy()


def main():
    root = tk.Tk()
    BruceScriptAI(root)
    root.mainloop()


if __name__ == "__main__":
    main()