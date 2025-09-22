import tkinter as tk
from tkinter import Menu, Listbox, Toplevel
import threading
import time
import os
import functools
from core.app_logger import logger
from core.app_speech import speech_recognizer
from core.command_manager import command_manager
from core.config_manager import config_manager
from core.utils import PathUtils
from .modern_form import open_modern_settings_form


from .autocompletion_listbox import AutocompletionListbox

floating_icon_instance = None  # Global reference to the active FloatingIcon


class FloatingIcon:
    def __init__(self):
        logger.info("Initializing FloatingIcon...")
        self.root = tk.Tk()
        self.root.title("Assistant")

        # Load configuration from settings
        logger.info("Loading floating icon configuration...")
        self.load_config()

        # Set window properties
        if self.config_always_on_top:
            self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)

        # Make window transparent
        if self.window_transparency:
            self.root.wm_attributes('-transparentcolor', 'black')
            self.root.wm_attributes('-alpha', self.opacity)
        self.root.configure(bg='black')

        # Animation states
        self.is_listening = False
        self.is_processing = False
        self.is_shaking = False
        self.listening_thread = None
        self.processing_thread = None
        self.shake_thread = None
        self.rotation_angle = 0
        self.last_stop_angle = 0
        self.glow_intensity = 0
        self.original_position = None
        self._on_processing_complete_callback = None

        # Settings window state
        self.settings_window_open = False
        self.actions_enabled = True

        # Phrase textbox state
        self.phrase_textbox = None
        self.phrase_listbox = None
        self.phrase_window = None
        self.available_phrases = []
        self.filtered_phrases = []
        # Autocompletion helper
        self._autocomplete = AutocompletionListbox(self)

        # Animation parameters (loaded from config)
        self.rotation_speed = 0
        self.total_rotation = 0  # Total degrees rotated in current session
        
        # Icon properties for animation
        self.original_image = None
        self.photo = None

        # Window dragging
        self.drag_data = {
            "x": 0,
            "y": 0,
            "dragging": False,
            "start_time": 0,
            "start_x": 0,
            "start_y": 0,
        }

        # UI widget placeholders (initialized here to satisfy linters and for safer access)
        self.main_frame = None
        self.icon_label = None
        self.context_menu = None
        # Autocomplete/window placeholders
        self.listbox_window = None
        self._root_icon_img = None

        # Load custom icon or default
        self.load_icon()

        # Create UI and bindings
        self.setup_ui()
        self.setup_bindings()

        # Position window
        self.center_window()

        logger.info("Enhanced floating icon initialized")
    
    def load_config(self):
        """Load configuration parameters from settings.json."""
      
        # Get floating icon configuration using the new config manager
        floating_icon_config = config_manager.get_settings_section('Floating_Icon')
            
        # Icon and window settings
        # Size of the displayed icon in pixels (int). Typical values: 48-128.
        self.icon_size = floating_icon_config.get('Icon_Size', 70)
        # If True, window stays above other windows. Useful for quick access.
        self.config_always_on_top = floating_icon_config.get('Always_On_Top', True)
        # If True, the window uses a transparent background and alpha blending.
        # Set to False to have an opaque window (no transparentcolor or alpha).
        self.window_transparency = floating_icon_config.get('Window_Transparency', True)
        # Opacity / alpha for the window when transparency is enabled.
        # Range: 0.0 (fully transparent/invisible) to 1.0 (fully opaque).
        # Example: 0.1 will be very faint/mostly transparent, 0.9 is nearly solid.
        self.opacity = floating_icon_config.get('Opacity', 0.9)        
        # Path to a custom icon image. Can be a PNG/JPG/ICO with transparency.
        # If empty or invalid, bundled resource 'icon.png' will be used as fallback.
        self.icon_path = floating_icon_config.get('Icon_Path', 'resources/icon.png') 
        # Animation frames per second for glow/rotation/pulse loops. Typical: 30-120.
        self.animation_fps = floating_icon_config.get('Animation_FPS', 66)
            
        # Position settings - Offset_X and Offset_Y store the last dragged position
        # These values are automatically updated when the user drags the icon
        # Negative values = distance from bottom-right corner
        # Positive values = absolute coordinates from top-left corner
        position_config = floating_icon_config.get('Position', {})
        self.config_offset_x = position_config.get('Offset_X', -150)
        self.config_offset_y = position_config.get('Offset_Y', -150)
            
        # Drag and click settings
        drag_click_config = floating_icon_config.get('Drag_And_Click', {})
        # Minimum movement in pixels to be considered a drag (vs click). Typical: 2-12.
        self.drag_threshold = drag_click_config.get('Drag_Threshold', 5)
        # Time threshold (ms) within which a quick press is treated as a click.
        # Example: 200 ms = typical click speed; increase for slower users.
        self.click_timeout = drag_click_config.get('Click_Timeout', 200)
            
        # Rotation animation settings
        rotation_config = floating_icon_config.get('Rotation_Animation', {})
        # Max rotation speed in degrees per frame or arbitrary unit used by loop.
        # Larger values = faster spinning. Typical: 5-60 (experiment for smoothness).
        self.max_rotation_speed = rotation_config.get('Max_Rotation_Speed', 15)
        # How quickly rotation_speed increases while processing (per frame step).
        # Larger values accelerate faster. Typical: 0.1 - 2.0.
        self.rotation_acceleration = rotation_config.get('Rotation_Acceleration', 0.5)
        # How quickly rotation_speed decreases when stopping. Larger = snappier stop.
        self.rotation_deceleration = rotation_config.get('Rotation_Deceleration', 0.8)
        # Minimum full rotation cycles to complete before stopping (1 => 360° min).
        self.min_rotation_cycles = rotation_config.get('Min_Rotation_Cycles', 1)
            
        # Glow effect settings
        glow_config = floating_icon_config.get('Glow_Effect', {})
        # Brightness multiplier portion used when pulsing. Typical 0.0-1.0.
        # Example: 0.3 => pulse increases brightness by up to ~30%.
        self.brightness_intensity = glow_config.get('Brightness_Intensity', 2.0)
        # Contrast adjustment intensity during pulse. Typical 0.0-0.5.
        self.contrast_intensity = glow_config.get('Contrast_Intensity', 0.1)
        # Color saturation intensity used by glow. Typical 0.0-0.2 for subtle effect.
        self.color_intensity = glow_config.get('Color_Intensity', 0.05)
                
        # Pulse animation settings
        pulse_config = floating_icon_config.get('Pulse_Animation', {})
        # Pulse (glow) speed controls how fast the sine wave oscillates.
        # Larger = faster pulsing. Typical: 1.0 - 10.0.
        self.pulse_speed = pulse_config.get('Pulse_Speed', 5.0)
        # Variation speed adds secondary motion to avoid robotic pulses.
        self.pulse_variation_speed = pulse_config.get('Pulse_Variation_Speed', 0.7)
        # Variation intensity scales the secondary oscillation (0.0 - 1.0).
        self.pulse_variation_intensity = pulse_config.get('Pulse_Variation_Intensity', 0.1)
            
        # Shake animation settings   
        shake_config = floating_icon_config.get('Shake_Animation', {})     
        # Use shake_config and correct mapping of keys (intensity, duration, frequency)
        # Shake intensity in pixels (max horizontal displacement). Typical: 2-20.
        self.shake_intensity = shake_config.get('Shake_Intensity', 5)
        # Total shake duration in seconds. Typical: 0.2 - 1.0.
        self.shake_duration = shake_config.get('Shake_Duration', 0.5)
        # Shake frequency (shakes per second). Typical: 8 - 40.
        self.shake_frequency = shake_config.get('Shake_Frequency', 25)
             
        logger.info("Floating icon configuration loaded successfully")
            
    def load_icon_from_path(self, icon_path):
        """Load icon from a specific path and update display immediately"""
        try:
            from PIL import Image
            
            if icon_path and os.path.exists(icon_path):
                img = Image.open(icon_path).convert('RGBA')
                # Paste onto fully transparent background to preserve alpha when resizing
                canvas = Image.new('RGBA', img.size, (0, 0, 0, 0))
                canvas.paste(img, (0, 0), img)
                # Resize using high-quality resampling
                self.original_image = canvas.resize((self.icon_size, self.icon_size), Image.Resampling.LANCZOS)
                self.update_icon_display()
                # Ensure window geometry reflects new icon size immediately
                try:
                    self.root.update_idletasks()
                    self.root.geometry(f"{self.icon_size}x{self.icon_size}+{self.root.winfo_x()}+{self.root.winfo_y()}")
                except Exception:
                    pass
                logger.info(f"Icon loaded from path: {icon_path}")
                return True
            else:
                logger.warning(f"Icon path not found: {icon_path}")
                return False
        except Exception as e:
            logger.exception(f"Error loading icon from path: {e}")
            return False
    
    def load_icon(self):
        """Load icon from settings."""
        try:
            from PIL import Image
            
            # Get the icon path using resource utility
            icon_name = os.path.basename(self.icon_path) if self.icon_path else 'icon.png'
            resource_path = PathUtils.get_resource_path(icon_name)
            
            if resource_path and resource_path.exists():
                img = Image.open(resource_path).convert('RGBA')
                canvas = Image.new('RGBA', img.size, (0, 0, 0, 0))
                canvas.paste(img, (0, 0), img)
                self.original_image = canvas
                logger.info(f"Loaded icon: {resource_path}")
            else:
                # Try fallback with configured path
                if self.icon_path and os.path.exists(self.icon_path):
                    img = Image.open(self.icon_path).convert('RGBA')
                    canvas = Image.new('RGBA', img.size, (0, 0, 0, 0))
                    canvas.paste(img, (0, 0), img)
                    self.original_image = canvas
                    logger.info(f"Loaded icon from configured path: {self.icon_path}")
                else:
                    # Try default fallback
                    fallback_path = PathUtils.get_resource_path('icon.png')
                    if fallback_path and fallback_path.exists():
                        self.original_image = Image.open(fallback_path)
                        logger.info(f"Loaded fallback icon: {fallback_path}")
                    else:
                        raise FileNotFoundError(f"No icon found. Tried: {icon_name}, {self.icon_path}")
                    
        except Exception as e:
            logger.error(f"Error loading icon: {e}")
            logger.info("Creating fallback colored rectangle as icon")
            # Create a simple colored rectangle as fallback
            from PIL import Image, ImageDraw
            self.original_image = Image.new('RGBA', (self.icon_size, self.icon_size), (70, 130, 180, 255))
            draw = ImageDraw.Draw(self.original_image)
            # Draw a simple circle
            margin = 10
            draw.ellipse([margin, margin, self.icon_size-margin, self.icon_size-margin], 
                        fill=(100, 149, 237, 255), outline=(255, 255, 255, 200), width=3)
                    
        # Resize to standard size (preserve alpha)
        if self.original_image:
            self.original_image = self.original_image.convert('RGBA')
            self.original_image = self.original_image.resize((self.icon_size, self.icon_size), Image.Resampling.LANCZOS)
            # Ensure UI reflects the changed icon size so other windows can position relative to it
            try:
                self.update_icon_display()
                self.root.update_idletasks()
                self.root.geometry(f"{self.icon_size}x{self.icon_size}+{self.root.winfo_x()}+{self.root.winfo_y()}")
            except Exception:
                pass
          
    def setup_ui(self):
        """Set up the user interface."""
        # Create main frame with transparent background
        self.main_frame = tk.Frame(self.root, bg='black', highlightthickness=0, bd=0)
        self.main_frame.pack(fill='both', expand=True)
        
        # Create label for icon with no background/border
        self.icon_label = tk.Label(
            self.main_frame, 
            bg='black', 
            bd=0, 
            highlightthickness=0,
            relief='flat'
        )
        self.icon_label.pack(pady=0, padx=0)
        
        # Update display
        self.update_icon_display()
        
        # Resize window to fit content exactly
        try:
            self.root.update_idletasks()
            # Preserve current position if already set; otherwise center using saved offsets
            try:
                cur_x = self.root.winfo_x()
                cur_y = self.root.winfo_y()
                self.root.geometry(f"{self.icon_size}x{self.icon_size}+{cur_x}+{cur_y}")
            except Exception:
                self.root.geometry(f"{self.icon_size}x{self.icon_size}")
        except Exception:
            pass
    
    def setup_bindings(self):
        """Set up event bindings."""
        # Enhanced drag and click handling
        def handle_button_press(_event):
            """Handle mouse button press - start potential drag or click."""
            try:
                self.drag_data["x"] = _event.x_root - self.root.winfo_x()
                self.drag_data["y"] = _event.y_root - self.root.winfo_y()
                self.drag_data["dragging"] = False
                self.drag_data["start_time"] = time.time() * 1000  # Convert to milliseconds
                self.drag_data["start_x"] = _event.x_root
                self.drag_data["start_y"] = _event.y_root
            except Exception:
                # Defensive: ignore event errors
                pass
            return 'break'

        def handle_button_motion(_event):
            """Handle mouse motion - determine if it's a drag."""
            try:
                # Calculate distance moved
                dx = abs(_event.x_root - self.drag_data["start_x"])
                dy = abs(_event.y_root - self.drag_data["start_y"])
                distance = (dx * dx + dy * dy) ** 0.5

                # If moved beyond threshold, it's a drag
                if distance > self.drag_threshold:
                    self.drag_data["dragging"] = True

                    # Perform drag
                    x = _event.x_root - self.drag_data["x"]
                    y = _event.y_root - self.drag_data["y"]
                    self.root.geometry(f"+{x}+{y}")
            except Exception:
                pass
            return 'break'

        def handle_button_release(_event):
            """Handle mouse button release - determine if it was click or drag."""
            try:
                current_time = time.time() * 1000
                time_elapsed = current_time - self.drag_data["start_time"]

                # Calculate distance moved
                dx = abs(_event.x_root - self.drag_data["start_x"])
                dy = abs(_event.y_root - self.drag_data["start_y"])
                distance = (dx * dx + dy * dy) ** 0.5

                # If it was a drag, save the new position
                if self.drag_data.get("dragging"):
                    self.save_window_position()

                # If it wasn't a drag and was quick enough, treat as click
                elif distance <= self.drag_threshold and time_elapsed <= self.click_timeout:
                    if not self.is_listening and not self.is_processing:
                        try:
                            logger.info(f"Click detected at {_event.x}, {_event.y}")
                        except Exception:
                            pass
                        self.on_click(_event)

                # Reset drag state
                self.drag_data["dragging"] = False
            except Exception:
                # Defensive: ignore errors during release handling
                pass
            return 'break'

        def handle_right_click(_event):
            """Handle right click - show textbox or context menu when Ctrl is pressed."""
            try:
                # Check if Ctrl key is pressed
                if _event.state & 0x4:  # Ctrl key mask
                    self.show_context_menu(_event)
                else:
                    # Show phrase input textbox
                    self.show_phrase_textbox(_event)
            except Exception:
                pass
            return 'break'

        # Bind events to the icon label (main clickable area)
        self.icon_label.bind('<Button-1>', handle_button_press)
        self.icon_label.bind('<B1-Motion>', handle_button_motion)
        self.icon_label.bind('<ButtonRelease-1>', handle_button_release)
        self.icon_label.bind('<Button-3>', handle_right_click)

        # Also bind to main frame and root for better coverage
        self.main_frame.bind('<Button-1>', handle_button_press)
        self.main_frame.bind('<B1-Motion>', handle_button_motion)
        self.main_frame.bind('<ButtonRelease-1>', handle_button_release)
        self.main_frame.bind('<Button-3>', handle_right_click)

        self.root.bind('<Button-1>', handle_button_press)
        self.root.bind('<B1-Motion>', handle_button_motion)
        self.root.bind('<ButtonRelease-1>', handle_button_release)
        self.root.bind('<Button-3>', handle_right_click)
        
        # Context menu
        self.context_menu = Menu(self.root, tearoff=0)
        # Compact (quick view)
        self.context_menu.add_command(label="Show Phrases", command=self.show_available_phrases)
        self.context_menu.add_command(label="Settings", command=lambda: self.open_settings_with_callback())
                
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exit", command=self.quit_app)
        
    def update_icon_display(self, angle=None, glow=0):
        """Update the icon display with rotation and glow effects.
        If angle is None, use the current persisted self.rotation_angle so the
        icon keeps its last orientation when idle or during glow-only updates.
        """
        if not self.original_image:
            return
        
        try:
            from PIL import ImageTk
            
            # Start with original image
            img = self.original_image.copy()
            
            # Apply rotation if needed
            # Pillow's Image.rotate(angle) rotates COUNTER-clockwise for positive angles.
            # We keep `self.rotation_angle` increasing (for bookkeeping) but pass
            # the negative angle to rotate clockwise visually.
            angle_to_use = self.rotation_angle if angle is None else angle
            if angle_to_use != 0:
                img = img.rotate(-angle_to_use, expand=False, fillcolor=(0, 0, 0, 0))
            
            # Apply glow effect if needed
            if glow > 0:
                img = self.apply_glow_effect(img, glow)
            
            # Convert to PhotoImage and assign once
            self.photo = ImageTk.PhotoImage(img)
            # If the UI hasn't been built yet (icon_label may not exist),
            # store the PhotoImage on the instance and skip configuring the widget.
            # setup_ui() will call update_icon_display() again after creating icon_label.
            try:
                if hasattr(self, 'icon_label') and self.icon_label is not None:
                    self.icon_label.config(image=self.photo)
            except Exception:
                # Swallow any widget update errors here; update will be attempted later.
                pass
            
        except Exception as e:
            logger.exception(f"Error updating icon display: {e}")
    
    def apply_glow_effect(self, img, intensity):
        """Apply a brightness-based pulse glow effect to the image."""
        try:
            from PIL import ImageEnhance
            
            # Create a copy for processing
            glow_img = img.copy()
            
            # Use configurable brightness intensity
            brightness_multiplier = 1.0 + (intensity * self.brightness_intensity)
            
            # Apply brightness enhancement for pulse effect
            enhancer = ImageEnhance.Brightness(glow_img)
            brightened_img = enhancer.enhance(brightness_multiplier)
            
            # Use configurable contrast intensity
            contrast_enhancer = ImageEnhance.Contrast(brightened_img)
            pulse_img = contrast_enhancer.enhance(1.0 + (intensity * self.contrast_intensity))
            
            # Use configurable color saturation intensity
            color_enhancer = ImageEnhance.Color(pulse_img)
            final_img = color_enhancer.enhance(1.0 + (intensity * self.color_intensity))
            
            return final_img
            
        except Exception as e:
            logger.exception(f"Error applying glow effect: {e}")
            return img
    
    def start_listening_animation(self):
        """Start the listening animation (glowing effect)."""
        self.is_listening = True
        if self.listening_thread is None or not self.listening_thread.is_alive():
            self.listening_thread = threading.Thread(target=self._listening_animation_loop, daemon=True)
            self.listening_thread.start()
            logger.info("Listening animation started")
    
    def stop_listening_animation(self):
        """Stop the listening animation."""
        self.is_listening = False
        logger.info("Listening animation stopped")
    
    def start_processing_animation(self):
        """Start the processing animation (rotation)."""
        self.is_processing = True
        self.rotation_speed = 0
        self.total_rotation = 0
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(target=self._processing_animation_loop, daemon=True)
            self.processing_thread.start()
            logger.info("Processing animation started")
    
    def stop_processing_animation(self, on_complete_callback=None):
        """Stop the processing animation with deceleration, but ensure minimum rotation.
        
        Args:
            on_complete_callback: Optional callback to execute when animation completes
        """
        self.is_processing = False
        self._on_processing_complete_callback = on_complete_callback
        logger.info("Processing animation stop initiated")
    
    def start_shake_animation(self):
        """Start the shake animation for unrecognized commands."""
        if self.is_shaking:
            return  # Don't start if already shaking
            
        self.is_shaking = True
        # Store original position
        self.original_position = (self.root.winfo_x(), self.root.winfo_y())
        
        if self.shake_thread is None or not self.shake_thread.is_alive():
            self.shake_thread = threading.Thread(target=self._shake_animation_loop, daemon=True)
            self.shake_thread.start()
            logger.info("Shake animation started")
    
    def stop_shake_animation(self):
        """Stop the shake animation and return to original position."""
        self.is_shaking = False
        if self.original_position:
            self.root.geometry(f"+{self.original_position[0]}+{self.original_position[1]}")
            self.original_position = None
        logger.info("Shake animation stopped")
    
    def _listening_animation_loop(self):
        """Animation loop for listening state with smooth pulse effect."""
        while self.is_listening:
            try:
                # Smooth oscillating pulse effect using sine wave
                import math
                # Use configurable pulse speed
                time_factor = time.time() * self.pulse_speed
                sine_wave = math.sin(time_factor)
                
                # Map sine wave (-1 to 1) to intensity (0 to 1)
                self.glow_intensity = (sine_wave + 1) / 2
                
                # Add configurable variation for more organic feel
                variation = math.sin(time_factor * self.pulse_variation_speed) * self.pulse_variation_intensity
                self.glow_intensity = max(0, min(1, self.glow_intensity + variation))
                
                # Update display on main thread
                # Use functools.partial to avoid unnecessary lambda creation
                self.root.after(0, functools.partial(self.update_icon_display, glow=self.glow_intensity))
                
                # Use configurable frame rate
                sleep_time = 1.0 / self.animation_fps
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.exception(f"Error in listening animation: {e}")
                break
        
        # Reset to normal when done
        self.root.after(0, lambda: self.update_icon_display())
    
    def _processing_animation_loop(self):
        """Animation loop for processing state with smooth rotation and minimum cycle guarantee."""
        while True:
            try:
                # Calculate minimum rotation needed
                min_rotation_needed = self.min_rotation_cycles * 360
                
                if self.is_processing:
                    # Accelerate rotation while processing
                    self.rotation_speed = min(self.max_rotation_speed, 
                                            self.rotation_speed + self.rotation_acceleration)
                else:
                    # Check if we've completed minimum rotation
                    if self.total_rotation >= min_rotation_needed:
                        # We've completed minimum rotation, start decelerating
                        self.rotation_speed = max(0, self.rotation_speed - self.rotation_deceleration)
                        
                        # Stop when speed is very low
                        if self.rotation_speed <= 0.1:
                            break
                    else:
                        # Haven't completed minimum rotation yet, keep rotating at reduced speed
                        target_speed = self.max_rotation_speed * 0.6  # 60% of max speed
                        if self.rotation_speed > target_speed:
                            self.rotation_speed = max(target_speed, self.rotation_speed - self.rotation_deceleration)
                        elif self.rotation_speed < target_speed:
                            self.rotation_speed = min(target_speed, self.rotation_speed + self.rotation_acceleration)
                
                # Update rotation angle and track total rotation
                old_angle = self.rotation_angle
                self.rotation_angle = (self.rotation_angle + self.rotation_speed) % 360
                
                # Track total rotation (handle wraparound)
                if old_angle > self.rotation_angle:  # Wrapped around from 359 to 0
                    self.total_rotation += (360 - old_angle) + self.rotation_angle
                else:
                    self.total_rotation += self.rotation_speed
                
                # Update display on main thread
                # Use functools.partial to avoid unnecessary lambda creation
                self.root.after(0, functools.partial(self.update_icon_display, angle=self.rotation_angle))
                
                # Use configurable frame rate
                sleep_time = 1.0 / self.animation_fps
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.exception(f"Error in processing animation: {e}")
                break
        
        # Capture final orientation so we can resume from here next time
        self.last_stop_angle = self.rotation_angle
        logger.info(f"Rotation stopped at angle: {self.last_stop_angle:.2f}°")
        # Do not snap back to 0 angle on stop to avoid visual jerk; keep last frame
        # Next start will reinitialize speed/trackers but reuse current angle.
        
        # Call the completion callback if one was provided
        if self._on_processing_complete_callback:
            self.root.after(0, self._on_processing_complete_callback)
            self._on_processing_complete_callback = None
    
    def _shake_animation_loop(self):
        """Animation loop for shake effect when command is not recognized."""
        if not self.original_position:
            return
            
        try:
            import math
            import random
            
            # Use configuration values instead of hardcoded ones
            shake_duration = self.shake_duration  # Total shake duration in seconds
            shake_intensity = self.shake_intensity   # Maximum shake distance in pixels
            shake_frequency = self.shake_frequency  # Shakes per second
            # Use shake_frequency in a harmless way to avoid unused-variable lint warnings
            _ = shake_frequency
            
            start_time = time.time()
            frame_time = 1.0 / 60  # 60 FPS
            
            while self.is_shaking and (time.time() - start_time) < shake_duration:
                elapsed = time.time() - start_time
                progress = elapsed / shake_duration
                
                # Reduce intensity over time (exponential decay)
                current_intensity = shake_intensity * math.exp(-3 * progress)
                
                # Generate horizontal shake offset only
                shake_x = random.uniform(-current_intensity, current_intensity)
                shake_y = 0  # No vertical movement
                
                # Apply shake to original position
                new_x = int(self.original_position[0] + shake_x)
                new_y = int(self.original_position[1] + shake_y)

                # Update position on main thread (use partial to avoid lambda)
                self.root.after(0, functools.partial(self.root.geometry, f"+{new_x}+{new_y}"))

                time.sleep(frame_time)
            
            # Return to original position
            self.root.after(0, self.stop_shake_animation)
            
        except Exception as e:
            logger.exception(f"Error in shake animation: {e}")
            self.root.after(0, self.stop_shake_animation)

    def show_phrase_textbox(self, _event):
        """Delegate showing the phrase textbox to AutocompletionListbox."""
        try:
            self._autocomplete.show(_event)
        except Exception as e:
            logger.exception(f"Error showing phrase textbox (delegate): {e}")

    def _load_available_phrases(self):
        """Load available phrases for autocomplete."""
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
        """Handle textbox focus in - clear placeholder."""
        if self.phrase_textbox.get() == "Type a phrase..." and self.phrase_textbox.cget('fg') == '#888888':
            self.phrase_textbox.delete(0, tk.END)
            self.phrase_textbox.configure(fg='white')

    def _on_textbox_focus_out(self, _event):
        """Handle textbox focus out - restore placeholder if empty."""
        if not self.phrase_textbox.get().strip():
            self.phrase_textbox.delete(0, tk.END)
            self.phrase_textbox.insert(0, "Type a phrase...")
            self.phrase_textbox.configure(fg='#888888')

    def _on_window_focus_out(self, _event):
        """Handle window focus out - close if clicking outside."""
        # Small delay to allow other events to process first
        self.root.after(100, self._check_and_close_textbox)

    def _check_and_close_textbox(self):
        """Check if we should close the textbox."""
        try:
            if self.phrase_window:
                # Check if any part of our textbox/listbox system has focus
                focused = self.root.focus_get()
                if (focused != self.phrase_textbox and 
                    (not self.phrase_listbox or focused != self.phrase_listbox) and
                    focused != self.phrase_window):
                    self._close_phrase_textbox()
        except Exception:
            pass

    def _on_textbox_key_release(self, _event):
        """Handle key release in textbox - update autocomplete."""
        try:
            if _event.keysym in ['Up', 'Down', 'Return', 'Escape']:
                return
            
            current_text = self.phrase_textbox.get().strip()
            
            # Skip placeholder text
            if current_text == "Type a phrase..." or not current_text:
                self.filtered_phrases = self.available_phrases.copy()
            else:
                # Filter phrases based on input
                current_lower = current_text.lower()
                self.filtered_phrases = [
                    phrase for phrase in self.available_phrases
                    if current_lower in phrase.lower()
                ]
            
            # Update or show autocomplete listbox
            if self.filtered_phrases and current_text and current_text != "Type a phrase...":
                self._show_autocomplete_listbox()
            else:
                self._hide_autocomplete_listbox()
                
        except Exception as e:
            logger.exception(f"Error in textbox key release: {e}")

    def _show_autocomplete_listbox(self):
        """Show autocomplete listbox with filtered phrases."""
        try:
            if not self.phrase_window:
                return
            
            # Create listbox if it doesn't exist
            if not self.phrase_listbox:
                # Calculate position below the textbox
                textbox_x = self.phrase_window.winfo_x()
                textbox_y = self.phrase_window.winfo_y()
                textbox_height = self.phrase_window.winfo_height()
                
                # Create listbox window
                self.listbox_window = Toplevel(self.phrase_window)
                self.listbox_window.title("")
                self.listbox_window.overrideredirect(True)
                self.listbox_window.attributes('-topmost', True)
                self.listbox_window.configure(bg='#2b2b2b')
                
                # Position below textbox
                listbox_width = 250
                max_listbox_height = min(120, len(self.filtered_phrases) * 20)
                pos_x = textbox_x
                pos_y = textbox_y + textbox_height + 2
                
                self.listbox_window.geometry(f"{listbox_width}x{max_listbox_height}+{pos_x}+{pos_y}")
                
                # Create frame for listbox
                listbox_frame = tk.Frame(self.listbox_window, bg='#2b2b2b', highlightthickness=1,
                                       highlightcolor='#4a9eff', highlightbackground='#404040')
                listbox_frame.pack(fill='both', expand=True, padx=2, pady=2)
                
                # Create listbox
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
                
                # Bind listbox events
                self.phrase_listbox.bind('<Double-Button-1>', self._on_listbox_double_click)
                self.phrase_listbox.bind('<Return>', self._on_listbox_enter)
                self.phrase_listbox.bind('<Button-1>', self._on_listbox_click)
            
            # Clear and populate listbox
            self.phrase_listbox.delete(0, tk.END)
            for phrase in self.filtered_phrases[:10]:  # Limit to 10 items
                self.phrase_listbox.insert(tk.END, phrase)
            
            # Select first item if available
            if self.phrase_listbox.size() > 0:
                self.phrase_listbox.selection_set(0)
                self.phrase_listbox.activate(0)
            
        except Exception as e:
            logger.exception(f"Error showing autocomplete listbox: {e}")

    def _hide_autocomplete_listbox(self):
        """Hide autocomplete listbox."""
        try:
            if hasattr(self, 'listbox_window') and self.listbox_window:
                self.listbox_window.destroy()
                self.listbox_window = None
            self.phrase_listbox = None
        except Exception as e:
            logger.exception(f"Error hiding autocomplete listbox: {e}")

    def _on_listbox_navigate_up(self, _event):
        """Handle up arrow in textbox - navigate listbox."""
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
        """Handle down arrow in textbox - navigate listbox."""
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
        """Handle single click in listbox."""
        # Keep focus on textbox for continued typing
        self.phrase_textbox.focus_set()

    def _on_listbox_double_click(self, _event):
        """Handle double click in listbox - select phrase."""
        self._select_phrase_from_listbox()

    def _on_listbox_enter(self, _event):
        """Handle enter in listbox - select phrase."""
        self._select_phrase_from_listbox()

    def _select_phrase_from_listbox(self):
        """Select phrase from listbox and execute."""
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
        """Handle enter in textbox - execute phrase or select from listbox."""
        try:
            # If listbox is showing and has selection, use that
            if (self.phrase_listbox and self.phrase_listbox.size() > 0 and 
                self.phrase_listbox.curselection()):
                self._select_phrase_from_listbox()
            else:
                # Execute the typed phrase
                self._execute_phrase()
        except Exception as e:
            logger.exception(f"Error in textbox enter: {e}")

    def _execute_phrase(self):
        """Execute the phrase in the textbox."""
        try:
            phrase = self.phrase_textbox.get().strip()
            
            # Skip placeholder text or empty input
            if not phrase or phrase == "Type a phrase...":
                self._close_phrase_textbox()
                return
            
            logger.info(f"Executing phrase from textbox: {phrase}")
            
            # Close the textbox first
            self._close_phrase_textbox()
            
            # Start processing animation
            self.start_processing_animation()
            
            # Execute the command in a separate thread
            threading.Thread(target=self._execute_phrase_async, args=(phrase,), daemon=True).start()
            
        except Exception as e:
            logger.exception(f"Error executing phrase: {e}")
            self._close_phrase_textbox()

    def _execute_phrase_async(self, phrase):
        """Execute phrase asynchronously."""
        try:
            # Use command manager to handle the phrase
            success = command_manager.handle_voice_command(phrase)
            
            if success:
                logger.info("Phrase executed successfully")
                # Stop processing animation
                self.stop_processing_animation()
            else:
                # Stop processing animation and start shake once rotation completes
                self.stop_processing_animation(on_complete_callback=self.start_shake_animation)
                logger.info("Phrase execution failed")
                
        except Exception as e:
            logger.exception(f"Error in async phrase execution: {e}")
            self.stop_processing_animation(on_complete_callback=self.start_shake_animation)

    def _close_phrase_textbox(self, _event=None):
        """Close the phrase textbox and autocomplete."""
        try:
            self._hide_autocomplete_listbox()
            
            if self.phrase_window:
                self.phrase_window.destroy()
                self.phrase_window = None
            
            self.phrase_textbox = None
            logger.info("Phrase textbox closed")
            
        except Exception as e:
            logger.exception(f"Error closing phrase textbox: {e}")
            # Force cleanup
            self.phrase_window = None
            self.phrase_textbox = None
            self.phrase_listbox = None

    # PhrasesReferenceDialog moved to ui.components.phrase_listbox

    def disable_actions(self):
        """Disable floating icon actions (called when settings window opens)."""
        self.actions_enabled = False
        self.settings_window_open = True
        logger.info("Floating icon actions disabled - settings window opened")
    
    def enable_actions(self):
        """Enable floating icon actions (called when settings window closes)."""
        self.actions_enabled = True
        self.settings_window_open = False
        logger.info("Floating icon actions enabled - settings window closed")
    
    def get_last_stop_angle(self):
        """Return the angle (0-359) where the rotation last stopped."""
        return self.last_stop_angle
    
    def on_click(self, _event):
        """Handle icon click to start voice command."""
        # Check if actions are disabled (settings window is open)
        if not self.actions_enabled or self.settings_window_open:
            logger.info("Voice command ignored - actions are disabled (settings window is open)")
            return
            
        logger.info("Voice command activated")
        
        if self.is_listening or self.is_processing or self.is_shaking:
            logger.info("Already processing or shaking, ignoring click")
            return  # Ignore clicks during animation
        
        # Start voice command in separate thread
        threading.Thread(target=self.handle_voice_command, daemon=True).start()
    
    def handle_voice_command(self):
        """Handle voice command in separate thread."""
        try:
            logger.info("Voice command initiated by user click")
                  
            # Calibrate if needed (may be skipped if recently calibrated)
            speech_recognizer._ensure_calibrated()
            # Start listening animation
            self.start_listening_animation()
            
            # Get speech input
            voice_text = speech_recognizer.get_speech_as_text()
            
            # Stop listening animation
            self.stop_listening_animation()
            
            if voice_text:
                # Start processing animation
                self.start_processing_animation()
                
                # Process command
                success = command_manager.handle_voice_command(voice_text)
                
                if success:
                    logger.info("Voice command executed successfully")
                    # Stop processing animation
                    self.stop_processing_animation()
                else:
                    # Stop processing animation and start shake once rotation completes
                    self.stop_processing_animation(on_complete_callback=self.start_shake_animation)
                    logger.info("Voice command execution failed")                                  
                
            else:
                logger.info("No voice input detected")
                # Trigger visual feedback for unrecognized command
                self.start_shake_animation()
                
        except Exception as e:
            logger.exception(f"Error handling voice command: {e}")
            self.stop_listening_animation()
            self.stop_processing_animation()
    
    def open_settings_with_callback(self):
        """Open settings form and disable actions while it's open."""
        try:
            # Disable actions immediately
            self.disable_actions()
            
            # Open settings form with callback
            open_modern_settings_form(self, on_close_callback=self.enable_actions)
            
        except Exception as e:
            logger.exception(f"Error opening settings: {e}")
            # Re-enable actions if there was an error
            self.enable_actions()
    
    def show_available_phrases(self):
        """Show the compact centered dark popup listing phrases."""
        try:
            from .available_phrases import show_available_phrases
            show_available_phrases(parent=self.root)
        except Exception as e:
            logger.exception(f"Error showing centered phrases popup: {e}")
    
    def show_context_menu(self, _event):
        """Show context menu on right-click."""
        try:
            self.context_menu.post(_event.x_root, _event.y_root)
        except Exception as e:
            logger.exception(f"Error showing context menu: {e}")
    
    def center_window(self):
        """Position the window based on saved coordinates from settings.json (last dragged position)."""
        try:
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            # Get screen dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Always use the saved offset values from settings.json (last dragged position)
            # Convert offset values back to absolute coordinates
            if self.config_offset_x < 0:
                # Negative offset means distance from right edge
                x = screen_width - width + self.config_offset_x
            else:
                # Positive offset means absolute x coordinate
                x = self.config_offset_x
                
            if self.config_offset_y < 0:
                # Negative offset means distance from bottom edge
                y = screen_height - height + self.config_offset_y
            else:
                # Positive offset means absolute y coordinate
                y = self.config_offset_y
            
            # Ensure the window stays within screen bounds
            x = max(0, min(x, screen_width - width))
            y = max(0, min(y, screen_height - height))
            
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            logger.info(f"Window positioned at ({x}, {y}) using saved coordinates from settings (offset_x={self.config_offset_x}, offset_y={self.config_offset_y})")
        except Exception as e:
            logger.exception(f"Error positioning window: {e}")

    def save_window_position(self):
        """Save the current window position as offset values to settings (becomes the new last dragged position)."""
        try:
            # Get current window position
            current_x = self.root.winfo_x()
            current_y = self.root.winfo_y()
            
            # Get screen and window dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            # Calculate offset values based on current position
            # Store as negative offsets from bottom-right corner for consistency
            offset_x = current_x - (screen_width - width)
            offset_y = current_y - (screen_height - height)
            
            # Update configuration with new offset values (this becomes the new last dragged position)
            config_manager.set_setting('Floating_Icon.Position.Offset_X', offset_x)
            config_manager.set_setting('Floating_Icon.Position.Offset_Y', offset_y)
            
            # Update local variables
            self.config_offset_x = offset_x
            self.config_offset_y = offset_y
            
            logger.info(f"Saved new dragged position to settings: offset_x={offset_x}, offset_y={offset_y} (absolute coords: {current_x}, {current_y})")
            
        except Exception as e:
            logger.exception(f"Error saving window position: {e}")

    def quit_app(self):
        """Quit the application."""
        logger.info("Shutting down Assistant...")
          
        self.is_listening = False
        self.is_processing = False
        self.is_shaking = False
        try:
            self.root.withdraw()
            self.root.quit()               
            self.root.destroy()            
        except tk.TclError:
            # Window already destroyed, ignore
            pass
        
    def force_quit_app(self):
        """Forcefully Quit the application."""
        logger.info("Forcefully Shutting down Assistant...")

        try:
            self.root.withdraw()
            self.root.quit()
            self.root.destroy()
            os._exit(0)  # Force exit to ensure all threads are killed
        except tk.TclError:
            # Window already destroyed, ignore
            pass
        
    def run(self):
        """Run the main loop."""
        try:
            global floating_icon_instance
            # Register global instance before starting loop so internal actions can access it
            floating_icon_instance = self
            logger.info("Starting floating icon main loop")
            self.root.mainloop()
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
        # Note: quit_app() is called by main.py finally block, not here to avoid duplicate logs    