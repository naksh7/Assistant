"""Phrases reference dialog implemented with tkinter.ttk.

This provides a simple, dependency-light dialog that lists available
voice phrases grouped by command description. It mirrors the features
of the previous CTk dialog but uses standard ttk widgets.
"""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from core.app_logger import logger
from core.command_manager import command_manager

def set_taskbar_icon(win, parent=None):
    """Best-effort set an icon on a tkinter window and (on Windows) the AppUserModelID

    This helper mirrors the behavior used elsewhere in the app. It does not raise
    on error so it is safe to call on any platform.
    """
    try:
        icon_path = Path(__file__).resolve().parents[1] / 'resources' / 'icon.ico'
    except Exception:
        return

    try:
        if icon_path.exists():
            # Prefer iconbitmap on Windows for .ico files
            try:
                win.iconbitmap(str(icon_path))
            except Exception:
                # Fallback to iconphoto (supports more formats)
                try:
                    img = tk.PhotoImage(file=str(icon_path))
                    # keep reference to avoid GC
                    win._icon_img = img
                    try:
                        win.iconphoto(False, img)
                    except Exception:
                        pass
                except Exception:
                    pass

            # Also attempt to set parent's icon so the taskbar groups correctly
            try:
                if parent is not None:
                    try:
                        parent.iconbitmap(str(icon_path))
                    except Exception:
                        try:
                            img2 = tk.PhotoImage(file=str(icon_path))
                            parent._root_icon_img = img2
                            try:
                                parent.iconphoto(False, img2)
                            except Exception:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass

        # On Windows, set an explicit AppUserModelID so the taskbar groups and
        # displays the application's icon consistently.
        if sys.platform.startswith('win'):
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Akatsuki.Assistant')
            except Exception:
                pass
    except Exception:
        # Swallow all icon-related errors
        return


def show_available_phrases(parent=None) -> None:
    """Show a compact, centered, dark-themed popup listing description -> phrases.

    This mirrors the visual style of the autocompletion listbox: dark background,
    topmost, compact, and centered on the primary screen. Only the description and
    corresponding phrases are shown (phrases are quoted and comma-separated).
    """
    try:
        # Load phrases grouped by description
        phrases = command_manager.get_all_phrases_with_descriptions() or []
        commands = {}
        for p in phrases:
            desc = p.get('description', '') or 'Misc'
            commands.setdefault(desc, []).append(p.get('phrase', ''))

        sorted_cmds = sorted(commands.items(), key=lambda x: x[0].lower())

        # Create popup
        root = parent if parent is not None else None
        popup = tk.Toplevel(root)
        popup.title('Available Phrases')
        # Apply per-popup scaling based on reported DPI so the dialog scales on HiDPI
        try:
            popup.update_idletasks()
            dpi = float(popup.winfo_fpixels('1i'))
            if dpi and dpi > 0:
                scale = dpi / 96.0
                if abs(scale - 1.0) > 0.01:
                    try:
                        popup.tk.call('tk', 'scaling', scale)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            # Ensure the popup has the application icon and a consistent AppUserModelID
            set_taskbar_icon(popup, parent=root)
        except Exception:
            pass
        popup.attributes('-topmost', True)
        popup.configure(bg="#f0f0f0")

        # Build content frame
        frame = tk.Frame(popup, bg="#f0f0f0", bd=0)
        frame.pack(fill='both', expand=True, padx=8, pady=8)

        # Table (Treeview) with two columns: Description | Phrases
        container = tk.Frame(frame, bg="#f0f0f0")
        container.pack(fill='both', expand=True, padx=6, pady=(0,6))

        # Compute popup size and center
        popup.update_idletasks()
        popup_width = 800        
        popup_height = 280
        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        x = (screen_w - popup_width) // 2
        y = (screen_h - popup_height) // 2
        

        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        

        # Treeview and vertical scrollbar (no horizontal scrollbar)
        style = ttk.Style()
        try:
            # Light style for the popup tree: ensure item text is black and increase
            # row height so phrase lines have more vertical space for readability.
            # We keep the same font but bump the rowheight for a taller appearance.
            style.configure(
                'Light.Treeview',
                background='#f0f0f0',
                foreground='black',
                fieldbackground='#f0f0f0',
                font=('Segoe UI', 11),
                rowheight=26,
            )
            style.configure('Light.Treeview.Heading', background='#ffffff', foreground="#020202", font=('Segoe UI', 12, 'bold'))
            # Keep selected foreground black as requested
            style.map('Light.Treeview', background=[('selected', '#c8d6ff')], foreground=[('selected', 'black')])
        except Exception:
            pass

        columns = ('description', 'phrases')
        tree = ttk.Treeview(container, columns=columns, show='headings', style='Light.Treeview')
        tree.heading('description', text='Description')
        tree.heading('phrases', text='Phrases')
        # column widths
        tree.column('description', width=int(popup_width * 0.25), anchor='w')
        tree.column('phrases', width=int(popup_width * 0.7), anchor='w')

        tree.grid(row=0, column=0, sticky='nsew')        
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Populate table rows: phrases without quotes, comma-separated
        for i, (desc, phs) in enumerate(sorted_cmds):
            phrases_text = " | ".join(ph for ph in phs if ph)
            tag = 'even' if (i % 2 == 0) else 'odd'
            tree.insert('', 'end', values=(desc, phrases_text), tags=(tag,))

        # Style alternating row colors (dark, matching autocompletion)
        try:
            tree.tag_configure('even', background="#f0f0f0")
            tree.tag_configure('odd', background="#e2e2e2")
        except Exception:
            pass
        
        # Focus / close handlers
        def _close(_event=None):
            try:
                popup.destroy()
            except Exception:
                pass

        popup.bind('<Escape>', _close)

        def _on_focus_out(_event=None):
            popup.after(120, lambda: (not popup.focus_get()) and _close())

        popup.bind('<FocusOut>', _on_focus_out)

        try:
            popup.focus_force()
        except Exception:
            pass

        try:
            popup.grab_set()
        except Exception:
            pass

        try:
            popup.wait_window()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Error showing centered dark popup: {e}")


