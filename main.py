import json
import os
import re
import threading
import time
import urllib.request as urlrequest
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(ROOT, "config.json")
PROFILE_PATH = os.path.join(ROOT, "knowledge", "script_types.json"))
LIBRARY = os.path.join(ROOT, "scripts")
os.makedirs(LIBRARY, exist_ok=True)

BASE = """\n}")

# placeholder_base"}