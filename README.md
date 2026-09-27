# Bruce Script AI

AI-assisted script generator for Bruce firmware on the T-Embed CC1101 Plus.

## Current stack
- Python 3.10+
- Tkinter GUI (standard library)
- Ollama local API
- Default model: qwen2.5-coder:7b
- No Python packages required

## Run

1. Make sure Ollama is running and the model exists:
   ollama pull qwen2.5-coder:7b
2. Clone:
   git clone https://github.com/kris1019/bruce-script-ai.git
   cd bruce-script-ai
3. Start:
   run.bat

Or:
   python main.py

The app generates code for authorized/lab use and keeps a local script library.

## Configuration
Edit config.json to change the Ollama URL, model, and generation settings.
