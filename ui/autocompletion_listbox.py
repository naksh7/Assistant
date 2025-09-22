import threading
import tkinter as tk
from tkinter import Toplevel, Listbox
from core.app_logger import logger
from core.command_manager import command_manager


class AutocompletionListbox:
    """Encapsulates the floating phrase textbox and autocomplete listbox.

    It expects an owner with methods: start_processing_animation, stop_processing_animation,
    start_shake_animation, and attributes root. The class will set owner.phrase_window,
    owner.phrase_textbox, owner.phrase_listbox while active for compatibility.
    """

    def __init__(self, owner):
        self.owner = owner
        self.root = owner.root
        self.phrase_window = None
        self.phrase_textbox = None
        self.phrase_listbox = None
        self.listbox_window = None
        self.available_phrases = []
        self.filtered_phrases = []

    def show(self, _event):
        try:
            # Don't show if already open or if actions are disabled
            if self.phrase_window or not getattr(self.owner, 'actions_enabled', True):
                return

            self._load_available_phrases()

            # Create floating window
            self.phrase_window = Toplevel(self.root)
            self.phrase_window.title("")
            self.phrase_window.overrideredirect(True)
            self.phrase_window.attributes('-topmost', True)
            self.phrase_window.configure(bg='#2b2b2b')

            # Position near the floating icon
            # Make sure geometry information is up-to-date (handles runtime icon size changes)
            try:
                self.root.update_idletasks()
            except Exception:
                pass

            icon_x = self.root.winfo_x()
            icon_y = self.root.winfo_y()
            # Prefer the actual icon_label size if available (more accurate when icon size changes)
            try:
                icon_width = self.owner.icon_label.winfo_width()
                icon_height = self.owner.icon_label.winfo_height()
            except Exception:
                icon_width = self.root.winfo_width()
                icon_height = self.root.winfo_height()

            screen_width = self.root.winfo_screenwidth()
            textbox_width = 250
            textbox_height = 35

            if icon_x + icon_width + textbox_width + 10 < screen_width:
                pos_x = icon_x + icon_width + 10
            else:
                pos_x = max(10, icon_x - textbox_width - 10)

            # Align textbox vertically to the icon (centered) when possible
            try:
                pos_y = icon_y + max(0, (icon_height - textbox_height) // 2)
            except Exception:
                pos_y = icon_y
            self.phrase_window.geometry(f"{textbox_width}x{textbox_height}+{pos_x}+{pos_y}")

            frame = tk.Frame(self.phrase_window, bg='#2b2b2b', highlightthickness=1,
                             highlightcolor='#4a9eff', highlightbackground='#404040')
            frame.pack(fill='both', expand=True, padx=2, pady=2)

            self.phrase_textbox = tk.Entry(frame,
                                           font=('Segoe UI', 11),
                                           bg='#3b3b3b',
                                           fg='white',
                                           insertbackground='white',
                                           relief='flat',
                                           bd=0,
                                           highlightthickness=0)
            self.phrase_textbox.pack(fill='both', expand=True, padx=5, pady=5)

            self.phrase_textbox.insert(0, "Type a phrase...")
            self.phrase_textbox.configure(fg='#888888')

            # Bind events
            self.phrase_textbox.bind('<KeyRelease>', self._on_textbox_key_release)
            self.phrase_textbox.bind('<Return>', self._on_textbox_enter)
            self.phrase_textbox.bind('<Escape>', self._close_phrase_textbox)
            self.phrase_textbox.bind('<FocusIn>', self._on_textbox_focus_in)
            self.phrase_textbox.bind('<FocusOut>', self._on_textbox_focus_out)
            self.phrase_textbox.bind('<Up>', self._on_listbox_navigate_up)
            self.phrase_textbox.bind('<Down>', self._on_listbox_navigate_down)

            self.phrase_window.bind('<FocusOut>', self._on_window_focus_out)

            self.phrase_textbox.focus_set()

            # expose attributes on owner for backward compatibility
            try:
                self.owner.phrase_window = self.phrase_window
                self.owner.phrase_textbox = self.phrase_textbox
                self.owner.phrase_listbox = self.phrase_listbox
            except Exception:
                pass

            logger.info("Phrase textbox opened (autocompletion)")

        except Exception as e:
            logger.exception(f"Error showing phrase textbox: {e}")
            self._close_phrase_textbox()

    def _load_available_phrases(self):
        try:
            phrases_info = command_manager.get_all_phrases_with_descriptions()
            self.available_phrases = [info['phrase'] for info in phrases_info]
            self.filtered_phrases = self.available_phrases.copy()
            logger.info(f"Loaded {len(self.available_phrases)} phrases for autocomplete")
        except Exception as e:
            logger.exception(f"Error loading phrases: {e}")
            self.available_phrases = []
            self.filtered_phrases = []

    def _on_textbox_focus_in(self, _event):
        if self.phrase_textbox.get() == "Type a phrase..." and self.phrase_textbox.cget('fg') == '#888888':
            self.phrase_textbox.delete(0, tk.END)
            self.phrase_textbox.configure(fg='white')

    def _on_textbox_focus_out(self, _event):
        if not self.phrase_textbox.get().strip():
            self.phrase_textbox.delete(0, tk.END)
            self.phrase_textbox.insert(0, "Type a phrase...")
            self.phrase_textbox.configure(fg='#888888')

    def _on_window_focus_out(self, _event):
        self.root.after(100, self._check_and_close_textbox)

    def _check_and_close_textbox(self):
        try:
            if self.phrase_window:
                focused = self.root.focus_get()
                if (focused != self.phrase_textbox and
                        (not self.phrase_listbox or focused != self.phrase_listbox) and
                        focused != self.phrase_window):
                    self._close_phrase_textbox()
        except Exception:
            pass

    def _on_textbox_key_release(self, _event):
        try:
            if _event.keysym in ['Up', 'Down', 'Return', 'Escape']:
                return

            current_text = self.phrase_textbox.get().strip()

            if current_text == "Type a phrase..." or not current_text:
                self.filtered_phrases = self.available_phrases.copy()
            else:
                current_lower = current_text.lower()
                self.filtered_phrases = [phrase for phrase in self.available_phrases if current_lower in phrase.lower()]

            if self.filtered_phrases and current_text and current_text != "Type a phrase...":
                self._show_autocomplete_listbox()
            else:
                self._hide_autocomplete_listbox()

        except Exception as e:
            logger.exception(f"Error in textbox key release: {e}")

    def _show_autocomplete_listbox(self):
        try:
            if not self.phrase_window:
                return

            # Ensure geometry values are fresh (handles rapid resize/size changes)
            try:
                self.phrase_window.update_idletasks()
            except Exception:
                pass

            # Compute textbox/listbox positions regardless of whether the listbox exists yet
            textbox_x = self.phrase_window.winfo_x()
            textbox_y = self.phrase_window.winfo_y()
            textbox_height = self.phrase_window.winfo_height()
            pos_x = textbox_x
            listbox_width = 250

            # Determine screen geometry to decide whether to place listbox below or above
            try:
                screen_height = self.root.winfo_screenheight()
                # Approximate row height and padding used below when sizing listbox
                row_height = 20
                padding = 12
            except Exception:
                screen_height = 800
                row_height = 20
                padding = 12

            # Estimate desired listbox height for current filtered items (will be updated later)
            estimated_rows = min(10, max(1, len(self.filtered_phrases)))
            estimated_height = estimated_rows * row_height + padding

            # Space available below textbox and above textbox
            space_below = screen_height - (textbox_y + textbox_height)
            space_above = textbox_y

            # Prefer below unless not enough space; if below insufficient but above is, flip above
            if space_below >= estimated_height + 2:
                pos_y = textbox_y + textbox_height + 2
                place_above = False
            elif space_above >= estimated_height + 2:
                # place above textbox
                pos_y = max(0, textbox_y - estimated_height - 2)
                place_above = True
            else:
                # Neither side has enough space: choose the side with more space and clamp height later
                if space_below >= space_above:
                    pos_y = textbox_y + textbox_height + 2
                    place_above = False
                    estimated_height = max(40, space_below - 4)
                else:
                    pos_y = max(0, 2)
                    place_above = True
                    estimated_height = max(40, space_above - 4)

            if not self.phrase_listbox:
                self.listbox_window = Toplevel(self.phrase_window)
                self.listbox_window.title("")
                self.listbox_window.overrideredirect(True)
                self.listbox_window.attributes('-topmost', True)
                self.listbox_window.configure(bg='#2b2b2b')

                # initial geometry will be adjusted after we populate items
                # Use the estimated height so the window appears in the correct direction
                try:
                    self.listbox_window.geometry(f"{listbox_width}x{int(estimated_height)}+{pos_x}+{pos_y}")
                except Exception:
                    self.listbox_window.geometry(f"{listbox_width}x100+{pos_x}+{pos_y}")

                listbox_frame = tk.Frame(self.listbox_window, bg='#2b2b2b', highlightthickness=1,
                                         highlightcolor='#4a9eff', highlightbackground='#404040')
                listbox_frame.pack(fill='both', expand=True, padx=2, pady=2)

                self.phrase_listbox = Listbox(listbox_frame,
                                              font=('Segoe UI', 10),
                                              bg='#3b3b3b',
                                              fg='white',
                                              selectbackground='#4a9eff',
                                              selectforeground='white',
                                              relief='flat',
                                              bd=0,
                                              highlightthickness=0,
                                              activestyle='none')
                self.phrase_listbox.pack(fill='both', expand=True, padx=2, pady=2)

                self.phrase_listbox.bind('<Double-Button-1>', self._on_listbox_double_click)
                self.phrase_listbox.bind('<Return>', self._on_listbox_enter)
                self.phrase_listbox.bind('<Button-1>', self._on_listbox_click)

            # Populate listbox with up to 10 items and resize window to fit rows
            self.phrase_listbox.delete(0, tk.END)
            for phrase in self.filtered_phrases[:10]:
                self.phrase_listbox.insert(tk.END, phrase)

            visible_count = min(10, max(1, self.phrase_listbox.size()))
            try:
                # set number of rows shown by the Listbox
                self.phrase_listbox.configure(height=visible_count)
            except Exception:
                pass

            # Approximate row height in pixels (depends on font). Add small padding.
            row_height = 20
            padding = 12
            new_height = visible_count * row_height + padding

            # If we flipped above, adjust pos_y so the bottom of listbox sits just above textbox
            if place_above:
                pos_y = max(0, textbox_y - new_height - 2)

            # Ensure the listbox doesn't go off the bottom/right of the screen
            try:
                screen_width = self.root.winfo_screenwidth()
                # clamp x
                if pos_x + listbox_width > screen_width - 4:
                    pos_x = max(2, screen_width - listbox_width - 4)
                # clamp y
                if pos_y + new_height > screen_height - 2:
                    new_height = max(40, screen_height - pos_y - 4)

                # Update geometry so items are visible and placement is correct
                self.listbox_window.geometry(f"{listbox_width}x{new_height}+{pos_x}+{pos_y}")
            except Exception:
                try:
                    self.listbox_window.geometry(f"{listbox_width}x{new_height}+{pos_x}+{pos_y}")
                except Exception:
                    pass

            if self.phrase_listbox.size() > 0:
                self.phrase_listbox.selection_set(0)
                self.phrase_listbox.activate(0)

        except Exception as e:
            logger.exception(f"Error showing autocomplete listbox: {e}")

    def _hide_autocomplete_listbox(self):
        try:
            if hasattr(self, 'listbox_window') and self.listbox_window:
                self.listbox_window.destroy()
                self.listbox_window = None
            self.phrase_listbox = None
        except Exception as e:
            logger.exception(f"Error hiding autocomplete listbox: {e}")

    def _on_listbox_navigate_up(self, _event):
        if self.phrase_listbox and self.phrase_listbox.size() > 0:
            current_selection = self.phrase_listbox.curselection()
            if current_selection:
                new_index = max(0, current_selection[0] - 1)
            else:
                new_index = self.phrase_listbox.size() - 1

            self.phrase_listbox.selection_clear(0, tk.END)
            self.phrase_listbox.selection_set(new_index)
            self.phrase_listbox.activate(new_index)
            self.phrase_listbox.see(new_index)
        return 'break'

    def _on_listbox_navigate_down(self, _event):
        if self.phrase_listbox and self.phrase_listbox.size() > 0:
            current_selection = self.phrase_listbox.curselection()
            if current_selection:
                new_index = min(self.phrase_listbox.size() - 1, current_selection[0] + 1)
            else:
                new_index = 0

            self.phrase_listbox.selection_clear(0, tk.END)
            self.phrase_listbox.selection_set(new_index)
            self.phrase_listbox.activate(new_index)
            self.phrase_listbox.see(new_index)
        return 'break'

    def _on_listbox_click(self, _event):
        if self.phrase_textbox:
            self.phrase_textbox.focus_set()

    def _on_listbox_double_click(self, _event):
        self._select_phrase_from_listbox()

    def _on_listbox_enter(self, _event):
        self._select_phrase_from_listbox()

    def _select_phrase_from_listbox(self):
        try:
            if self.phrase_listbox:
                selection = self.phrase_listbox.curselection()
                if selection:
                    selected_phrase = self.phrase_listbox.get(selection[0])
                    self.phrase_textbox.delete(0, tk.END)
                    self.phrase_textbox.insert(0, selected_phrase)
                    self.phrase_textbox.configure(fg='white')
                    self._execute_phrase()
        except Exception as e:
            logger.exception(f"Error selecting phrase from listbox: {e}")

    def _on_textbox_enter(self, _event):
        try:
            if (self.phrase_listbox and self.phrase_listbox.size() > 0 and self.phrase_listbox.curselection()):
                self._select_phrase_from_listbox()
            else:
                self._execute_phrase()
        except Exception as e:
            logger.exception(f"Error in textbox enter: {e}")

    def _execute_phrase(self):
        try:
            phrase = self.phrase_textbox.get().strip()
            if not phrase or phrase == "Type a phrase...":
                self._close_phrase_textbox()
                return

            logger.info(f"Executing phrase from textbox: {phrase}")
            self._close_phrase_textbox()

            # Start processing animation on owner
            try:
                self.owner.start_processing_animation()
            except Exception:
                pass

            threading.Thread(target=self._execute_phrase_async, args=(phrase,), daemon=True).start()

        except Exception as e:
            logger.exception(f"Error executing phrase: {e}")
            self._close_phrase_textbox()

    def _execute_phrase_async(self, phrase):
        try:
            _success = command_manager.handle_voice_command(phrase)
            if _success:
                logger.info("Phrase executed successfully")
                try:
                    self.owner.stop_processing_animation()
                except Exception:
                    pass
            else:
                try:
                    self.owner.stop_processing_animation(on_complete_callback=self.owner.start_shake_animation)
                except Exception:
                    pass
                logger.info("Phrase execution failed")

        except Exception as e:
            logger.exception(f"Error in async phrase execution: {e}")
            try:
                self.owner.stop_processing_animation(on_complete_callback=self.owner.start_shake_animation)
            except Exception:
                pass

    def _close_phrase_textbox(self, _event=None):
        try:
            self._hide_autocomplete_listbox()

            if self.phrase_window:
                self.phrase_window.destroy()
                self.phrase_window = None

            self.phrase_textbox = None

            # clear owner references (do not delete owner._autocomplete so it persists)
            try:
                self.owner.phrase_window = None
                self.owner.phrase_textbox = None
                self.owner.phrase_listbox = None
            except Exception:
                pass

            logger.info("Phrase textbox closed (autocompletion)")

        except Exception as e:
            logger.exception(f"Error closing phrase textbox: {e}")
            self.phrase_window = None
            self.phrase_textbox = None
            self.phrase_listbox = None
