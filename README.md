# Assistant

A lightweight, offline-capable desktop assistant written in Python. It accepts voice or text phrases and runs mapped actions (open apps, search, run scripts, etc.) through a compact GUI and a configurable command set.

## Table of Contents

- Overview
- Features
- Requirements
- Installation (development)
- Quick start
- Command configuration
- Project structure
- Development notes
- Packaging (building an executable)
- Troubleshooting
- Contributing
- License

## Overview

`Assistant` is a small desktop assistant focused on local, configurable command execution. It provides a simple GUI (floating icon and modern form), voice/text input, and a pluggable command manager so you can add custom automations without relying on cloud services.

## Features

- Voice and text input handling
- Pluggable commands and actions defined in JSON
- Minimal modern GUI elements (floating icon, autocompletion list)
- Helper scripts to create a self-contained executable

## Requirements

- Python 3.10+ (project was developed with Python 3.12)
- Windows (packaging and GUI tested on Windows)
- See `requirements.txt` for Python dependencies used during development.

## Installation (development)

1. Clone the repository and change into its directory.

2. Create and activate a virtual environment (recommended):

   ```
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

## Quick start

Run the assistant in development mode:

```
python main.py
```

The app loads settings from `config/settings.json` and commands from `config/commands.json` by default.

## Command configuration

Commands are editable JSON files located in `config/commands.json`. The `core/command_manager.py` module handles loading and executing configured commands. Edit the JSON to add or change how phrases map to actions.

## Project structure

- `main.py` — application entrypoint
- `core/` — core functionality: speech, logging, command and config managers
- `ui/` — GUI code: floating icon, autocompletion, modern form
- `config/` — `commands.json` and `settings.json` for runtime configuration
- `resources/` — icons and other static assets
- `build_exe.py`, `build.bat` — helper scripts for building a packaged executable
- `requirements.txt` — pinned dependencies
- `build/` — produced packaging artifacts (PyInstaller output)

Key core modules:

- `core/command_manager.py` — load and dispatch commands
- `core/config_manager.py` — handle reading/writing project configuration
- `core/app_speech.py` — speech recognition and text-to-speech helpers
- `core/app_logger.py` — centralized logging utilities

## Development notes

- The app should gracefully handle missing or malformed configuration files. When editing `config/*.json`, verify JSON syntax to avoid runtime errors.
- If your environment lacks audio devices or a TTS backend, the app can be used in text-only mode. Check `core/app_speech.py` to see how audio backends are detected and how to stub them during development.
- Keep long-running or blocking actions off the main GUI thread (use threads or async) to prevent the UI from freezing.

Edge cases and testing ideas:

- Missing `config/` files: verify app logs clear error messages and falls back to safe defaults.
- Invalid command actions: verify malformed actions are rejected with logged errors.
- Large or slow external actions: ensure the UI remains responsive and timeouts are handled.

## Packaging (building an executable)

This repository contains a previous packaged output under `build/assistant/` showing a PyInstaller-style bundle. To create your own build:

1. Install PyInstaller in your virtualenv:

   ```
   pip install pyinstaller
   ```

2. Run the included build script (PowerShell):

   ```
   python build_exe.py
   ```

   Or run the batch file from Command Prompt or PowerShell:

   ```
   .\build.bat
   ```

After a successful build, inspect `build/assistant/` for the packaged executable and supporting files. Pay attention to any `warn-*.txt` logs created by PyInstaller which list missing modules or data.

## Troubleshooting

- App doesn't start: run `python main.py` from a terminal to see the traceback and logs.
- Configuration fails to load: validate JSON syntax in `config/*.json` and inspect `core/config_manager.py` logging for errors.
- Audio issues: ensure microphone and speakers are configured, or run in text-only mode.
- Packaging problems: inspect `build/` and PyInstaller warning files for missing resources or modules.

## Contributing

Contributions are welcome. Typical workflow:

1. Fork the project and create a feature branch.
2. Implement your change and run any local tests.
3. Open a pull request with a description of your change.

Please avoid committing generated files or large binaries from `build/` into source control.

## License

This project is licensed under the MIT License. See `LICENSE` for details.

## Contact

Open an issue or contact the repository owner for questions and support.
