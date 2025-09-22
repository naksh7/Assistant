"""
Centralized Configuration Manager

A more robust and feature-rich configuration manager that consolidates
settings and commands management with validation, caching, and event handling.

Configuration Strategy:
- Default templates are kept in the 'config/' directory (read-only)
- User-writable configurations are copied to AppData on first run
- All subsequent operations use AppData files for persistence
"""

import os
import sys
import threading
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Union
from core.app_logger import logger
from core.utils import JsonUtils, PathUtils, ValidationUtils


class ConfigManager:
    """
    Centralized configuration manager for settings and commands.
    
    Configuration Strategy:
    - Default templates are kept in the 'config/' directory (read-only)
    - On first run, templates are copied to AppData for user modification
    - All subsequent operations use AppData files for persistence
    - This allows updates to default templates without affecting user customizations
    """
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._settings = {}
        self._commands = {}
        self._lock = threading.RLock()
        self._cache = {}
        self._auto_save = True
        # Last operation error message (useful for UI to fetch human-friendly messages)
        self._last_error_message = ""
        # Structured conflicts mapping phrase -> existing command description
        self._last_conflicts = {}

        # Initialize configuration paths
        self._init_config_paths()
        
        # Load configurations
        self._load_configurations()
        
        logger.info("ConfigManager initialized with AppData storage")
    
    def _init_config_paths(self) -> None:
        """Initialize configuration file paths and copy templates if needed."""
        try:
            # Get AppData directory
            self._user_config_dir = self._get_user_config_directory()
            
            # Ensure user config directory exists
            PathUtils.ensure_directory_exists(self._user_config_dir)
            
            # Copy template files if they don't exist in AppData
            self._ensure_user_config_files()
            
            logger.info(f"User configuration directory: {self._user_config_dir}")
        except Exception as e:
            logger.exception(f"Error initializing configuration paths: {e}")
    
    def _get_user_config_directory(self) -> Path:
        """Get the user configuration directory in AppData."""
        if sys.platform.startswith('win'):
            # Windows: Use APPDATA
            appdata = os.environ.get('APPDATA')
            if appdata:
                return Path(appdata) / 'Assistant'
        
        # Fallback for other platforms or if APPDATA not available
        home = Path.home()
        if sys.platform.startswith('linux'):
            return home / '.config' / 'Assistant'
        elif sys.platform.startswith('darwin'):
            return home / 'Library' / 'Application Support' / 'Assistant'
        else:
            return home / '.Assistant'
    
    def _get_template_config_directory(self) -> Path:
        """Get the template configuration directory."""
        if getattr(sys, 'frozen', False):
            # Running as EXE - use bundled config
            if hasattr(sys, '_MEIPASS'):
                return Path(sys._MEIPASS) / 'config'
            else:
                # Fallback if _MEIPASS not available
                return Path(sys.executable).parent / 'config'
        else:
            # Running as script - use project config
            return PathUtils.get_project_root() / 'config'
    
    def _ensure_user_config_files(self) -> None:
        """Ensure user configuration files exist, copy from templates if needed."""
        template_dir = self._get_template_config_directory()
        config_files = ['settings.json', 'commands.json']
        
        for config_file in config_files:
            template_path = template_dir / config_file
            user_path = self._user_config_dir / config_file
            
            if not user_path.exists() and template_path.exists():
                try:
                    # Copy template to user directory
                    shutil.copy2(template_path, user_path)
                    logger.info(f"Copied template {config_file} to user config directory")
                except Exception as e:
                    logger.error(f"Failed to copy template {config_file}: {e}")
            elif not template_path.exists():
                logger.warning(f"Template file not found: {template_path}")
                # Create empty file if template doesn't exist
                if not user_path.exists():
                    try:
                        default_data = {} if config_file.endswith('.json') else ""
                        JsonUtils.save_json(default_data, user_path)
                        logger.info(f"Created empty {config_file} in user config directory")
                    except Exception as e:
                        logger.error(f"Failed to create empty {config_file}: {e}")
    
    def _get_user_config_path(self, filename: str) -> Path:
        """Get the path to a user configuration file in AppData."""
        return self._user_config_dir / filename
    
    def _get_template_config_path(self, filename: str) -> Path:
        """Get the path to a template configuration file."""
        return self._get_template_config_directory() / filename
    
    def _load_configurations(self) -> None:
        """Load all configuration files from user directory."""
        try:
            with self._lock:
                # Load settings from user directory
                settings_path = self._get_user_config_path('settings.json')
                self._settings = JsonUtils.load_json(settings_path, {})
                
                # Load commands from user directory
                commands_path = self._get_user_config_path('commands.json')
                commands_data = JsonUtils.load_json(commands_path, {})
                
                # Separate commands from settings
                self._commands = {k: v for k, v in commands_data.items() if k != 'settings'}
                
                # Clear cache
                self._cache.clear()
                
                logger.info("Configurations loaded from user directory")
        except Exception as e:
            logger.exception(f"Error loading configurations: {e}")
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to default templates."""
        try:
            with self._lock:
                # Remove existing user config files
                config_files = ['settings.json', 'commands.json']
                for config_file in config_files:
                    user_path = self._get_user_config_path(config_file)
                    if user_path.exists():
                        user_path.unlink()
                        logger.info(f"Removed user config file: {user_path}")
                
                # Re-copy templates
                self._ensure_user_config_files()
                
                # Reload configurations
                self._load_configurations()
                
                logger.info("Configuration reset to defaults")
                return True
        except Exception as e:
            logger.error(f"Error resetting configuration to defaults: {e}")
            return False
    
    def get_template_config(self, config_type: str) -> Dict[str, Any]:
        """
        Get the template configuration (read-only).
        
        Args:
            config_type: 'settings' or 'commands'
            
        Returns:
            Template configuration data
        """
        try:
            filename = f"{config_type}.json"
            template_path = self._get_template_config_path(filename)
            return JsonUtils.load_json(template_path, {})
        except Exception as e:
            logger.error(f"Error loading template {config_type}: {e}")
            return {}
           
    def _notify_change(self, section: str, key: str, old_value: Any, new_value: Any) -> None:
        """Notify about a configuration change (simple log only).

        Listener registration was removed; this method now only logs a debug message.
        """
        try:
            logger.debug(f"Config change: section={section}, key={key}, old={old_value}, new={new_value}")
        except Exception:
            pass
    
    # Settings methods
    def get_setting(self, key_path: str, default: Any = None) -> Any:
        """
        Get a setting value using dot notation.
        
        Args:
            key_path: Dot-separated path (e.g., 'Application.Icon_Path')
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        with self._lock:
            # Check cache first
            cache_key = f"setting:{key_path}"
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            try:
                keys = key_path.split('.')
                value = self._settings
                
                for key in keys:
                    value = value[key]
                
                # Cache the result
                self._cache[cache_key] = value
                return value
                
            except (KeyError, TypeError):
                return default
    
    def set_setting(self, key_path: str, value: Any, save: bool = None) -> bool:
        """
        Set a setting value using dot notation.
        
        Args:
            key_path: Dot-separated path
            value: Value to set
            save: Whether to save immediately (uses auto_save if None)
            
        Returns:
            True if set successfully
        """
        with self._lock:
            try:
                keys = key_path.split('.')
                current = self._settings
                
                # Navigate to parent of target key
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Get old value for change notification
                old_value = current.get(keys[-1])
                
                # Set the value
                current[keys[-1]] = value
                
                # Clear cache for this key
                cache_key = f"setting:{key_path}"
                if cache_key in self._cache:
                    del self._cache[cache_key]
                
                # Notify listeners
                self._notify_change('settings', key_path, old_value, value)
                
                # Save if requested
                if save is True or (save is None and self._auto_save):
                    return self.save_settings()
                
                return True
                
            except Exception as e:
                logger.error(f"Error setting {key_path}: {e}")
                return False
    
    def get_settings_section(self, section: str) -> Dict[str, Any]:
        """Get an entire settings section."""
        with self._lock:
            return self._settings.get(section, {}).copy()
    
    def save_settings(self) -> bool:
        """Save settings to user configuration file."""
        with self._lock:
            try:
                settings_path = self._get_user_config_path('settings.json')
                success = JsonUtils.save_json(self._settings, settings_path)
                if success:
                    logger.info(f"Settings saved to: {settings_path}")
                else:
                    logger.error(f"Failed to save settings to: {settings_path}")
                
                return success
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                return False
    
    # Commands methods
    def get_command(self, description: str) -> Optional[Dict[str, Any]]:
        """Get a command by description/name."""
        with self._lock:
            return self._commands.get(description, {}).copy() if description in self._commands else None
    
    def get_all_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get all commands."""
        with self._lock:
            return self._commands.copy()
    
    def add_command(self, description: str, command_data: Dict[str, Any], save: bool = None) -> bool:
        """
        Add a new command.
        
        Args:
            description: Command description/name (unique identifier)
            command_data: Command configuration
            save: Whether to save immediately
            
        Returns:
            True if added successfully
        """
        if not ValidationUtils.is_valid_command_data(command_data):
            message = f"Invalid command data for {description}"
            logger.error(message)
            # Clear any previous structured conflicts
            self._last_conflicts = {}
            self._last_error_message = message
            return False

        # Check for duplicate phrases in existing commands
        conflicts = self._find_phrase_conflicts(description, command_data.get('Phrases', []))
        if conflicts:
            # Build human-friendly message listing conflicting phrases and existing commands
            conflict_msgs = [f"{phrase} -> {existing_desc}" for phrase, existing_desc in conflicts.items()]
            message = (
                "Duplicate phrase(s) detected: \n" + "\n".join(conflict_msgs) +
                ". \nRemove the old command(s) or Update the phrase(s) to resolve the conflict."
            )
            logger.warning(message)
            # Store structured conflicts for programmatic access
            self._last_conflicts = conflicts.copy()
            self._last_error_message = message
            return False
        
        with self._lock:
            old_value = self._commands.get(description)
            self._commands[description] = command_data.copy()
            
            # Notify listeners
            self._notify_change('commands', description, old_value, command_data)
            
            # Save if requested
            if save is True or (save is None and self._auto_save):
                return self.save_commands()
            
            return True
    
    def update_command(self, description: str, command_data: Dict[str, Any], save: bool = None) -> bool:
        """
        Update an existing command.
        
        Args:
            description: Command description/name
            command_data: New command configuration
            save: Whether to save immediately
            
        Returns:
            True if updated successfully
        """
        if description not in self._commands:
            logger.error(f"Command {description} does not exist")
            return False
        
        if not ValidationUtils.is_valid_command_data(command_data):
            message = f"Invalid command data for {description}"
            logger.error(message)
            # Clear structured conflicts
            self._last_conflicts = {}
            self._last_error_message = message
            return False

        # Check for duplicate phrases in other commands (exclude current description)
        conflicts = self._find_phrase_conflicts(description, command_data.get('Phrases', []), exclude_description=description)
        if conflicts:
            conflict_msgs = [f"'{phrase}' -> {existing_desc}" for phrase, existing_desc in conflicts.items()]
            message = (
                "Duplicate phrase(s) detected: " + ", ".join(conflict_msgs) +
                ". Remove the old command(s) or update the phrases to resolve the conflict."
            )
            logger.warning(message)
            # Store structured conflicts for programmatic access
            self._last_conflicts = conflicts.copy()
            self._last_error_message = message
            return False
        
        with self._lock:
            old_value = self._commands[description].copy()
            self._commands[description] = command_data.copy()
            
            # Notify listeners
            self._notify_change('commands', description, old_value, command_data)
            
            # Save if requested
            if save is True or (save is None and self._auto_save):
                return self.save_commands()
            
            return True
    
    def remove_command(self, description: str, save: bool = None) -> bool:
        """
        Remove a command.
        
        Args:
            description: Command description/name to remove
            save: Whether to save immediately
            
        Returns:
            True if removed successfully
        """
        with self._lock:
            if description not in self._commands:
                logger.warning(f"Command {description} does not exist")
                return False
            
            old_value = self._commands[description].copy()
            del self._commands[description]
            
            # Notify listeners
            self._notify_change('commands', description, old_value, None)
            
            # Save if requested
            if save is True or (save is None and self._auto_save):
                return self.save_commands()
            
            return True
    
    def save_commands(self) -> bool:
        """Save commands to user configuration file."""
        with self._lock:
            try:
                # Validate there are no phrase conflicts across commands before saving
                conflicts = self._validate_all_phrase_conflicts()
                if conflicts:
                    # Build message
                    conflict_msgs = [f"'{phrase}' -> {desc}" for phrase, desc in conflicts.items()]
                    message = (
                        "Duplicate phrase(s) detected across commands: " + ", ".join(conflict_msgs) +
                        ". Remove the old command(s) or update the phrases to resolve the conflict."
                    )
                    logger.warning(message)
                    # Store structured conflicts for programmatic access
                    self._last_conflicts = conflicts.copy()
                    self._last_error_message = message
                    return False

                commands_path = self._get_user_config_path('commands.json')
                # Add back any command settings if they exist
                commands_data = self._commands.copy()

                success = JsonUtils.save_json(commands_data, commands_path)
                if success:
                    logger.info(f"Commands saved to: {commands_path}")
                else:
                    logger.error(f"Failed to save commands to: {commands_path}")
                
                return success
            except Exception as e:
                logger.error(f"Error saving commands: {e}")
                return False

    def _validate_all_phrase_conflicts(self) -> Dict[str, str]:
        """
        Check all commands for duplicate phrases across commands.

        Returns:
            dict mapping conflicting_phrase -> existing_command_description
        """
        # Reuse the single-command conflict checker to ensure consistent
        # normalization and exclusion behavior. For each command, call
        # `_find_phrase_conflicts` and aggregate results. This keeps the
        # logic DRY and avoids divergent normalization logic.
        conflicts: Dict[str, str] = {}
        try:
            for desc, cmd in self._commands.items():
                phrases = cmd.get('Phrases', []) if isinstance(cmd, dict) else []
                if not phrases:
                    continue

                # For each command, ask _find_phrase_conflicts to report
                # conflicts against the rest of the commands by excluding
                # the current description.
                cmd_conflicts = self._find_phrase_conflicts(desc, phrases, exclude_description=desc)
                # Merge - if same phrase conflicts with multiple commands,
                # keep the first seen (existing behavior mirrored).
                for ph, owner in cmd_conflicts.items():
                    if ph not in conflicts:
                        conflicts[ph] = owner
        except Exception as e:
            logger.exception(f"Error validating phrase conflicts: {e}")

        return conflicts
    
    # Utility methods
    def reload_all(self) -> bool:
        """Reload all configurations from files."""
        try:
            self._load_configurations()
            logger.info("All configurations reloaded")
            return True
        except Exception as e:
            logger.error(f"Error reloading configurations: {e}")
            return False
    
    def export_config(self, file_path: Union[str, Path], config_type: str = 'all') -> bool:
        """
        Export configuration to a file.
        
        Args:
            file_path: Path to export file
            config_type: Type of config ('settings', 'commands', 'all')
            
        Returns:
            True if exported successfully
        """
        try:
            with self._lock:
                if config_type == 'settings':
                    data = self._settings
                elif config_type == 'commands':
                    data = self._commands
                elif config_type == 'all':
                    data = {
                        'settings': self._settings,
                        'commands': self._commands
                    }
                else:
                    logger.error(f"Invalid config type: {config_type}")
                    return False
                
                return JsonUtils.save_json(data, file_path)
        except Exception as e:
            logger.error(f"Error exporting config: {e}")
            return False
    
    def import_config(self, file_path: Union[str, Path], config_type: str = 'all', 
                     merge: bool = True) -> bool:
        """
        Import configuration from a file.
        
        Args:
            file_path: Path to import file
            config_type: Type of config ('settings', 'commands', 'all')
            merge: Whether to merge with existing config
            
        Returns:
            True if imported successfully
        """
        try:
            data = JsonUtils.load_json(file_path)
            if not data:
                return False
            
            with self._lock:
                if config_type == 'settings':
                    if merge:
                        self._settings.update(data)
                    else:
                        self._settings = data
                elif config_type == 'commands':
                    if merge:
                        self._commands.update(data)
                    else:
                        self._commands = data
                elif config_type == 'all':
                    if 'settings' in data:
                        if merge:
                            self._settings.update(data['settings'])
                        else:
                            self._settings = data['settings']
                    if 'commands' in data:
                        if merge:
                            self._commands.update(data['commands'])
                        else:
                            self._commands = data['commands']
                else:
                    logger.error(f"Invalid config type: {config_type}")
                    return False
                
                # Clear cache and save
                self._cache.clear()
                
                if self._auto_save:
                    self.save_settings()
                    self.save_commands()
                
                logger.info(f"Configuration imported from {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error importing config: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the current configuration."""
        with self._lock:
            return {
                'settings_sections': list(self._settings.keys()),
                'settings_count': len(self._settings),
                'commands_count': len(self._commands),
                'command_descriptions': list(self._commands.keys()),
                'cache_size': len(self._cache),
                'auto_save': self._auto_save,
                'listeners': 0,
                'user_config_dir': str(self._user_config_dir),
                'template_config_dir': str(self._get_template_config_directory())
            }

    def get_last_error_message(self) -> str:
        """Return the last human-friendly error message from config operations."""
        with self._lock:
            # Build combined message: base message (if any) plus structured conflicts
            base = self._last_error_message or ""
            if self._last_conflicts:
                # Format conflicts into readable lines
                conflict_lines = [f"'{ph}' -> {desc}" for ph, desc in self._last_conflicts.items()]
                conflicts_text = "Conflicting phrases: " + ", ".join(conflict_lines)
                if base:
                    return base + "\n" + conflicts_text
                return conflicts_text

            return base

    def _find_phrase_conflicts(self, new_description: str, phrases: list, exclude_description: str = None) -> Dict[str, str]:
        """
        Find phrases that conflict with existing commands.

        Args:
            new_description: Description of the command being added/updated
            phrases: List of phrases to check
            exclude_description: Optional command description to exclude from checks

        Returns:
            dict: mapping 'conflicting_phrase' -> 'existing_command_description'
        """
        conflicts = {}
        try:
            normalized_new = [p.strip().lower() for p in (phrases or []) if p and p.strip()]
            if not normalized_new:
                return conflicts

            for desc, cmd in self._commands.items():
                if exclude_description and desc == exclude_description:
                    continue

                existing_phrases = cmd.get('Phrases', []) if isinstance(cmd, dict) else []
                for ep in existing_phrases:
                    if not ep or not ep.strip():
                        continue
                    ep_norm = ep.strip().lower()
                    for np_raw, np_norm in zip(phrases, normalized_new):
                        # If normalized phrase equals existing normalized phrase, it's a conflict
                        if np_norm == ep_norm:
                            conflicts[np_raw.strip()] = desc
        except Exception as e:
            logger.exception(f"Error checking phrase conflicts: {e}")

        return conflicts
    
    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        with self._lock:
            self._cache.clear()
            logger.info("Configuration cache cleared")
    
    def set_auto_save(self, enabled: bool) -> None:
        """Enable or disable auto-save."""
        with self._lock:
            self._auto_save = enabled
            logger.info(f"Auto-save {'enabled' if enabled else 'disabled'}")
    
    def get_user_config_directory(self) -> Path:
        """Get the user configuration directory path."""
        return self._user_config_dir
    
    def get_template_config_directory(self) -> Path:
        """Get the template configuration directory path."""
        return self._get_template_config_directory()
    
    def backup_user_config(self, backup_path: Union[str, Path] = None) -> bool:
        """
        Create a backup of user configuration files.
        
        Args:
            backup_path: Path to save backup (optional)
            
        Returns:
            True if backup created successfully
        """
        try:
            if backup_path is None:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self._user_config_dir.parent / f"Assistant_backup_{timestamp}"
            
            backup_path = Path(backup_path)
            
            # Create backup directory
            PathUtils.ensure_directory_exists(backup_path)
            
            # Copy configuration files
            for config_file in ['settings.json', 'commands.json']:
                src_path = self._get_user_config_path(config_file)
                if src_path.exists():
                    dst_path = backup_path / config_file
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"Backed up {config_file}")
            
            logger.info(f"Configuration backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating configuration backup: {e}")
            return False
    
    def restore_from_backup(self, backup_path: Union[str, Path]) -> bool:
        """
        Restore configuration from backup.
        
        Args:
            backup_path: Path to backup directory
            
        Returns:
            True if restored successfully
        """
        try:
            backup_path = Path(backup_path)
            
            if not backup_path.exists():
                logger.error(f"Backup path does not exist: {backup_path}")
                return False
            
            with self._lock:
                # Restore configuration files
                for config_file in ['settings.json', 'commands.json']:
                    src_path = backup_path / config_file
                    if src_path.exists():
                        dst_path = self._get_user_config_path(config_file)
                        shutil.copy2(src_path, dst_path)
                        logger.info(f"Restored {config_file}")
                
                # Reload configurations
                self._load_configurations()
                
                logger.info(f"Configuration restored from: {backup_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error restoring configuration: {e}")
            return False


# Global configuration manager instance
config_manager = ConfigManager()
