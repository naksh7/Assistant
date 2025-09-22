import time
import speech_recognition as sr
from .app_logger import logger
from .config_manager import config_manager

class SpeechRecognizer:
    """Speech recognition class with configurable settings."""
    
    def __init__(self):
        """Initialize the speech recognizer with configuration."""
        logger.info("Initializing SpeechRecognizer...")
        # Load configuration from settings
        self.load_config()
        
        # Module-level recognizer and lazy microphone initialization
        self._recognizer = sr.Recognizer()
        self._microphone = None  # initialized lazily
        # Timestamp of last ambient calibration (seconds since epoch)
        self._calibrated_at = 0.0
        
        # Apply initial recognizer configuration
        self._apply_recognizer_config()
        
        logger.info("Speech recognizer initialized")
    
    def load_config(self):
        """Load configuration parameters from settings.json."""
        try:
            # Get speech recognition configuration using the new config manager
            speech_config = config_manager.get_settings_section('Speech_Recognition')
            
            # Recognition settings
            # Recognition settings
            # Energy threshold for detecting voice vs. silence. Integer; lower = more sensitive.
            # Typical default: 300. Increase if noisy (e.g., 400-1000). Decrease for quiet environments.
            self.energy_threshold = speech_config.get('Energy_Threshold', 300)
            # Whether to use dynamic adjustment of the energy threshold. Boolean (True/False).
            # True lets the recognizer adapt to background noise automatically.
            self.dynamic_energy_threshold = speech_config.get('Dynamic_Energy_Threshold', True)
            # Pause threshold (seconds) - how long of a silence indicates the end of a phrase.
            # Float; smaller values cut phrases earlier (e.g., 0.5), larger values wait longer (e.g., 1.5).
            self.pause_threshold = speech_config.get('Pause_Threshold', 0.8)
            
            # Handle operation_timeout - convert string "None" to actual None
            # Operation timeout for blocking recognizer operations (seconds).
            # Accepts int/float (number of seconds) or None to disable timeout.
            # Some configs may store the literal strings "None" or "null"; these are
            # converted to Python None here. Example: 5 or None
            operation_timeout_value = speech_config.get('Operation_Timeout', None)
            if operation_timeout_value == "None" or operation_timeout_value == "null":
                self.operation_timeout = None
            else:
                self.operation_timeout = operation_timeout_value
            
            # Audio capture settings
            # Duration (seconds) to sample ambient noise during calibration.
            # Float/int; typical 0.5-2.0. Longer durations produce a more reliable ambient noise estimate.
            self.ambient_noise_duration = speech_config.get('Ambient_Noise_Duration', 1)
            
            # Handle listen_timeout and phrase_time_limit - ensure they're numeric or None
            # listen_timeout: maximum seconds to wait for phrase to start. Numeric or None.
            # Example: 5 (wait up to 5s for speech to start) or None (wait indefinitely).
            listen_timeout_value = speech_config.get('Listen_Timeout', None)
            if listen_timeout_value == "None" or listen_timeout_value == "null":
                self.listen_timeout = None
            else:
                self.listen_timeout = listen_timeout_value
                
            # phrase_time_limit: maximum seconds to record a single phrase. Numeric or None.
            # Example: 10 (cap phrase to 10s) or None (no limit). Use to avoid very long recordings.
            phrase_time_limit_value = speech_config.get('Phrase_Time_Limit', None)
            if phrase_time_limit_value == "None" or phrase_time_limit_value == "null":
                self.phrase_time_limit = None
            else:
                self.phrase_time_limit = phrase_time_limit_value
            
            # Language and calibration settings
            # Language tag for recognizer (BCP-47). Example: 'en-US', 'en-GB', 'es-ES'. String.
            self.language = speech_config.get('Language', 'en-US')
            # Calibration interval in seconds. How often to re-run ambient noise calibration.
            # Integer; e.g., 300 = calibrate every 5 minutes. Use larger numbers to reduce blocking calls.
            self.calibration_interval = speech_config.get('Calibration_Interval', 300)
            
            logger.info("Speech recognition configuration loaded successfully")
            
        except Exception as e:
            logger.exception(f"Error loading speech recognition configuration: {e}")
            # Set default values if config loading fails
            logger.warning("Using default speech recognition configuration due to config loading error")
            self.set_default_config()
    
    def set_default_config(self):
        """Set default configuration values if loading from settings fails."""
        # Recognition settings
        self.energy_threshold = 300
        self.dynamic_energy_threshold = True
        self.pause_threshold = 0.8
        self.operation_timeout = None
        
        # Audio capture settings
        self.ambient_noise_duration = 1
        self.listen_timeout = None
        self.phrase_time_limit = None
        
        # Language and calibration settings
        self.language = 'en-US'
        self.calibration_interval = 300
        
        logger.info("Default speech recognition configuration set")
    
    def _apply_recognizer_config(self):
        """Apply current configuration to the recognizer."""
        try:
            self._recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
            self._recognizer.pause_threshold = self.pause_threshold
            self._recognizer.energy_threshold = self.energy_threshold
            
            # operation_timeout may not be present in older versions of the library
            if self.operation_timeout is not None:
                self._recognizer.operation_timeout = self.operation_timeout
                
        except Exception as e:
            logger.warning(f"Error applying recognizer configuration: {e}")
    
    def _get_microphone(self):
        """Create and return the module microphone, lazily."""
        if self._microphone is None:
            try:
                self._microphone = sr.Microphone()
                logger.info("Microphone initialized successfully")
            except Exception as e:
                logger.exception(f"Failed to initialize microphone: {e}")
                raise
        return self._microphone
    
    def _ensure_calibrated(self):
        """Calibrate ambient noise if not calibrated recently.

        Uses a configurable calibration interval to avoid repeated blocking calls.
        """
        now = time.time()
        if now - self._calibrated_at < self.calibration_interval:
            return

        try:
            mic = self._get_microphone()
            logger.info("Calibrating for background noise...")
            with mic as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=self.ambient_noise_duration)
            self._calibrated_at = now
            logger.info("Ambient noise calibration complete")
        except Exception as e:
            logger.exception(f"Ambient calibration failed: {e}")
    
    def get_speech_as_text(self) -> str:
        """Listen for speech and return it as text.

        Returns empty string on failures. Reuses recognizer and microphone.
        """
        try:
            # Apply current configuration to recognizer
            self._apply_recognizer_config()
             
            logger.info("Listening for voice input...")
            mic = self._get_microphone()
            
            start_time = time.perf_counter()
            with mic as source:
                audio = self._recognizer.listen(
                    source, 
                    timeout=self.listen_timeout, 
                    phrase_time_limit=self.phrase_time_limit
                )
            
            listen_time = time.perf_counter() - start_time
            logger.info(f"Audio captured in {listen_time:.2f}s")

            logger.info("Processing audio...")
            
            recognition_start = time.perf_counter()
            text = self._recognizer.recognize_google(audio, language=self.language)
            recognition_time = time.perf_counter() - recognition_start
            
            logger.info(f"Voice input recognized: '{text}'")
            logger.info(f"Recognition completed in {recognition_time:.2f}s")

            return text.lower()
        
        except sr.WaitTimeoutError:
            logger.warning("No speech detected within timeout period")
            return ""
        except sr.UnknownValueError:
            logger.warning("Could not understand the audio - speech not clear or recognizable")
            return ""
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return ""
        except Exception as e:
            logger.exception(f"An unexpected error occurred in speech recognition: {e}")
            return ""


# Global speech recognizer instance for easy import and backward compatibility
speech_recognizer = SpeechRecognizer()
