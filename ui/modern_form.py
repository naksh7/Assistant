# -*- coding: utf-8 -*-
"""Single consolidated settings + commands form using standard tkinter.

This module replaces the previous component-based UI and provides a single
form with two tabs: Settings (JSON editor) and Commands (list + editor).

The public entry points remain:
- open_modern_settings_form(parent, on_close_callback)
- open_settings_form(parent)

This keeps compatibility with the rest of the code (e.g. FloatingIcon).
"""

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
import os
import subprocess
import sys
import shutil
from pathlib import Path
from core.app_logger import logger
from core.config_manager import config_manager
from core.command_manager import command_manager
import re
import webbrowser

class SingleSettingsCommandsForm:
    """A simple Tkinter Toplevel containing Settings and Commands tabs."""

    def __init__(self, parent=None, floating_icon_instance=None, on_close_callback=None):
        self.parent = parent
        self.floating_icon_instance = floating_icon_instance
        self.on_close_callback = on_close_callback
        # Initialize commonly-late-assigned attributes to satisfy linters and
        # make instance shape explicit. These are placeholders and will be
        # overwritten by subsequent initialization logic below.
        self.win = None
        self.nb = None
        self.settings_frame = None
        self.commands_frame = None
        self.about_frame = None
        self.settings_canvas = None
        self.form_inner = None
        self.form_window = None
        self.settings_widgets = None
        self.cmd_tree = None
        self.entry_desc = None
        self.combo_action = None
        self.txt_command = None
        self.txt_phrases = None
        self.internal_info_label = None
        self.save_btn = None
        self.delete_btn = None
        self.test_btn = None
        self.clear_btn = None
        self._about_links = None
        self._preferred_width = None
        self._preferred_height = None
        # Taskbar icon image refs
        self._icon_img = None
        self._root_icon_img = None       

        # Create window
        if parent and hasattr(parent, 'root'):
            self.win = tk.Toplevel(parent.root)
        else:
            self.win = tk.Toplevel()        
        self.win.title("Assistant")
        
        # Desired size
        width, height = 900, 600
        
        # use helper to centre window (keeps init tidy and reusable)
        try:
            self.centre_window(width, height)
        except Exception:
            # fallback to a simple geometry if centering fails
            self.win.geometry(f"{width}x{height}+0+0")

        # Set window and taskbar icon (extracted to helper method)
        try:
            self.set_taskbar_icon()
        except Exception:
            # Do not let icon failures prevent the form from opening
            pass
        # Attempt to set application-wide font to Segoe UI for a consistent look
        try:
            # Configure ttk default style font
            try:
                style = ttk.Style()
                style.configure('.', font=('Segoe UI', 10))
            except Exception:
                pass
            # Configure named Tk fonts
            try:
                default_font = tkfont.nametofont('TkDefaultFont')
                default_font.configure(family='Segoe UI', size=10)
            except Exception:
                pass
            try:
                text_font = tkfont.nametofont('TkTextFont')
                text_font.configure(family='Segoe UI', size=10)
            except Exception:
                pass
            try:
                heading_font = tkfont.nametofont('TkHeadingFont')
                heading_font.configure(family='Segoe UI', size=12, weight='bold')
            except Exception:
                pass
        except Exception:
            pass
       
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # Notebook
        self.nb = ttk.Notebook(self.win)
        self.nb.pack(fill="both", expand=True)
       
        # Commands tab
        self.commands_frame = ttk.Frame(self.nb)
        self.nb.add(self.commands_frame, text="Commands")
        self._build_commands_tab()

        # Settings tab
        self.settings_frame = ttk.Frame(self.nb)
        self.nb.add(self.settings_frame, text="Settings")
        self._build_settings_tab()

        # About tab
        self.about_frame = ttk.Frame(self.nb)
        self.nb.add(self.about_frame, text="About")
        self._build_about_tab()

        # Load data
        self._load_settings()
        self._load_commands()
        
    def _build_settings_tab(self):
        # Form-based settings UI (scrollable) - make widgets expand to fill area
        # Scrollable canvas that resizes the inner frame to match width.
        # Place canvas and scrollbar inside a content frame so the footer
        # can be packed at the bottom of the settings tab reliably.
        content = ttk.Frame(self.settings_frame)
        content.pack(fill='both', expand=True)

        canvas = tk.Canvas(content)
        scrollbar = ttk.Scrollbar(content, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        # expose canvas for global scroll handling
        self.settings_canvas = canvas

        self.form_inner = ttk.Frame(canvas)
        # keep window id so we can set its width when canvas resizes
        self.form_window = canvas.create_window((0, 0), window=self.form_inner, anchor='nw')

        def _on_configure_inner(_event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_resize(_event):
            try:
                canvas.itemconfigure(self.form_window, width=_event.width)
            except Exception:
                pass

        self.form_inner.bind('<Configure>', _on_configure_inner)
        canvas.bind('<Configure>', _on_canvas_resize)

        # Bind mouse wheel globally while this window exists so wheel scrolls
        # the settings canvas when the Settings tab is active. Support Windows and X11.
        try:
            # Windows / macOS (MouseWheel)
            self.win.bind_all('<MouseWheel>', self._on_mousewheel)
            # Linux (Button-4/Button-5)
            self.win.bind_all('<Button-4>', self._on_mousewheel)
            self.win.bind_all('<Button-5>', self._on_mousewheel)
        except Exception:
            pass

        # Footer: Save button placed below the scrollable form so it doesn't scroll away
        footer = ttk.Frame(self.settings_frame)
        footer.pack(side='bottom', fill='x')
       
        footer_label = ttk.Label(footer, text='Developed in Python🐍 by Naksh.')        
        footer_label.pack(side='left', padx=8, pady=6)

        save_btn = ttk.Button(footer, text='Save Settings', command=self._save_settings)
        save_btn.pack(side='right', padx=4, pady=6)

        # Store widgets
        self.settings_widgets = {}

        # Application section
        app_frame = ttk.LabelFrame(self.form_inner, text='Application Settings')
        app_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(app_frame, 'language', 'Language', placeholder='Language tag for recognizer. Example: en-US, en-GB, es-ES')
        self._add_entry(app_frame, 'icon_size', 'Icon Size', placeholder='Size of the displayed icon in pixels. Typical values: 48-128')
        self._add_entry(app_frame, 'animation_fps', 'Animation FPS', placeholder='Animation frames per second for glow/rotation/pulse loops. Typical: 30-120')
        self._add_file_entry(app_frame, 'icon_path', 'Custom Icon', placeholder='Path to custom icon (png, ico, ...)', file_type='icon')
        self._add_file_entry(app_frame, 'browser_path', 'Browser Path', file_type='executable', placeholder='Path to browser executable (.exe)')
    

        # Developer / Floating Icon settings
        dev_frame = ttk.LabelFrame(self.form_inner, text='Developer Settings')
        dev_frame.pack(fill='both', expand=True, padx=6, pady=6)

        # Speech Recognition
        speech_frame = ttk.LabelFrame(dev_frame, text='Speech Recognition')
        speech_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(speech_frame, 'ambient_noise_duration', 'Ambient Noise Duration', placeholder='Longer durations produce a more reliable ambient noise estimate. Typical: 0.2-2.0 seconds')
        self._add_entry(speech_frame, 'listen_timeout', 'Listen Timeout', placeholder='Waits for the seconds mentioned. Example: 5 (waits up to 5s for speech to start) or empty (waits indefinitely)')
        self._add_entry(speech_frame, 'phrase_time_limit', 'Phrase Time Limit', placeholder='Listens for the seconds mentioned. Example: 10 (listens phrase to 10s)')
        self._add_entry(speech_frame, 'pause_threshold', 'Pause Threshold', placeholder='Pause between the two words. Smaller values cut phrases earlier (e.g., 0.5), larger values wait longer (e.g., 1.5). Typical: 0.5-1.5')
        self._add_entry(speech_frame, 'energy_threshold', 'Energy Threshold', placeholder='Energy threshold for detecting voice vs. silence. Integer; lower = more sensitive. Typical default: 300.')
        self._add_entry(speech_frame, 'operation_timeout', 'Operation Timeout', placeholder='Operation timeout for blocking recognizer operations (seconds). Accepts int/float (number of seconds) or None to disable timeout. Example: 5 or empty (None)')
        self._add_entry(speech_frame, 'calibration_interval', 'Calibration Interval', placeholder='Calibrate every n seconds. Integer; e.g., 300 = calibrate every 5 minutes. Use larger numbers to reduce blocking calls.')
        self._add_check(speech_frame, 'dynamic_energy_threshold', 'Dynamic Energy Threshold (True, lets the recognizer adapt to background noise automatically)')

        # Icon basic
        icon_frame = ttk.LabelFrame(dev_frame, text='Icon Settings')
        icon_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_check(icon_frame, 'always_on_top', 'Always On Top (True, window stays above other windows. Useful for quick access)')
        self._add_check(icon_frame, 'window_transparency', 'Window Transparency (True, allows the window to be transparent)')
        self._add_entry(icon_frame, 'opacity', 'Opacity', placeholder='Transparency level from 0.0 (invisible) to 1.0 (opaque). Typical: 0.7-1.0')

        # Glow
        glow_frame = ttk.LabelFrame(dev_frame, text='Glow Effect')
        glow_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(glow_frame, 'brightness_intensity', 'Brightness Intensity', placeholder='Intensity of the glow brightness effect.')
        self._add_entry(glow_frame, 'contrast_intensity', 'Contrast Intensity', placeholder='Intensity of the glow contrast effect. Typical: 0.1-0.5')
        self._add_entry(glow_frame, 'color_intensity', 'Color Intensity', placeholder='Intensity of the glow color effect. Typical: 0.05-0.2')

        # Pulse
        pulse_frame = ttk.LabelFrame(dev_frame, text='Pulse Animation')
        pulse_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(pulse_frame, 'pulse_speed', 'Pulse Speed', placeholder='Pulse (glow) speed controls how fast the sine wave oscillates. Larger = faster pulsing. Typical: 1.0 - 10.0')
        self._add_entry(pulse_frame, 'pulse_variation_speed', 'Pulse Variation Speed', placeholder='Variation speed adds secondary motion to avoid robotic pulses. Typical: 0.5-1.5')
        self._add_entry(pulse_frame, 'pulse_variation_intensity', 'Pulse Variation Intensity', placeholder='Variation intensity scales the secondary oscillation. Typical: 0.1-0.5')

        # Rotation
        rotation_frame = ttk.LabelFrame(dev_frame, text='Rotation Animation')
        rotation_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(rotation_frame, 'max_rotation_speed', 'Max Rotation Speed', placeholder='Max rotation speed in degrees per frame. Larger values = faster spinning. Typical: 5-60 (experiment for smoothness)')
        self._add_entry(rotation_frame, 'rotation_acceleration', 'Rotation Acceleration', placeholder='How quickly rotation_speed increases while processing (per frame step). Larger values accelerate faster. Typical: 0.1 - 2.0.')
        self._add_entry(rotation_frame, 'rotation_deceleration', 'Rotation Deceleration', placeholder='How quickly rotation_speed decreases when stopping. Larger = snappier stop. Typical: 0.1 - 2.0.')
        self._add_entry(rotation_frame, 'min_rotation_cycles', 'Min Rotation Cycles', placeholder='Minimum number of full rotation cycles to complete before stopping. Typical: 1-5.')

        # Shake
        shake_frame = ttk.LabelFrame(dev_frame, text='Shake Animation')
        shake_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(shake_frame, 'shake_intensity', 'Shake Intensity', placeholder='Shake intensity in pixels (max horizontal displacement). Typical: 2-20.')
        self._add_entry(shake_frame, 'shake_duration', 'Shake Duration', placeholder='Duration of the shake effect in seconds (e.g. 0.5)')
        self._add_entry(shake_frame, 'shake_frequency', 'Shake Frequency', placeholder='Frequency of the shake effect in Hz (e.g. 25)')

        # Position and Drag/Click
        pos_frame = ttk.LabelFrame(dev_frame, text='Position / Drag and Click')
        pos_frame.pack(fill='both', expand=True, padx=6, pady=6)
        self._add_entry(pos_frame, 'offset_x', 'Offset X', placeholder='These values are automatically updated when the user drags the icon')
        self._add_entry(pos_frame, 'offset_y', 'Offset Y', placeholder='These values are automatically updated when the user drags the icon')
        self._add_entry(pos_frame, 'drag_threshold', 'Drag Threshold', placeholder='Minimum movement in pixels to be considered a drag (vs click). Typical: 2-12')
        self._add_entry(pos_frame, 'click_timeout', 'Click Timeout (ms)', placeholder='Time threshold (ms) within which a quick press is treated as a click')

        # Configuration management section: open AppData, load defaults, reset
        cfg_frame = ttk.LabelFrame(self.form_inner, text='Configuration Management')
        cfg_frame.pack(fill='both', expand=True, padx=6, pady=6)

        def _open_appdata_folder():
            try:
                path = config_manager.get_user_config_directory()
                if not path:
                    messagebox.showerror('Error', 'User config directory not available', parent=self.win)
                    return
                os.startfile(str(path))
            except Exception as e:
                logger.exception(f'Error opening AppData folder: {e}')
                messagebox.showerror('Error', f'Failed to open AppData folder: {e}', parent=self.win)

        def _load_default_settings(skip_confirm: bool = False):
            if not skip_confirm:
                if not messagebox.askyesno('Load Default Settings', 'This will overwrite your current settings with the default settings. Continue?', parent=self.win):
                    return
            try:
                tpl_dir = Path(config_manager.get_template_config_directory())
                tpl_path = tpl_dir / 'settings.json'
                user_path = Path(config_manager.get_user_config_directory()) / 'settings.json'

                if not tpl_path.exists():
                    messagebox.showwarning('Not found', f'Template settings.json not found: {tpl_path}', parent=self.win)
                    return

                shutil.copy2(str(tpl_path), str(user_path))
                # Reload into memory and update UI
                try:
                    config_manager.reload_all()
                except Exception:
                    logger.exception('Error reloading config_manager after loading default settings')
                self._load_settings()
                messagebox.showinfo('Loaded', 'Default settings loaded', parent=self.win)
            except Exception as e:
                logger.exception(f'Error loading default settings: {e}')
                messagebox.showerror('Error', f'Failed to load default settings: {e}', parent=self.win)

        def _load_default_commands(skip_confirm: bool = False):
            if not skip_confirm:
                if not messagebox.askyesno('Load Default Commands', 'This will overwrite your current commands with the default commands. Continue?', parent=self.win):
                    return
            try:
                tpl_dir = Path(config_manager.get_template_config_directory())
                tpl_path = tpl_dir / 'commands.json'
                user_path = Path(config_manager.get_user_config_directory()) / 'commands.json'

                if not tpl_path.exists():
                    messagebox.showwarning('Not found', f'Template commands.json not found: {tpl_path}', parent=self.win)
                    return

                shutil.copy2(str(tpl_path), str(user_path))
                try:
                    config_manager.reload_all()
                except Exception:
                    logger.exception('Error reloading config_manager after loading default commands')
                self._load_commands()
                messagebox.showinfo('Loaded', 'Default commands loaded', parent=self.win)
            except Exception as e:
                logger.exception(f'Error loading default commands: {e}')
                messagebox.showerror('Error', f'Failed to load default commands: {e}', parent=self.win)

        def _reset_all():
            if not messagebox.askyesno('Reset All', 'This will reset all configuration to defaults. Your custom settings and commands will be lost. Continue?', parent=self.win):
                return
            try:
                # Call loaders without their individual confirmations
                _load_default_settings(skip_confirm=True)
                _load_default_commands(skip_confirm=True)
                config_manager.reload_all()
                self._load_settings()
                self._load_commands()
                config_manager.save_commands()
                self._save_settings()
            except Exception as e:
                logger.exception(f'Error resetting configuration: {e}')
                messagebox.showerror('Error', f'Failed to reset configuration: {e}', parent=self.win)

        btn_row = ttk.Frame(cfg_frame)
        btn_row.pack(fill='x', padx=4, pady=4)
        ttk.Button(btn_row, text='Open AppData Folder', command=_open_appdata_folder).pack(side='left', padx=4, pady=4)
        ttk.Button(btn_row, text='Load Default Settings', command=_load_default_settings).pack(side='left', padx=4, pady=4)
        ttk.Button(btn_row, text='Load Default Commands', command=_load_default_commands).pack(side='left', padx=4, pady=4)
        ttk.Button(btn_row, text='Reset All', command=_reset_all).pack(side='left', padx=4, pady=4)

    # --- Helper widget methods ---
    def _add_entry(self, parent, key, label, placeholder=None):
        frm = ttk.Frame(parent)
        frm.pack(fill='x', padx=4, pady=2)
        ttk.Label(frm, text=label+':', width=24).pack(side='left')
        ent = ttk.Entry(frm)
        ent.pack(side='left', fill='x', expand=True)
        # apply placeholder behavior so empty entries show the default message
        # Compute per-widget placeholder up-front so it's available even if
        # parts of the initialization raise; we'll always register the
        # widget with the placeholder metadata.
        ph = placeholder
        try:
            # pass per-widget placeholder into the behavior
            self._add_placeholder_behavior(ent, ph)
            # initialize placeholder text value appropriately
            try:
                if not ent.get():
                    ent.delete(0, 'end')
                    ent.insert(0, ph)
                    try:
                        ent.configure(foreground='gray')
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            # ignore placeholder wiring errors but still register widget below
            pass
        # Always register widget metadata including placeholder
        self.settings_widgets[key] = {'type': 'entry', 'widget': ent, 'placeholder': ph}

    def _add_file_entry(self, parent, key, label, file_type='icon', placeholder=None):
        frm = ttk.Frame(parent)
        frm.pack(fill='x', padx=4, pady=2)
        ttk.Label(frm, text=label+':', width=24).pack(side='left')
        ent = ttk.Entry(frm)
        ent.pack(side='left', fill='x', expand=True)
        # Compute per-widget placeholder and wire behavior; always register
        ph = placeholder if placeholder is not None else getattr(self, '_placeholder_text', 'Default values')
        try:
            # ensure per-widget placeholder is used instead of global default
            self._add_placeholder_behavior(ent, ph)
            # initialize placeholder text value
            if not ent.get():
                ent.delete(0, 'end')
                ent.insert(0, ph)
                try:
                    ent.configure(foreground='gray')
                except Exception:
                    pass
        except Exception:
            # ignore behavior wiring errors
            pass
        # Always register widget metadata including placeholder
        self.settings_widgets[key] = {'type': 'entry', 'widget': ent, 'placeholder': ph}
        def _browse():
            if file_type == 'icon':
                filetypes = [('Image files', '*.png *.jpg *.jpeg *.gif *.bmp *.ico'), ('All', '*.*')]
                init = 'resources'
            else:
                filetypes = [('Executable files', '*.exe'), ('All', '*.*')]
                init = 'C:/Program Files'
            fp = filedialog.askopenfilename(title='Select file', filetypes=filetypes, initialdir=init, parent=self.win)
            if fp:
                ent.delete(0, 'end')
                ent.insert(0, fp)

        btn = ttk.Button(frm, text='Browse', command=_browse)
        btn.pack(side='left', padx=4)

    def _add_folder_entry(self, parent, key, label, placeholder=None):
        """Add an entry with Browse (directory) and Open (explore) buttons."""
        frm = ttk.Frame(parent)
        frm.pack(fill='x', padx=4, pady=2)
        ttk.Label(frm, text=label+':', width=24).pack(side='left')
        ent = ttk.Entry(frm)
        ent.pack(side='left', fill='x', expand=True)

        ph = placeholder if placeholder is not None else getattr(self, '_placeholder_text', 'Default values')
        try:
            self._add_placeholder_behavior(ent, ph)
            if not ent.get():
                ent.delete(0, 'end')
                ent.insert(0, ph)
                try:
                    ent.configure(foreground='gray')
                except Exception:
                    pass
        except Exception:
            pass

        # Always register widget metadata including placeholder
        self.settings_widgets[key] = {'type': 'entry', 'widget': ent, 'placeholder': ph}

        def _browse_dir():
            fp = filedialog.askdirectory(title='Select folder', initialdir=os.path.expanduser('~'), parent=self.win)
            if fp:
                ent.delete(0, 'end')
                ent.insert(0, fp)

        def _open_dir():
            path = ent.get().strip()
            if not path:
                messagebox.showwarning('Open folder', 'No folder specified', parent=self.win)
                return
            if not os.path.exists(path):
                messagebox.showerror('Open folder', f'Path does not exist: {path}', parent=self.win)
                return
            try:
                if sys.platform.startswith('win'):
                    os.startfile(path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', path])
                else:
                    subprocess.Popen(['xdg-open', path])
            except Exception as e:
                logger.exception(f'Error opening folder {path}: {e}')
                messagebox.showerror('Open folder', f'Failed to open folder: {e}', parent=self.win)

        btn_browse = ttk.Button(frm, text='Browse', command=_browse_dir)
        btn_browse.pack(side='left', padx=4)
        btn_open = ttk.Button(frm, text='Open', command=_open_dir)
        btn_open.pack(side='left', padx=4)

    def _add_appdata_entry(self, parent, _key, label):
        """Add an entry that opens the AppData user config directory via a single 'Open' button.

        If the entry contains a path, the Open button will open that path. If empty,
        it falls back to config_manager.get_user_config_directory().
        """
        def _open_appdata():            
            path = config_manager.get_user_config_directory()          
            os.startfile(path)
                        
        frm = ttk.Frame(parent)
        frm.pack(fill='x', padx=4, pady=2)
        ttk.Label(frm, text=label+':', width=24).pack(side='left')
        
        btn_open = ttk.Button(frm, text='Open', command=_open_appdata)
        btn_open.pack(side='left', padx=4)      

    def _add_check(self, parent, key, label):
        var = tk.BooleanVar()
        chk = ttk.Checkbutton(parent, text=label, variable=var)
        chk.pack(anchor='w', padx=4, pady=2)
        self.settings_widgets[key] = {'type': 'check', 'var': var}

    def _set_widget_value(self, key, value):
        w = self.settings_widgets.get(key)
        if not w:
            return
        if w['type'] == 'entry':
            widget = w['widget']
            # Determine if the widget is currently readonly/disabled. For
            # ttk widgets the state may be managed via widget.state()/instate()
            # instead of the option returned by cget('state'), so check both.
            was_disabled = False
            try:
                is_readonly = False
                try:
                    state = widget.cget('state')
                    if state in ('disabled', 'readonly'):
                        is_readonly = True
                except Exception:
                    is_readonly = False

                # ttk widgets support instate(('readonly',)) / instate(('disabled',))
                try:
                    if hasattr(widget, 'instate') and widget.instate(('readonly',)):
                        is_readonly = True
                    if hasattr(widget, 'instate') and widget.instate(('disabled',)):
                        is_readonly = True
                except Exception:
                    pass

                if is_readonly:
                    was_disabled = True
                    # Try multiple ways to make it writable temporarily
                    try:
                        widget.configure(state='normal')
                    except Exception:
                        try:
                            widget.state(['!readonly', '!disabled'])
                        except Exception:
                            pass
            except Exception:
                pass

            # Now insert the value. If value is empty/None, show placeholder instead
            try:
                widget.delete(0, 'end')
            except Exception:
                pass
            if value is None or value == '':
                # insert placeholder text and style it. Prefer per-widget placeholder if present.
                ph = w.get('placeholder', getattr(self, '_placeholder_text', 'Default values'))
                try:
                    widget.insert(0, ph)
                    try:
                        widget.configure(foreground='gray')
                    except Exception:
                        pass
                except Exception:
                    # fallback to empty string
                    try:
                        widget.insert(0, '')
                    except Exception:
                        pass
            else:
                try:
                    widget.insert(0, str(value))
                    try:
                        widget.configure(foreground='black')
                    except Exception:
                        pass
                except Exception:
                    pass

            # Restore readonly state if we changed it
            if was_disabled:
                try:
                    widget.configure(state='readonly')
                except Exception:
                    try:
                        widget.state(['readonly'])
                    except Exception:
                        pass
        elif w['type'] == 'check':
            w['var'].set(bool(value))

    def _add_placeholder_behavior(self, ent: tk.Entry, placeholder: str = None):
        """Add simple placeholder behavior to an Entry widget.

        Accept a per-widget `placeholder` string. If omitted, falls back to
        `self._placeholder_text`. The placeholder is displayed in gray when
        the entry is empty. On focus, if the placeholder is present it is
        cleared so the user can type; on focus-out, if the entry is empty
        the placeholder is restored.
        """
        ph = placeholder if placeholder is not None else getattr(self, '_placeholder_text', 'Default values')

        def _focus_in(_ev=None):
            try:
                if ent.get() == ph:
                    ent.delete(0, 'end')
                    try:
                        ent.configure(foreground='black')
                    except Exception:
                        pass
            except Exception:
                pass

        def _focus_out(_ev=None):
            try:
                if not ent.get():
                    ent.insert(0, ph)
                    try:
                        ent.configure(foreground='gray')
                    except Exception:
                        pass
            except Exception:
                pass

        # Bind events
        try:
            ent.bind('<FocusIn>', _focus_in)
            ent.bind('<FocusOut>', _focus_out)
        except Exception:
            pass

        # Initialize placeholder if empty
        try:
            if not ent.get():
                ent.insert(0, ph)
                try:
                    ent.configure(foreground='gray')
                except Exception:
                    pass
        except Exception:
            pass

    def _get_widget_value(self, key):
        w = self.settings_widgets.get(key)
        if not w:
            return None
        if w['type'] == 'entry':
            try:
                val = w['widget'].get()
                ph = w.get('placeholder', getattr(self, '_placeholder_text', 'Default values'))
                if val == ph:
                    return ''
                return val
            except Exception:
                return ''
        elif w['type'] == 'check':
            return w['var'].get()
        return None

    def _snake_to_camel(self, s: str) -> str:
        # ambient_noise_duration -> Ambient_Noise_Duration
        parts = s.split('_')
        return '_'.join(p.capitalize() for p in parts)

    def _to_number(self, val, typ, default):
        try:
            if val is None or val == '':
                return default
            return typ(val)
        except Exception:
            return default

    def _on_mousewheel(self, event):
        """Global mouse wheel handler: scroll settings canvas when Settings tab is active."""
        try:
            # Only scroll when Settings tab is selected
            try:
                sel_widget = self.nb.nametowidget(self.nb.select())
            except Exception:
                sel_widget = None

            if sel_widget is not self.settings_frame:
                return

            # Determine scroll direction/amount
            if hasattr(event, 'delta'):
                # Windows / macOS: event.delta usually a multiple of 120
                lines = -1 * int(event.delta / 120)
            elif hasattr(event, 'num'):
                # X11: Button-4 = scroll up, Button-5 = scroll down
                if event.num == 4:
                    lines = -1
                else:
                    lines = 1
            else:
                return

            # Scroll the canvas
            if hasattr(self, 'settings_canvas') and self.settings_canvas:
                self.settings_canvas.yview_scroll(lines, 'units')
        except Exception:
            # swallow exceptions to avoid interfering with main app
            return

    def centre_window(self, width: int = None, height: int = None):
        """Position the toplevel window centered on parent (if provided) or screen.

        Accepts optional width/height; if omitted, will use current stored
        preferred size or the window's current size.
        """
        try:
            w = width or getattr(self, '_preferred_width', None) or self.win.winfo_width()
            h = height or getattr(self, '_preferred_height', None) or self.win.winfo_height()
            # ensure geometry info is up-to-date
            #self.win.update_idletasks()

            if self.parent and hasattr(self.parent, 'root'):
                px = self.parent.root.winfo_rootx()
                py = self.parent.root.winfo_rooty()
                pw = self.parent.root.winfo_width()
                ph = self.parent.root.winfo_height()
                x = px + (pw // 2) - (w // 2)
                y = py + (ph // 2) - (h // 2)
            else:
                sw = self.win.winfo_screenwidth()
                sh = self.win.winfo_screenheight()
                x = (sw // 2) - (w // 2)
                y = (sh // 2) - (h // 2)

            self.win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            # let caller handle errors; keep silent here to avoid UI interruption
            raise

    def set_taskbar_icon(self):
        """Set the window icon and (on Windows) the AppUserModelID for taskbar grouping.

        This method is best-effort and swallows errors so it won't prevent the
        form from opening if icon handling fails on a given platform or setup.
        """
        # resources folder is sibling of the ui package
        try:
            icon_path = Path(__file__).resolve().parents[1] / 'resources' / 'icon.ico'
        except Exception:
            return

        try:
            if icon_path.exists():
                # Preferred for .ico on Windows
                try:
                    self.win.iconbitmap(str(icon_path))
                except Exception:
                    # Fallback: try iconphoto (supports more formats)
                    try:
                        img = tk.PhotoImage(file=str(icon_path))
                        # keep reference to avoid GC
                        self._icon_img = img
                        try:
                            self.win.iconphoto(False, img)
                        except Exception:
                            pass
                    except Exception:
                        pass

                # If a parent/root window exists, also set its icon so the
                # taskbar (and other windows) inherit the same icon.
                try:
                    root_win = getattr(self.parent, 'root', None)
                    if root_win is not None:
                        try:
                            root_win.iconbitmap(str(icon_path))
                        except Exception:
                            try:
                                # try iconphoto on root
                                img2 = tk.PhotoImage(file=str(icon_path))
                                self._root_icon_img = img2
                                try:
                                    root_win.iconphoto(False, img2)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass

            # On Windows, set an explicit AppUserModelID so the taskbar groups
            # and displays the application's icon consistently. This is a
            # best-effort call and is safe to skip on other platforms.
            if sys.platform.startswith('win'):
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Akatsuki.Assistant')
                except Exception:
                    pass
        except Exception:
            # Do not let icon failures prevent the form from opening
            return

    def _build_commands_tab(self):
        # Use tk.PanedWindow instead of ttk.Panedwindow
        pan = tk.PanedWindow(self.commands_frame, orient='horizontal')
        pan.pack(fill='both', expand=True)

        # Make left pane bigger by default
        left = ttk.Frame(pan)   # wider starting size
        right = ttk.Frame(pan)  # smaller editor pane

        # Add with minsize so panes don't collapse
        pan.add(left, minsize=280)   # Left min 400px
        pan.add(right, minsize=520)  # Right min 250px

        # ---------------- Left Pane ----------------
        self.cmd_tree = ttk.Treeview(left, show='tree', selectmode='extended')
        self.cmd_tree.column('#0', stretch=True)
        self.cmd_tree.pack(side='left', fill='both', expand=True)

        self.cmd_tree.bind('<<TreeviewSelect>>', self._on_command_select)

        # ---------------- Right Pane ----------------
        form = ttk.Frame(right)
        form.pack(fill='both', expand=True)

    # (No inline warning label — validation uses messagebox warnings)

        ttk.Label(form, text='Description:').pack(anchor='w')
        self.entry_desc = ttk.Entry(form)
        self.entry_desc.pack(fill='x')

        ttk.Label(form, text='Action:').pack(anchor='w', pady=(6, 0))
        self.combo_action = ttk.Combobox(
            form, values=['browser', 'command', 'keys'], state='readonly'
        )
        self.combo_action.pack(fill='x')

        ttk.Label(form, text='Command / URL / Keys:').pack(anchor='w', pady=(6, 0))
        self.txt_command = tk.Text(form, height=8)
        self.txt_command.pack(fill='both', expand=True)

        ttk.Label(form, text='Phrases (one per line):').pack(anchor='w', pady=(6, 0))
        self.txt_phrases = tk.Text(form, height=4)
        self.txt_phrases.pack(fill='both', expand=True)

        try:
            self.txt_phrases.bind('<Return>', self._on_phrases_enter)
            self.txt_phrases.tag_configure('duplicate', background='#fff0f0')
            self.txt_phrases.tag_configure('conflict', background='#fff7e6')
        except Exception:
            pass

        # ---------------- Bottom Button Row ----------------
        bottom_btn_row = ttk.Frame(self.commands_frame)
        bottom_btn_row.pack(fill='x', padx=2, pady=(2, 2))

        # Left-side actions
        self.delete_btn = ttk.Button(bottom_btn_row, text='Delete', command=self._delete_command)
        self.delete_btn.pack(side='left', padx=4, pady=4)
        ttk.Button(bottom_btn_row, text='Import', command=self._import_commands).pack(side='left', padx=4, pady=4)
        ttk.Button(bottom_btn_row, text='Export', command=self._export_commands).pack(side='left', padx=4, pady=4)

        # Spacer frame to push Save/Test/Clear buttons to the right
        spacer = ttk.Frame(bottom_btn_row)
        spacer.pack(side='left', fill='x', expand=True)

        # Right-side actions
        self.save_btn = ttk.Button(bottom_btn_row, text='Save Command', command=self._save_command)
        self.save_btn.pack(side='right', padx=4, pady=4)
        self.test_btn = ttk.Button(bottom_btn_row, text='Test', command=self._test_command)
        self.test_btn.pack(side='right', padx=4, pady=4)
        self.clear_btn = ttk.Button(bottom_btn_row, text='Clear', command=self._clear_command)
        self.clear_btn.pack(side='right', padx=4, pady=4)

                
    def _build_about_tab(self):
        try:
            # Content area with scroll
            content = ttk.Frame(self.about_frame)
            content.pack(fill='both', expand=True, padx=6, pady=6)

            txt = tk.Text(content, wrap='word', cursor='arrow')
            txt.pack(side='left', fill='both', expand=True)
            sb = ttk.Scrollbar(content, orient='vertical', command=txt.yview)
            sb.pack(side='right', fill='y')
            # Slightly reduced vertical padding to avoid large gaps around content
            txt.configure(yscrollcommand=sb.set, padx=8, pady=4)

            # Fonts: prefer Segoe UI for a native GitHub-like look on Windows.
            def make_font(family, size, weight=None, slant=None):
                try:
                    kwargs = {'family': family, 'size': size}
                    if weight:
                        kwargs['weight'] = weight
                    if slant:
                        kwargs['slant'] = slant
                    return tkfont.Font(**kwargs)
                except Exception:
                    try:
                        # best-effort fallback to default named font
                        return tkfont.Font(size=size)
                    except Exception:
                        return None

            body_font = make_font('Segoe UI', 10)
            h1_font = make_font('Segoe UI', 16, weight='bold')
            h2_font = make_font('Segoe UI', 13, weight='bold')
            code_font = make_font('Segoe UI', 10)
            bold_font = make_font('Segoe UI', 10, weight='bold')
            italic_font = make_font('Segoe UI', 10, slant='italic')

            # Load README. Prefer the template directory provided by the
            # config manager (this covers packaged templates). Fall back to
            # bundled resources (source or PyInstaller _MEIPASS)
            try:
                readme_path = None    
                # resources packaged with the app (source or PyInstaller)
                if readme_path is None:                    
                    base = Path(__file__).resolve().parents[1] 
                                       
                readme_path = base / 'resources' / 'readme.md'

                if readme_path and readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        data = f.read()
                else:
                    data = 'README not found.'
            except Exception as e:
                data = f'Error loading README: {e}'

            # Simple markdown-like renderer (headings, lists, inline code, bold, italic, links)
            def parse_inline(s):
                """Return (clean_text, list_of_tags) where tags are (tagname, start, end, extra).
                extra is used for link URL when tagname startswith 'link'.
                """
                tags = []
                out = ''
                last = 0
                # Combined regex: link | code | bold | italic
                pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*')
                for m in pattern.finditer(s):
                    span_start, span_end = m.span()
                    # append text before match
                    out += s[last:span_start]
                    cur_start = len(out)
                    if m.group(1) and m.group(2):
                        # link
                        text = m.group(1)
                        url = m.group(2)
                        out += text
                        cur_end = len(out)
                        tags.append(('link', cur_start, cur_end, url))
                    elif m.group(3):
                        # inline code
                        text = m.group(3)
                        out += text
                        cur_end = len(out)
                        tags.append(('code', cur_start, cur_end, None))
                    elif m.group(4):
                        # bold
                        text = m.group(4)
                        out += text
                        cur_end = len(out)
                        tags.append(('bold', cur_start, cur_end, None))
                    elif m.group(5):
                        # italic
                        text = m.group(5)
                        out += text
                        cur_end = len(out)
                        tags.append(('italic', cur_start, cur_end, None))
                    last = span_end
                out += s[last:]
                return out, tags

            # maintain link tag -> url mapping
            self._about_links = getattr(self, '_about_links', {})
            link_counter = 0

            # Insert content line by line to handle headings and lists
            for raw_line in data.splitlines():
                line = raw_line.rstrip('\n')
                tag_for_line = None
                insert_text = ''

                # Headings (#, ##, ###)
                if line.startswith('### '):
                    insert_text = line[4:].strip() + '\n'
                    tag_for_line = 'h2'
                elif line.startswith('## '):
                    insert_text = line[3:].strip() + '\n'
                    tag_for_line = 'h1'
                elif line.startswith('# '):
                    insert_text = line[2:].strip() + '\n'
                    tag_for_line = 'h1'
                elif line.startswith('- '):
                    # list item
                    content_line = '• ' + line[2:].strip()
                    insert_text = content_line + '\n'
                    tag_for_line = 'list'
                else:
                    insert_text = line + '\n'

                # parse inline markdown and collect inline tags
                clean, inline_tags = parse_inline(insert_text)

                # record start index
                start_index = txt.index('end-1c')
                try:
                    txt.insert('end', clean)
                except Exception:
                    txt.insert('end', insert_text)
                    clean = insert_text
                    inline_tags = []

                # Apply line-level tag
                if tag_for_line:
                    txt.tag_add(tag_for_line, start_index, f"{start_index} + {len(clean)}c")

                # Apply inline tags
                for tname, s_off, e_off, extra in inline_tags:
                    s_idx = f"{start_index} + {s_off}c"
                    e_idx = f"{start_index} + {e_off}c"
                    if tname == 'link':
                        tag_name = f'about_link_{link_counter}'
                        link_counter += 1
                        self._about_links[tag_name] = extra
                        txt.tag_add(tag_name, s_idx, e_idx)
                        # bind click to open URL
                        def _make_cb(url):
                            return lambda e: webbrowser.open(url)
                        txt.tag_bind(tag_name, '<Button-1>', _make_cb(extra))
                        txt.tag_config(tag_name, foreground='#0366d6', underline=True)
                        txt.tag_bind(tag_name, '<Enter>', lambda e: txt.config(cursor='hand2'))
                        txt.tag_bind(tag_name, '<Leave>', lambda e: txt.config(cursor='arrow'))
                    elif tname == 'code':
                        txt.tag_add('code', s_idx, e_idx)
                    elif tname == 'bold':
                        txt.tag_add('bold', s_idx, e_idx)
                    elif tname == 'italic':
                        txt.tag_add('italic', s_idx, e_idx)

            # Configure tags (fonts/colors)
            if body_font:
                txt.tag_configure('body', font=body_font)
            # Use tighter spacing around headings to reduce excessive vertical gaps
            if h1_font:
                txt.tag_configure('h1', font=h1_font, spacing1=2, spacing3=2)
            if h2_font:
                txt.tag_configure('h2', font=h2_font, spacing1=1, spacing3=1)
            if code_font:
                txt.tag_configure('code', font=code_font, background='#f5f5f5')
            if bold_font:
                txt.tag_configure('bold', font=bold_font)
            if italic_font:
                txt.tag_configure('italic', font=italic_font)
            txt.tag_configure('list', lmargin1=24, lmargin2=36)

            # Make readonly
            try:
                txt.configure(state='disabled')
            except Exception:
                pass

        except Exception:
            # Don't let about tab errors stop the form
            logger.exception('Error building About tab')
            return

    def _load_settings(self):
        try:
            # Load base settings structure
            cfg = config_manager._settings.copy() if hasattr(config_manager, '_settings') else {}

            # Helper to safely get nested values
            def g(section, key, default=None):
                return cfg.get(section, {}).get(key, default)

            # Application
            self._set_widget_value('language', g('Speech_Recognition', 'Language', cfg.get('Language', 'en-IN')))
            self._set_widget_value('icon_size', g('Floating_Icon', 'Icon_Size', 80))
            self._set_widget_value('animation_fps', g('Floating_Icon', 'Animation_FPS', 66))
            self._set_widget_value('icon_path', g('Floating_Icon', 'Icon_Path', ''))  
            self._set_widget_value('browser_path', cfg.get('Default_Browser', ''))

            # Speech
            sp = cfg.get('Speech_Recognition', {})
            for k in ['ambient_noise_duration','listen_timeout','phrase_time_limit','pause_threshold','energy_threshold','operation_timeout','calibration_interval']:
                self._set_widget_value(k, sp.get(self._snake_to_camel(k), '') if isinstance(sp, dict) else sp.get(k, ''))
            # dynamic_energy_threshold
            self._set_widget_value('dynamic_energy_threshold', sp.get('Dynamic_Energy_Threshold', True))

            # Floating icon groups
            fi = cfg.get('Floating_Icon', {})
            self._set_widget_value('always_on_top', fi.get('Always_On_Top', True))
            self._set_widget_value('window_transparency', fi.get('Window_Transparency', True))
            self._set_widget_value('opacity', fi.get('Opacity', 0.9))

            glow = fi.get('Glow_Effect', {})
            self._set_widget_value('brightness_intensity', glow.get('Brightness_Intensity', 0.3))
            self._set_widget_value('contrast_intensity', glow.get('Contrast_Intensity', 0.1))
            self._set_widget_value('color_intensity', glow.get('Color_Intensity', 0.05))

            pulse = fi.get('Pulse_Animation', {})
            self._set_widget_value('pulse_speed', pulse.get('Pulse_Speed', 5.0))
            self._set_widget_value('pulse_variation_speed', pulse.get('Pulse_Variation_Speed', 0.7))
            self._set_widget_value('pulse_variation_intensity', pulse.get('Pulse_Variation_Intensity', 0.1))

            rot = fi.get('Rotation_Animation', {})
            self._set_widget_value('max_rotation_speed', rot.get('Max_Rotation_Speed', 30))
            self._set_widget_value('rotation_acceleration', rot.get('Rotation_Acceleration', 0.5))
            self._set_widget_value('rotation_deceleration', rot.get('Rotation_Deceleration', 0.8))
            self._set_widget_value('min_rotation_cycles', rot.get('Min_Rotation_Cycles', 1))

            shake = fi.get('Shake_Animation', {})
            self._set_widget_value('shake_intensity', shake.get('Shake_Intensity', 5))
            self._set_widget_value('shake_duration', shake.get('Shake_Duration', 0.5))
            self._set_widget_value('shake_frequency', shake.get('Shake_Frequency', 25))

            pos = fi.get('Position', {})
            self._set_widget_value('offset_x', pos.get('Offset_X', -150))
            self._set_widget_value('offset_y', pos.get('Offset_Y', -150))

            drag = fi.get('Drag_And_Click', {})
            self._set_widget_value('drag_threshold', drag.get('Drag_Threshold', 5))
            self._set_widget_value('click_timeout', drag.get('Click_Timeout', 200))

        except Exception as e:
            logger.exception(f"Error loading settings: {e}")
            messagebox.showerror('Error', f'Failed to load settings: {e}', parent=self.win)

    def _save_settings(self):
        try:
            # Collect form values and map back to expected settings structure
            final_data = {}

            # Default_Browser
            final_data['Default_Browser'] = self._get_widget_value('browser_path') or ''

            # Speech_Recognition
            sr = {}
            sr['Language'] = self._get_widget_value('language') or 'en-IN'
            sr['Energy_Threshold'] = self._to_number(self._get_widget_value('energy_threshold'), int, 300)
            sr['Dynamic_Energy_Threshold'] = bool(self._get_widget_value('dynamic_energy_threshold'))
            sr['Pause_Threshold'] = self._to_number(self._get_widget_value('pause_threshold'), float, 0.5)
            sr['Operation_Timeout'] = self._get_widget_value('operation_timeout')
            sr['Ambient_Noise_Duration'] = self._to_number(self._get_widget_value('ambient_noise_duration'), float, 0.2)
            sr['Listen_Timeout'] = self._to_number(self._get_widget_value('listen_timeout'), int, 5)
            sr['Phrase_Time_Limit'] = self._to_number(self._get_widget_value('phrase_time_limit'), int, 15)
            sr['Calibration_Interval'] = self._to_number(self._get_widget_value('calibration_interval'), int, 600)
            final_data['Speech_Recognition'] = sr

            # Floating_Icon
            fi = {}
            fi['Icon_Path'] = self._get_widget_value('icon_path') or ''
            fi['Icon_Size'] = self._to_number(self._get_widget_value('icon_size'), int, 80)
            fi['Animation_FPS'] = self._to_number(self._get_widget_value('animation_fps'), int, 66)
            fi['Always_On_Top'] = bool(self._get_widget_value('always_on_top'))
            fi['Window_Transparency'] = bool(self._get_widget_value('window_transparency'))
            fi['Opacity'] = self._to_number(self._get_widget_value('opacity'), float, 0.9)

            fi['Glow_Effect'] = {
                'Brightness_Intensity': self._to_number(self._get_widget_value('brightness_intensity'), float, 0.3),
                'Contrast_Intensity': self._to_number(self._get_widget_value('contrast_intensity'), float, 0.1),
                'Color_Intensity': self._to_number(self._get_widget_value('color_intensity'), float, 0.05),
            }

            fi['Pulse_Animation'] = {
                'Pulse_Speed': self._to_number(self._get_widget_value('pulse_speed'), float, 5.0),
                'Pulse_Variation_Speed': self._to_number(self._get_widget_value('pulse_variation_speed'), float, 0.7),
                'Pulse_Variation_Intensity': self._to_number(self._get_widget_value('pulse_variation_intensity'), float, 0.1),
            }

            fi['Rotation_Animation'] = {
                'Max_Rotation_Speed': self._to_number(self._get_widget_value('max_rotation_speed'), float, 30),
                'Rotation_Acceleration': self._to_number(self._get_widget_value('rotation_acceleration'), float, 0.5),
                'Rotation_Deceleration': self._to_number(self._get_widget_value('rotation_deceleration'), float, 0.8),
                'Min_Rotation_Cycles': self._to_number(self._get_widget_value('min_rotation_cycles'), int, 1),
            }

            fi['Shake_Animation'] = {
                'Shake_Intensity': self._to_number(self._get_widget_value('shake_intensity'), float, 5),
                'Shake_Duration': self._to_number(self._get_widget_value('shake_duration'), float, 0.5),
                'Shake_Frequency': self._to_number(self._get_widget_value('shake_frequency'), float, 25),
            }

            fi['Position'] = {
                'Offset_X': self._to_number(self._get_widget_value('offset_x'), int, -150),
                'Offset_Y': self._to_number(self._get_widget_value('offset_y'), int, -150),
            }

            fi['Drag_And_Click'] = {
                'Drag_Threshold': self._to_number(self._get_widget_value('drag_threshold'), int, 5),
                'Click_Timeout': self._to_number(self._get_widget_value('click_timeout'), int, 200),
            }

            final_data['Floating_Icon'] = fi

            # Merge with existing to preserve other keys
            final = config_manager._settings.copy() if hasattr(config_manager, '_settings') else {}
            final.update(final_data)

            if hasattr(config_manager, '_lock'):
                with config_manager._lock:
                    config_manager._settings.clear()
                    config_manager._settings.update(final)
            else:
                config_manager._settings = final

            if not config_manager.save_settings():
                messagebox.showerror('Error', 'config_manager.save_settings() failed', parent=self.win)
            else:
                # Reload configuration in memory and apply to running components
                try:
                    # Ensure config manager refreshes any cached views
                    if hasattr(config_manager, 'reload_all'):
                        config_manager.reload_all()
                except Exception:
                    logger.exception('Error reloading configuration after save')

                # If a floating icon instance was provided, apply new settings immediately
                try:
                    fi = getattr(self, 'floating_icon_instance', None)
                    if fi:
                        try:
                            fi.load_config()
                        except Exception:
                            logger.exception('Error calling FloatingIcon.load_config')
                        try:
                            fi.load_icon()
                        except Exception:
                            logger.exception('Error calling FloatingIcon.load_icon')
                        try:
                            fi.update_icon_display()
                        except Exception:
                            logger.exception('Error calling FloatingIcon.update_icon_display')
                        # Reapply window attributes (topmost / transparency / opacity)
                        try:
                            try:
                                fi.root.attributes('-topmost', bool(fi.config_always_on_top))
                            except Exception:
                                pass
                            if getattr(fi, 'window_transparency', False):
                                try:
                                    fi.root.wm_attributes('-transparentcolor', 'black')
                                except Exception:
                                    pass
                                try:
                                    fi.root.wm_attributes('-alpha', float(fi.opacity))
                                except Exception:
                                    pass
                            else:
                                try:
                                    fi.root.wm_attributes('-alpha', 1.0)
                                except Exception:
                                    pass
                        except Exception:
                            logger.exception('Error reapplying FloatingIcon window attributes')

                        try:
                            fi.center_window()
                        except Exception:
                            logger.exception('Error repositioning FloatingIcon after settings change')

                except Exception:
                    logger.exception('Error applying settings to running components')

                messagebox.showinfo('Saved', 'Settings saved successfully', parent=self.win)
        except Exception as e:
            logger.exception(f"Error saving settings: {e}")
            messagebox.showerror('Error', f'Failed to save settings: {e}', parent=self.win)

    def _reload_template(self):
        try:
            # Attempt to reload template by resetting from config_manager template location
            if hasattr(config_manager, 'get_template_config_directory'):
                tpl_dir = config_manager.get_template_config_directory()
                tpl_path = tpl_dir / 'settings.json'
                if tpl_path.exists():
                    with open(tpl_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # populate widgets from template
                        # Set speech
                        sp = data.get('Speech_Recognition', {})
                        self._set_widget_value('language', sp.get('Language', 'en-IN'))
                        for k in ['ambient_noise_duration','listen_timeout','phrase_time_limit','pause_threshold','energy_threshold','operation_timeout','calibration_interval']:
                            self._set_widget_value(k, sp.get(self._snake_to_camel(k), ''))

                        fi = data.get('Floating_Icon', {})
                        self._set_widget_value('icon_path', fi.get('Icon_Path', ''))
                        self._set_widget_value('icon_size', fi.get('Icon_Size', 80))
                        self._set_widget_value('animation_fps', fi.get('Animation_FPS', 66))
                        self._set_widget_value('always_on_top', fi.get('Always_On_Top', True))
                        self._set_widget_value('window_transparency', fi.get('Window_Transparency', True))
                        self._set_widget_value('opacity', fi.get('Opacity', 0.9))
                        return
            messagebox.showwarning('Not available', 'Template reload not available', parent=self.win)
        except Exception as e:
            logger.exception(f"Error reloading template: {e}")
            messagebox.showerror('Error', str(e), parent=self.win)

    def _load_commands(self):
        try:
            all_cmds = config_manager.get_all_commands() if hasattr(config_manager, 'get_all_commands') else command_manager.commands
            self.commands = {k: v for k, v in (all_cmds or {}).items() if k != 'settings'}
            # populate tree
            for iid in self.cmd_tree.get_children():
                self.cmd_tree.delete(iid)
            for name in sorted(self.commands.keys()):
                # Insert only the description text, no columns
                self.cmd_tree.insert('', 'end', iid=name, text=name)
        except Exception as e:
            logger.exception(f"Error loading commands: {e}")
            messagebox.showerror('Error', f'Failed to load commands: {e}', parent=self.win)

    # --- Internal command (read-only) handling helpers ---
    def _is_internal_command(self, data: dict) -> bool:
        try:
            return (data or {}).get('Action', '').lower() == 'internal'
        except Exception:
            return False

    def _set_command_editor_readonly(self, readonly: bool, internal: bool = False):
        """Enable / disable widgets for editing.

        If internal=True, show explanatory label. Readonly disables Save/Delete/Test buttons.
        """
        try:
            state_normal = 'normal'
            # Entry (description)
            try:
                self.entry_desc.configure(state='readonly' if readonly else 'normal')
            except Exception:
                pass
            # Action combo
            try:
                self.combo_action.configure(state='disabled' if readonly else 'readonly')
            except Exception:
                pass
            # Text widgets
            for widget in (self.txt_command, self.txt_phrases):
                try:
                    widget.configure(state='disabled' if readonly else 'normal')
                except Exception:
                    pass
            # Buttons
            for btn in (self.save_btn, self.delete_btn, self.test_btn):
                try:
                    if btn:
                        btn.configure(state='disabled' if readonly else state_normal)
                except Exception:
                    pass
            # Clear button stays enabled to let user start new command
            try:
                if self.clear_btn:
                    self.clear_btn.configure(state=state_normal)
            except Exception:
                pass            
        except Exception:
            logger.exception('Error toggling readonly state for command editor')

    def _on_command_select(self, _event=None):
        sel = self.cmd_tree.selection()
        if not sel:
            return
        name = sel[0]
        data = self.commands.get(name, {})
        self.entry_desc.delete(0, 'end')
        self.entry_desc.insert(0, name)
        action_val = data.get('Action', 'command')
        # If internal, temporarily allow setting the value even if not in values list
        if action_val == 'internal':
            try:
                # Temporarily make combo editable to set value
                self.combo_action.configure(state='normal')
                self.combo_action.set('internal')
            except Exception:
                pass
        else:
            self.combo_action.set(action_val)
        self.txt_command.delete('1.0', 'end')
        self.txt_command.insert('1.0', data.get('Command', ''))
        phrases = data.get('Phrases', [])
        self.txt_phrases.delete('1.0', 'end')
        self.txt_phrases.insert('1.0', '\n'.join(phrases))
        # Apply readonly state depending on whether command is internal
        is_internal = self._is_internal_command(data)
        self._set_command_editor_readonly(is_internal, internal=is_internal)
        # After setting, if internal keep combo disabled; if not, ensure normal state
        if not is_internal:
            try:
                self.combo_action.configure(state='readonly')
            except Exception:
                pass

    def _clear_command(self):
        """Clear the command editor fields and any validation highlights."""
        try:
            # Do not change tree selection; simply clear the editor fields
            self.entry_desc.delete(0, 'end')
            self.combo_action.set('command')
            self.txt_command.delete('1.0', 'end')
            self.txt_phrases.delete('1.0', 'end')
            # clear any existing validation highlights
            try:
                self.txt_phrases.tag_remove('duplicate', '1.0', 'end')
                self.txt_phrases.tag_remove('conflict', '1.0', 'end')
            except Exception:
                pass
            # Ensure editor becomes editable when starting a new command
            self._set_command_editor_readonly(False)
        except Exception:
            # swallow errors to avoid interrupting UI
            return

    def _delete_command(self):
        sel = list(self.cmd_tree.selection())
        if not sel:
            return

        # Filter out internal commands (read-only)
        internal_blocked = [name for name in sel if self._is_internal_command(self.commands.get(name, {}))]
        editable_selection = [name for name in sel if name not in internal_blocked]

        if internal_blocked and not editable_selection:
            try:
                messagebox.showinfo('Read-only', 'Selected command(s) are internal and cannot be deleted.', parent=self.win)
            except Exception:
                pass
            return
        elif internal_blocked:
            try:
                messagebox.showinfo('Partial Delete', 'Internal command(s) were skipped and will not be deleted.', parent=self.win)
            except Exception:
                pass
            sel = editable_selection

        # Build numbered confirmation message
        lines = ['Confirm to delete below commands :']
        for i, name in enumerate(sel, start=1):
            lines.append(f"{i}. {name}")
        msg = '\n'.join(lines)

        if not messagebox.askyesno('Delete', msg, parent=self.win):
            return

        # Attempt to remove each selected command (best-effort). Save once at the end.
        removed_any = False
        for name in sel:
            try:
                if hasattr(config_manager, 'remove_command'):
                    # prefer config_manager API
                    try:
                        config_manager.remove_command(name)
                    except TypeError:
                        # some implementations may accept a save flag
                        try:
                            config_manager.remove_command(name, save=False)
                        except Exception:
                            raise
                else:
                    # modify local via set_setting fallback
                    try:
                        config_manager.set_setting(f'commands.{name}', None)
                    except Exception:
                        # last resort: manipulate command_manager
                        if name in getattr(command_manager, 'commands', {}):
                            del command_manager.commands[name]
                removed_any = True
            except Exception:
                # best-effort: remove from command_manager if present
                try:
                    if name in getattr(command_manager, 'commands', {}):
                        del command_manager.commands[name]
                        removed_any = True
                except Exception:
                    pass

        # Persist changes if we removed anything
        try:
            if removed_any and hasattr(config_manager, 'save_commands'):
                config_manager.save_commands()
        except Exception:
            logger.exception('Error saving commands after deletion')

        self._load_commands()

    def _get_command_editor_data(self):
        desc = self.entry_desc.get().strip()
        action = self.combo_action.get() or 'command'
        cmd = self.txt_command.get('1.0', 'end').strip()
        phrases = [p.strip() for p in self.txt_phrases.get('1.0', 'end').splitlines() if p.strip()]
        return desc, {'Action': action, 'Command': cmd, 'Phrases': phrases}

    def _on_phrases_enter(self, _event=None):
        """Validate phrases when Enter is pressed: mark duplicates and conflicts.

        - duplicate: repeated line inside the current editor
        - conflict: phrase already used in another command
        Returns 'break' to allow normal newline insertion to continue.
        """
        try:
            text = self.txt_phrases.get('1.0', 'end')
            lines = [l.rstrip('\r') for l in text.splitlines()]

            # clear previous tags
            try:
                self.txt_phrases.tag_remove('duplicate', '1.0', 'end')
                self.txt_phrases.tag_remove('conflict', '1.0', 'end')
            except Exception:
                pass

            # find duplicates within editor (case-insensitive)
            seen = {}
            duplicates = set()
            for idx, raw in enumerate(lines, start=1):
                val = raw.strip()
                if not val:
                    continue
                key = val.lower()
                if key in seen:
                    duplicates.add(idx)
                    duplicates.add(seen[key])
                else:
                    seen[key] = idx

            # find conflicts with existing commands via config_manager helper
            # Build owner->phrases mapping for message grouping (best-effort)
            owner_to_phrases = {}
            try:
                phrases_info = command_manager.get_all_phrases_with_descriptions() or []
                for info in phrases_info:
                    ph = (info.get('phrase') or '').strip()
                    owner = info.get('description') or info.get('command') or ''
                    if ph:
                        owner_to_phrases.setdefault(owner or 'Unknown', []).append(ph)
            except Exception:
                try:
                    for name, data in (getattr(command_manager, 'commands', {}) or {}).items():
                        for ph in data.get('Phrases', []):
                            owner_to_phrases.setdefault(name or 'Unknown', []).append(ph)
                except Exception:
                    owner_to_phrases = {}

            # Ask config_manager to find conflicts (preferred). Exclude the
            # current description so editing an existing command doesn't flag
            # its own phrases as conflicts.
            conflicts_from_mgr = {}
            try:
                cur_desc = (self.entry_desc.get() or '').strip()
                phrases_for_check = [p.strip() for p in lines if p and p.strip()]
                if hasattr(config_manager, '_find_phrase_conflicts'):
                    # config_manager returns mapping of original_phrase -> owner_description
                    conflicts_from_mgr = config_manager._find_phrase_conflicts(cur_desc, phrases_for_check, exclude_description=cur_desc) or {}
            except Exception:
                conflicts_from_mgr = {}

            # Normalize conflicts keys to lowercase for quick lookup
            conflicts_lower = {k.strip().lower(): v for k, v in (conflicts_from_mgr or {}).items()}

            # build map of conflicts: line_index -> (phrase, owner_description)
            conflicts_map = {}
            for idx, raw in enumerate(lines, start=1):
                val = raw.strip()
                if not val:
                    continue
                owner = conflicts_lower.get(val.lower())
                if owner:
                    # ensure we don't flag phrases that belong to the command being edited
                    if owner and owner != (self.entry_desc.get() or '').strip():
                        conflicts_map[idx] = (val, owner)

            # Apply tags
            for i in duplicates:
                try:
                    start = f"{i}.0"
                    end = f"{i}.end"
                    self.txt_phrases.tag_add('duplicate', start, end)
                except Exception:
                    pass
            for i in conflicts_map.keys():
                try:
                    start = f"{i}.0"
                    end = f"{i}.end"
                    self.txt_phrases.tag_add('conflict', start, end)
                except Exception:
                    pass

            # If any problem, show a concise warning
            if duplicates or conflicts_map:
                msgs = []
                if duplicates:
                    # collect duplicate phrase texts for clarity
                    dup_texts = []
                    for i in sorted(duplicates):
                        try:
                            line = self.txt_phrases.get(f"{i}.0", f"{i}.end").strip()
                        except Exception:
                            line = ''
                        if line:
                            dup_texts.append(f"'{line}'")
                    if dup_texts:
                        msgs.append(f"Duplicate in editor: {', '.join(dup_texts)}")
                    else:
                        msgs.append(f"{len(duplicates)} duplicate line(s) in editor")
                if conflicts_map:
                    # Prefer showing the same human-friendly message produced by
                    # ConfigManager. This makes the UI and the backend consistent.
                    try:
                        # If config_manager has the last error message, use it
                        msg = ''
                        if hasattr(config_manager, 'get_last_error_message'):
                            msg = config_manager.get_last_error_message() or ''

                        if not msg:
                            # Fallback: construct the message similar to
                            # ConfigManager.add_command
                            conflict_msgs = []
                            for _, (ph, owner) in conflicts_map.items():
                                conflict_msgs.append(f"{ph} -> {owner}")
                            if conflict_msgs:
                                msg = (
                                    "Duplicate phrase(s) detected: \n" + "\n".join(conflict_msgs) +
                                    ". \nRemove the old command(s) or Update the phrases to resolve the conflict."
                                )

                        try:
                            messagebox.showwarning('Phrases validation', msg, parent=self.win)
                        except Exception:
                            pass
                    except Exception:
                        # Best-effort: if anything fails, show a minimal warning
                        try:
                            messagebox.showwarning('Phrases validation', 'Conflicting phrases detected', parent=self.win)
                        except Exception:
                            pass
                else:
                    try:
                        messagebox.showwarning('Phrases validation', '\n'.join(msgs), parent=self.win)
                    except Exception:
                        pass

        except Exception:
            logger.exception('Error validating phrases')
        # allow default behavior (insertion of newline)
        return None

    def _save_command(self):
        desc, data = self._get_command_editor_data()

        # Prevent editing/saving internal commands (read-only)
        existing = self.commands.get(desc)
        if existing and self._is_internal_command(existing):
            try:
                messagebox.showinfo('Read-only', 'Internal commands cannot be modified.', parent=self.win)
            except Exception:
                pass
            return

        # Validation: ensure all required fields are present
        missing = []
        # Description
        if not desc:
            missing.append('Description')
        # Action
        action = data.get('Action') or ''
        if action not in ('browser', 'command', 'keys'):
            missing.append('Action (must be browser, command or keys)')
        # Command / URL / Keys
        cmd_field = data.get('Command', '') or ''
        if not cmd_field.strip():
            missing.append('Command / URL / Keys')
        # Phrases
        phrases = data.get('Phrases') or []
        if not phrases:
            missing.append('At least one Phrase')

        if missing:
            msg = 'Missing required field(s): ' + ', '.join(missing)
            try:
                messagebox.showwarning('Validation', msg, parent=self.win)
            except Exception:
                pass

            # set focus to the first missing field for convenience
            try:
                if 'Description' in missing:
                    self.entry_desc.focus_set()
                elif 'Command / URL / Keys' in missing:
                    self.txt_command.focus_set()
                elif 'At least one Phrase' in missing:
                    self.txt_phrases.focus_set()
                else:
                    self.entry_desc.focus_set()
            except Exception:
                pass

            return
        try:
            # If description already exists in our commands, treat this as an update
            # and avoid surfacing phrase-conflict errors from config_manager.
            is_update = desc in (self.commands or {})

            if hasattr(config_manager, 'add_command'):
                if is_update:
                    # Preferred API: some implementations support an update path.
                    # Try to remove existing then add new (save deferred), falling
                    # back to direct manipulation if remove_command isn't available.
                    try:
                        # If config_manager provides an update or set API, prefer that
                        if hasattr(config_manager, 'update_command'):
                            ok = config_manager.update_command(desc, data, save=False)
                        else:
                            # Best-effort: remove existing then add new without validation
                            removed = False
                            try:
                                if hasattr(config_manager, 'remove_command'):
                                    try:
                                        config_manager.remove_command(desc, save=False)
                                        removed = True
                                    except TypeError:
                                        # some implementations may not accept save kwarg
                                        try:
                                            config_manager.remove_command(desc)
                                            removed = True
                                        except Exception:
                                            removed = False
                            except Exception:
                                removed = False

                            # If remove succeeded or wasn't possible, try add_command but
                            # skip phrase conflict checks by using a lower-level API if available.
                            try:
                                ok = config_manager.add_command(desc, data, save=False)
                            except Exception:
                                # As a last resort, update command_manager directly
                                command_manager.commands[desc] = data
                                ok = True

                        if not ok:
                            # Surface human-friendly message from config_manager
                            msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                            if not msg:
                                msg = 'Failed to add/update command (unknown error)'
                            try:
                                messagebox.showwarning('Save Failed', msg, parent=self.win)
                            except Exception:
                                pass
                            return
                    except Exception:
                        # Fallback to direct update if anything above fails
                        try:
                            command_manager.commands[desc] = data
                            ok = True
                        except Exception:
                            ok = False
                        if not ok:
                            try:
                                messagebox.showwarning('Save Failed', 'Failed to update command', parent=self.win)
                            except Exception:
                                pass
                            return
                else:
                    # New command: use config_manager.add_command which performs validation
                    added = config_manager.add_command(desc, data, save=False)
                    if not added:
                        # Surface human-friendly message from config_manager
                        msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                        if not msg:
                            msg = 'Failed to add command (unknown error)'
                        try:
                            messagebox.showwarning('Save Failed', msg, parent=self.win)
                        except Exception:
                            pass
                        return

                saved = True
                if hasattr(config_manager, 'save_commands'):
                    saved = config_manager.save_commands()
                    if not saved:
                        msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                        if not msg:
                            msg = 'Failed to save commands (unknown error)'
                        try:
                            messagebox.showwarning('Save Failed', msg, parent=self.win)
                        except Exception:
                            pass
                        return
            else:
                # fallback: try to save into command_manager and call save
                command_manager.commands[desc] = data
                if hasattr(config_manager, 'save_commands'):
                    saved = config_manager.save_commands()
                    if not saved:
                        msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                        if not msg:
                            msg = 'Failed to save commands (unknown error)'
                        try:
                            messagebox.showwarning('Save Failed', msg, parent=self.win)
                        except Exception:
                            pass
                        return

            self._load_commands()
            # Reload command manager so runtime picks up new commands
            try:
                if hasattr(command_manager, 'reload_commands'):
                    command_manager.reload_commands()
                elif hasattr(command_manager, 'load_commands'):
                    command_manager.load_commands()
            except Exception:
                logger.exception('Error reloading commands after save')

            try:
                messagebox.showinfo('Saved', 'Command saved', parent=self.win)
            except Exception:
                pass
        except Exception as e:
            logger.exception(f"Error saving command: {e}")
            try:
                messagebox.showerror('Error', f'Failed to save command: {e}', parent=self.win)
            except Exception:
                pass

    def _test_command(self):
        # Use existing command_manager test path if available
        desc, data = self._get_command_editor_data()
        if not data.get('Command'):
            messagebox.showerror('Error', 'Command/URL/Keys is required for testing', parent=self.win)
            return
        def run_test():
            try:
                if hasattr(command_manager, 'test_execute_direct'):
                    _success, msg = command_manager.test_execute_direct(data['Action'], data['Command'], '')
                    self.win.after(0, lambda: messagebox.showinfo('Test Result', msg, parent=self.win))
                else:
                    # best-effort: execute via execute_command
                    ok = command_manager.execute_command(desc or '_temp_', data.get('Command', ''))
                    self.win.after(0, lambda: messagebox.showinfo('Test Result', 'Success' if ok else 'Failed', parent=self.win))
            except Exception as e:
                logger.exception(f"Error testing command: {e}")
                self.win.after(0, lambda: messagebox.showerror('Test Error', str(e), parent=self.win))
        threading.Thread(target=run_test, daemon=True).start()

    def _import_commands(self):
        fp = filedialog.askopenfilename(title='Import Commands', filetypes=[('JSON','*.json'), ('All','*.*')], parent=self.win)
        if not fp:
            return
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            failed = []
            for k, v in data.items():
                if hasattr(config_manager, 'add_command'):
                    ok = config_manager.add_command(k, v, save=False)
                    if not ok:
                        msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                        failed.append((k, msg or 'Failed to add command'))
                else:
                    command_manager.commands[k] = v

            if hasattr(config_manager, 'save_commands'):
                saved = config_manager.save_commands()
                if not saved:
                    msg = getattr(config_manager, 'get_last_error_message', lambda: '')()
                    try:
                        messagebox.showwarning('Import - Save Failed', msg or 'Failed to save imported commands', parent=self.win)
                    except Exception:
                        pass
                    return

            self._load_commands()
            if failed:
                lines = [f"{name}: {err}" for name, err in failed]
                try:
                    messagebox.showwarning('Imported with Errors', '\n'.join(lines), parent=self.win)
                except Exception:
                    pass
            else:
                messagebox.showinfo('Imported', 'Commands imported', parent=self.win)
        except Exception as e:
            logger.exception(f"Error importing commands: {e}")
            messagebox.showerror('Error', str(e), parent=self.win)

    def _export_commands(self):
        fp = filedialog.asksaveasfilename(title='Export Commands', defaultextension='.json', filetypes=[('JSON','*.json')], parent=self.win)
        if not fp:
            return
        try:
            to_save = {k: v for k, v in (self.commands or {}).items()}
            with open(fp, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, indent=2)
            messagebox.showinfo('Exported', 'Commands exported', parent=self.win)
        except Exception as e:
            logger.exception(f"Error exporting commands: {e}")
            messagebox.showerror('Error', str(e), parent=self.win)

    def _on_close(self):
        try:
            # Clean up global bindings so they don't persist after window is closed
            try:
                self.win.unbind_all('<MouseWheel>')
                self.win.unbind_all('<Button-4>')
                self.win.unbind_all('<Button-5>')
            except Exception:
                pass

            if callable(self.on_close_callback):
                try:
                    self.on_close_callback()
                except Exception:
                    logger.exception('Error in on_close_callback')
            self.win.destroy()
        except Exception:
            pass


def open_modern_settings_form(parent=None, on_close_callback=None):
    """Compatibility entry point used by FloatingIcon and other modules."""
    try:
        floating_icon_instance = None
        if parent and hasattr(parent, 'quit_app'):
            floating_icon_instance = parent
            parent = None
        form = SingleSettingsCommandsForm(parent, floating_icon_instance, on_close_callback)
        # Run as modal-ish (disable parent actions already handled by caller)
        form.win.transient(None)
        form.win.grab_set()
        form.win.wait_window()
    except Exception as e:
        logger.exception(f"Failed to open settings form: {e}")
        messagebox.showerror('Error', f'Failed to open settings form: {e}')


def open_settings_form(parent=None):
    open_modern_settings_form(parent)


if __name__ == "__main__":     # only create console in debug/logging mode
    open_settings_form()