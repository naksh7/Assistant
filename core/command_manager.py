import subprocess
import webbrowser
import os
import pyautogui
from typing import Dict, List, Optional, Tuple, Any
from .app_logger import logger
from .config_manager import config_manager

class CommandManager:
    """
    Manages and executes commands using json_reader.
    Supports browser, command, and keys actions.
    """
    
    def __init__(self):
        """Initialize CommandManager with config_manager."""
        logger.info("Initializing CommandManager...")
        self.config_manager = config_manager
        logger.info("CommandManager initialized successfully")
        
    @property
    def commands(self) -> Dict[str, Dict]:
        """Get all commands from config_manager."""
        return self.config_manager.get_all_commands()
    
    @property
    def settings(self) -> Dict[str, Any]:
        """Get command settings from config_manager."""
        # Return empty dict for now since we don't have command settings in new structure
        return {}
    
    def load_commands(self) -> bool:
        """
        Reload commands from the external JSON file using config_manager.
        
        Returns:
            bool: True if commands loaded successfully, False otherwise
        """
        logger.info("Reloading commands via config_manager...")
        result = self.config_manager.reload_all()
        if result:
            commands = self.config_manager.get_all_commands()
            logger.info(f"Successfully reloaded {len(commands)} commands")
        else:
            logger.error("Failed to reload commands")
        return result
    
    def reload_commands(self) -> bool:
        """Reload commands from file (for runtime updates)."""
        logger.info("Reloading commands from file...")
        return self.load_commands()
    
    def save_commands(self) -> bool:
        """Save current commands back to the JSON file."""
        result = self.config_manager.save_commands()
        if result:
            logger.info("Commands saved successfully")
        else:
            logger.error("Failed to save commands")
        return result
    
    def add_command(self, description: str, command_data: Dict) -> bool:
        """
        Add a new command dynamically.
        
        Args:
            description (str): Command description/name (unique identifier)
            command_data (dict): Command configuration
            
        Returns:
            bool: True if command added successfully
        """
        logger.info(f"Adding command: {description}")
        return self.config_manager.add_command(description, command_data)
    
    def remove_command(self, description: str) -> bool:
        """
        Remove a command.
        
        Args:
            description (str): Command description/name to remove
            
        Returns:
            bool: True if command removed successfully
        """
        logger.info(f"Removing command: {description}")
        return self.config_manager.remove_command(description)
    
    def parse_voice_command(self, voice_text: str) -> Tuple[Optional[str], str, str]:
        """
        Parse voice command to find matching command and extract additional text.
        
        Args:
            voice_text (str): Raw voice input text (already lowercased by app_speech)
            
        Returns:
            tuple: (description, matched_pattern, additional_text)
        """
        voice_text_lower = voice_text.lower().strip()        
        partial_match = True  # Default to partial match since we don't have command settings in new structure
        
        # Collect all matches with their pattern lengths (for prioritization)
        matches = []
        
        for description, command_data in self.commands.items():
            phrases = command_data.get('Phrases', [])
            
            for pattern in phrases:
                pattern_lower = pattern.lower()
                
                if partial_match:
                    if pattern_lower in voice_text_lower:
                        # Calculate match quality (longer patterns are better matches)
                        match_length = len(pattern_lower)
                        # Check if this is an exact word boundary match (even better)
                        is_word_boundary = self._is_word_boundary_match(voice_text_lower, pattern_lower)
                        
                        matches.append({
                            'description': description,
                            'pattern': pattern,
                            'pattern_search': pattern_lower,
                            'match_length': match_length,
                            'is_word_boundary': is_word_boundary,
                            'original_voice_text': voice_text
                        })
                else:
                    if pattern_lower == voice_text_lower:
                        # Exact match - highest priority
                        additional_text = ""
                        return description, pattern, additional_text
        
        # Sort matches by priority:
        # 1. Word boundary matches first
        # 2. Then by pattern length (longer patterns are more specific)
        # 3. Then by alphabetical order for consistency
        if matches:
            matches.sort(key=lambda x: (
                not x['is_word_boundary'],  # Word boundary matches first (False sorts before True)
                -x['match_length'],         # Longer patterns first (negative for descending)
                x['description']            # Alphabetical for consistency
            ))
            
            best_match = matches[0]
            # Extract additional text (remove the pattern)
            pattern_to_remove = best_match['pattern']
            additional_text = voice_text.replace(pattern_to_remove, "").strip()
            
            return best_match['description'], best_match['pattern'], additional_text
        
        # No command found - return None to indicate no match
        return None, "", voice_text
    
    def _is_word_boundary_match(self, search_text: str, pattern: str) -> bool:
        """
        Check if the pattern matches at word boundaries in the search text.
        This helps distinguish between partial matches and more meaningful matches.
        
        Args:
            search_text (str): The text to search in (already lowercased)
            pattern (str): The pattern to find (already lowercased)
            
        Returns:
            bool: True if pattern is found at word boundaries
        """
        import re
        # Create a regex pattern that matches the pattern at word boundaries
        # \b ensures word boundaries, re.escape handles special regex characters
        word_boundary_pattern = r'\b' + re.escape(pattern) + r'\b'
        return bool(re.search(word_boundary_pattern, search_text))
    
    def execute_command(self, description: str, additional_text: str = "") -> bool:
        """
        Execute a command by its description/name.
        
        Args:
            description (str): Command description/name identifier
            additional_text (str): Additional text for context (e.g., search terms)
            
        Returns:
            bool: True if command executed successfully
        """
        
        if description not in self.commands:
            logger.warning(f"Unknown command: {description}")
            return False
        
        command_data = self.commands[description]
        action = command_data.get('Action', 'command')
        command = command_data.get('Command', '')        
        # Use description as the command identifier
        
        logger.info(f"Executing command: {description}")
        
        try:
            # Execute based on action type           
            if action == 'browser':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                return self._execute_browser(formatted_command)
            elif action == 'command':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                return self._execute_batch(formatted_command)
            elif action == 'keys':
                # Handle keyboard shortcuts
                # New behaviour: read shortcut exclusively from the 'Command' field.
                # Per recent settings change, do NOT fallback to legacy keys like
                # 'shortcukeys' or 'shortcut_keys'. This makes the mapping explicit.
                shortcut_keys = command_data.get('Command')
                if not shortcut_keys:
                    logger.error(f"No shortcut specified in 'Command' for keys action on '{description}'")
                    return False
                return self._execute_keys(shortcut_keys)
            elif action == 'internal':
                # Internal application action (e.g., open phrases dialog)
                internal_cmd = command_data.get('Command', '')
                return self._execute_internal(internal_cmd)
            else:
                logger.error(f"Unknown action type: {action}. Supported actions: 'browser', 'command', 'keys'")
                return False
                
        except Exception as e:
            logger.exception(f"Error executing command '{description}': {e}")
            return False
    
    def test_execute_command(self, description: str, additional_text: str = "") -> Tuple[bool, str]:
        """
        Test execute a command by its description/name - similar to execute_command but with feedback.
        
        Args:
            description (str): Command description/name identifier
            additional_text (str): Additional text for context (e.g., search terms)
            
        Returns:
            tuple: (success: bool, message: str) - success status and feedback message
        """
        
        command_data = self.commands[description]
        action = command_data.get('Action', 'command')
        command = command_data.get('Command', '')        
        
        logger.info(f"Testing command: {description}")
        
        try:
            # Test execute based on action type           
            if action == 'browser':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                success = self._execute_browser(formatted_command)
                if success:
                    return True, f"Successfully opened URL: {formatted_command}"
                else:
                    return False, f"Failed to open URL: {formatted_command}"
            elif action == 'command':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                success = self._execute_batch(formatted_command)
                if success:
                    return True, f"Successfully executed command: {formatted_command}"
                else:
                    return False, f"Failed to execute command: {formatted_command}"
            elif action == 'keys':
                # Handle keyboard shortcuts
                shortcut_keys = command_data.get('Command')
                if not shortcut_keys:
                    message = f"No shortcut specified in 'Command' for keys action on '{description}'"
                    logger.error(message)
                    return False, message
                success = self._execute_keys(shortcut_keys)
                if success:
                    return True, f"Successfully executed keyboard shortcut: {shortcut_keys}"
                else:
                    return False, f"Failed to execute keyboard shortcut: {shortcut_keys}"
            elif action == 'internal':
                internal_cmd = command_data.get('Command', '')
                success = self._execute_internal(internal_cmd)
                if success:
                    return True, f"Successfully executed internal action: {internal_cmd}"
                else:
                    return False, f"Failed to execute internal action: {internal_cmd}"
            else:
                message = f"Unknown action type: {action}. Supported actions: 'browser', 'command', 'keys'"
                logger.error(message)
                return False, message
                
        except Exception as e:
            message = f"Error executing command '{description}': {str(e)}"
            logger.exception(message)
            return False, message
    
    def test_execute_direct(self, action: str, command: str, additional_text: str = "") -> Tuple[bool, str]:
        """
        Test execute a command directly with action and command parameters.
        
        Args:
            action (str): Action type ('command', 'browser', 'keys')
            command (str): Command string to execute
            additional_text (str): Additional text for context (e.g., search terms)
            
        Returns:
            tuple: (success: bool, message: str) - success status and feedback message
        """
        
        if not action or not command:
            message = "Action type and Command are required"
            logger.warning(message)
            return False, message
        
        logger.info(f"Testing direct command - Action: {action}, Command: {command}")
        
        try:
            # Test execute based on action type           
            if action == 'browser':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                success = self._execute_browser(formatted_command)
                if success:
                    return True, f"Successfully opened URL: {formatted_command}"
                else:
                    return False, f"Failed to open URL: {formatted_command}"
            elif action == 'command':
                # Replace placeholders in command
                formatted_command = self._format_command_string(command, additional_text)
                success = self._execute_batch(formatted_command)
                if success:
                    return True, f"Successfully executed command: {formatted_command}"
                else:
                    return False, f"Failed to execute command: {formatted_command}"
            elif action == 'keys':
                # Handle keyboard shortcuts
                success = self._execute_keys(command)
                if success:
                    return True, f"Successfully executed keyboard shortcut: {command}"
                else:
                    return False, f"Failed to execute keyboard shortcut: {command}"
            elif action == 'internal':
                success = self._execute_internal(command)
                if success:
                    return True, f"Successfully executed internal action: {command}"
                else:
                    return False, f"Failed to execute internal action: {command}"
            else:
                message = f"Unknown action type: {action}. Supported actions: 'browser', 'command', 'keys'"
                logger.error(message)
                return False, message
                
        except Exception as e:
            message = f"Error executing direct command (Action: {action}, Command: {command}): {str(e)}"
            logger.exception(message)
            return False, message
    
    def _format_command_string(self, command_string: str, query: str) -> str:
        """
        Format command string by replacing placeholders.
        
        Args:
            command_string (str): Command string with placeholders
            query (str): Query text to substitute
            
        Returns:
            str: Formatted command string
        """
        # Replace common placeholders
        formatted = command_string.replace('{query}', query.replace(" ", "+"))
        formatted = formatted.replace('{raw_query}', query)
        
        # For URL encoding, do a simple replacement if needed
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            formatted = formatted.replace('{encoded_query}', encoded_query)
        except ImportError:
            # Fallback: just replace spaces with +
            formatted = formatted.replace('{encoded_query}', query.replace(" ", "+"))
        
        return formatted
    
    def _execute_keys(self, shortcut_keys: str) -> bool:
        """
        Execute keyboard shortcut using pyautogui.
        
        Args:
            shortcut_keys (str): Keyboard shortcut string (e.g., "ctrl+c", "windows+shift+t")
            
        Returns:
            bool: True if keys executed successfully
        """
        try:
            # Parse the shortcut keys string
            keys = [key.strip().lower() for key in shortcut_keys.split('+')]
                        
            # Execute the key combination
            if len(keys) == 1:
                # Single key press
                pyautogui.press(keys[0])
            else:
                # Key combination with modifiers
                pyautogui.hotkey(*keys)
            
            logger.info(f"Successfully executed keyboard shortcut: {shortcut_keys}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to execute keyboard shortcut '{shortcut_keys}': {e}")
            return False

    def _execute_batch(self, command: str) -> bool:
        """Execute direct command using subprocess."""
        try:
            # Execute the command directly            
            subprocess.Popen(
                command,
                shell=True,
                text=True
            )
            return True
        except Exception as e:
            logger.exception(f"Failed to execute command: {e}")
            return False
    
    def _execute_browser(self, url: str) -> bool:
        """Execute browser command."""
        try:
            self._open_with_browser(url)
            logger.info(f"Browser opened with URL: {url}")
            return True
        except Exception as e:
            logger.exception(f"Failed to open browser: {e}")
            return False

    def _execute_internal(self, internal_cmd: str) -> bool:
        """Execute internal application actions.

        Supported internal commands:
            - show_phrases: Open the available phrases dialog
        """
        try:
            internal_cmd = (internal_cmd or '').strip().lower()
            if not internal_cmd:
                logger.error("No internal command specified")
                return False

            if internal_cmd == 'show_phrases':
                # Delayed import to avoid circular dependency at module import time
                try:
                    from ui.floating_icon import floating_icon_instance
                except Exception:
                    floating_icon_instance = None
                try:
                    if floating_icon_instance is not None:
                        floating_icon_instance.show_available_phrases()
                        return True
                    else:
                        # Fallback: direct import of function (spawns a transient root if needed)
                        from ui.available_phrases import show_available_phrases
                        show_available_phrases()
                        return True
                except Exception as e:
                    logger.exception(f"Failed to execute internal command 'show_phrases': {e}")
                    return False
            elif internal_cmd in ('show_settings', 'open_settings'):
                try:
                    from ui.floating_icon import floating_icon_instance
                except Exception:
                    floating_icon_instance = None
                try:
                    if floating_icon_instance is not None:
                        floating_icon_instance.open_settings_with_callback()
                        return True
                    else:
                        logger.error("Floating icon instance not available to show settings")
                        return False
                except Exception as e:
                    logger.exception(f"Failed to execute internal command 'show_settings': {e}")
                    return False
            else:
                logger.error(f"Unknown internal command: {internal_cmd}")
                return False
        except Exception as e:
            logger.exception(f"Error executing internal command '{internal_cmd}': {e}")
            return False
    
    def _open_with_browser(self, url: str) -> None:
        """Open URL with preferred browser or fallback to default."""
        try:
            # Try the new structure first, then fallback to old structure
            browser_path = config_manager.get_setting('Default_Browser', '').strip()
            if not browser_path:
                browser_path = config_manager.get_setting('Application.Browser_Path', '').strip()

            if browser_path and os.path.isfile(browser_path):
                try:
                    logger.info(f"Opening URL with configured browser: {browser_path}")
                    subprocess.Popen([browser_path, url], shell=True)
                    return
                except Exception as e:
                    logger.warning(f"Failed to open with {browser_path}: {e}")

            # Fallback
            logger.info("Using system default browser")
            webbrowser.open(url)

        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            webbrowser.open(url)
    
    def handle_voice_command(self, voice_text: str) -> bool:
        """
        Handle a voice command by parsing and executing it.
        
        Args:
            voice_text (str): Raw voice input text
            
        Returns:
            bool: True if command executed successfully, False if no command found
        """
        logger.info(f"Processing voice command: {voice_text}")
        
        description, matched_pattern, additional_text = self.parse_voice_command(voice_text)
        
        if description:
            logger.info(f"Executing '{description}': {matched_pattern}")
            if additional_text:
                logger.info(f"Additional text: '{additional_text}'")
            return self.execute_command(description, additional_text)
        else:
            logger.warning(f"No matching command found for: {voice_text}")
            self.show_unrecognized_command_message(voice_text)
            return False
    
    def show_unrecognized_command_message(self, voice_text: str):
        """
        Show message when command is not recognized.
        
        Args:
            voice_text (str): The unrecognized voice input
        """
        logger.info(f"Command not recognized: '{voice_text}'. Please try again with a valid command.")
        logger.warning(f"❌ Command not recognized: '{voice_text}'")
        logger.info(f"💡 Try saying something like: 'open notepad', 'search google', or 'take screenshot'")

        # TODO: Add visual shaking feedback to the floating icon
        # This would require passing a reference to the UI or using a callback system
    
    def list_commands(self) -> Dict[str, str]:
        """
        Get a list of all available commands with descriptions.
        
        Returns:
            dict: Command description to description mapping
        """
        return {
            description: description  # Use description as both key and value since it's self-descriptive
            for description, cmd_data in self.commands.items()
        }
    
    def get_command_phrases(self, description: str) -> List[str]:
        """
        Get phrases for a specific command.
        
        Args:
            description (str): Command description/name identifier
            
        Returns:
            list: List of phrases for the command
        """
        command = self.config_manager.get_command(description)
        if command:
            return command.get('Phrases', [])
        return []
    
    def get_all_phrases_with_descriptions(self) -> List[Dict[str, Any]]:
        """
        Get all available phrases with their associated command descriptions.
        
        Returns:
            list: List of dictionaries containing phrase info:
                  [{'phrase': str, 'description': str, 'action': str, 'command': str}, ...]
        """
        phrases_info = []
        
        try:
            for description, cmd_data in self.commands.items():
                phrases = cmd_data.get('Phrases', [])
                action = cmd_data.get('Action', 'command')
                command = cmd_data.get('Command', '')
                
                # Truncate long commands for display
                display_command = command if len(command) <= 80 else command[:80] + "..."
                
                for phrase in phrases:
                    if phrase.strip():  # Only include non-empty phrases
                        phrases_info.append({
                            'phrase': phrase.strip(),
                            'description': description,
                            'action': action,
                            'command': display_command
                        })
            
            # Sort alphabetically by phrase for easier browsing
            phrases_info.sort(key=lambda x: x['phrase'].lower())
            
            logger.info(f"Retrieved {len(phrases_info)} phrases from {len(self.commands)} commands")
            
        except Exception as e:
            logger.exception(f"Error getting all phrases with descriptions: {e}")
        
        return phrases_info
    
    def _create_default_commands_file(self) -> None:
        """Create a default commands.json file if it doesn't exist."""
        # This is now handled by AppCommandConfig
        logger.info("Default commands file creation handled by AppCommandConfig")

# Global command manager instance
command_manager = CommandManager()
