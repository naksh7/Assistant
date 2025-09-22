"""
Utility Functions

Common utility functions used across the application.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union
from core.app_logger import logger


class PathUtils:
    """Path and file system utilities."""
    
    @staticmethod
    def get_project_root() -> Path:
        """Get the project root directory."""
        if getattr(sys, 'frozen', False):
            # Running as EXE
            return Path(sys.executable).parent
        else:
            # Running as script
            return Path(__file__).parent.parent
    
    @staticmethod
    def get_appdata_directory(app_name: str = "Assistant") -> Path:
        """
        Get the application data directory for the current user.
        
        Args:
            app_name: Name of the application subdirectory
            
        Returns:
            Path to application data directory
        """
        if sys.platform.startswith('win'):
            # Windows: Use APPDATA
            appdata = os.environ.get('APPDATA')
            if appdata:
                return Path(appdata) / app_name
        
        # Fallback for other platforms or if APPDATA not available
        home = Path.home()
        if sys.platform.startswith('linux'):
            return home / '.config' / app_name
        elif sys.platform.startswith('darwin'):
            return home / 'Library' / 'Application Support' / app_name
        else:
            return home / f'.{app_name}'
    
    @staticmethod
    def get_resource_path(resource_name: str) -> Optional[Path]:
        """
        Get path to a resource file.
        
        Args:
            resource_name: Name of the resource file (e.g., 'icon.png', 'settings.json')
            
        Returns:
            Path to resource or None if not found
        """
        # For PyInstaller executable
        if getattr(sys, 'frozen', False):
            # Check bundled resources (in _MEIPASS)
            if hasattr(sys, '_MEIPASS'):
                bundled_path = Path(sys._MEIPASS) / 'resources' / resource_name
                if bundled_path.exists():
                    return bundled_path
            
            # Check relative to executable (but don't create external directories)
            exe_dir = Path(sys.executable).parent
            resource_path = exe_dir / 'resources' / resource_name
            if resource_path.exists():
                return resource_path
        
        # For script mode - get project root
        root = PathUtils.get_project_root()
        
        # Check resources directory
        resource_path = root / 'resources' / resource_name
        if resource_path.exists():
            return resource_path
        
        # Check root directory
        resource_path = root / resource_name
        if resource_path.exists():
            return resource_path
        
        logger.warning(f"Resource not found: {resource_name}")
        return None
    
    @staticmethod
    def ensure_directory_exists(directory: Union[str, Path]) -> bool:
        """
        Ensure a directory exists, create if it doesn't.
        
        Args:
            directory: Directory path
            
        Returns:
            True if directory exists or was created successfully
        """
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Could not create directory {directory}: {e}")
            return False
    
    @staticmethod
    def copy_file_safe(src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """
        Safely copy a file from source to destination.
        
        Args:
            src: Source file path
            dst: Destination file path
            
        Returns:
            True if file copied successfully
        """
        try:
            import shutil
            src_path = Path(src)
            dst_path = Path(dst)
            
            # Ensure destination directory exists
            PathUtils.ensure_directory_exists(dst_path.parent)
            
            # Copy file
            shutil.copy2(src_path, dst_path)
            return True
        except Exception as e:
            logger.error(f"Error copying file from {src} to {dst}: {e}")
            return False


class JsonUtils:
    """JSON file utilities."""
    
    @staticmethod
    def load_json(file_path: Union[str, Path], default: Any = None) -> Any:
        """
        Load JSON from file with error handling.
        
        Args:
            file_path: Path to JSON file
            default: Default value if file cannot be loaded
            
        Returns:
            Loaded JSON data or default value
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"JSON file not found: {file_path}")
            return default
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return default
        except Exception as e:
            logger.error(f"Error loading JSON from {file_path}: {e}")
            return default
    
    @staticmethod
    def save_json(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
        """
        Save data to JSON file with error handling.
        
        Args:
            data: Data to save
            file_path: Path to save file
            indent: JSON indentation
            
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            PathUtils.ensure_directory_exists(Path(file_path).parent)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON to {file_path}: {e}")
            return False


class ProcessUtils:
    """Process and system utilities."""
    
    @staticmethod
    def run_command(command: str, shell: bool = True, capture_output: bool = False) -> Dict[str, Any]:
        """
        Run a system command with error handling.
        
        Args:
            command: Command to run
            shell: Whether to use shell
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Dictionary with result information
        """
        try:
            if capture_output:
                result = subprocess.run(
                    command,
                    shell=shell,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    'success': result.returncode == 0,
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                process = subprocess.Popen(command, shell=shell)
                return {
                    'success': True,
                    'process': process
                }
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            logger.error(f"Error running command '{command}': {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def is_process_running(process_name: str) -> bool:
        """
        Check if a process is running.
        
        Args:
            process_name: Name of the process
            
        Returns:
            True if process is running
        """
        try:
            import psutil
            for process in psutil.process_iter(['name']):
                if process.info['name'] and process_name.lower() in process.info['name'].lower():
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking process {process_name}: {e}")
            return False


class ValidationUtils:
    """Data validation utilities."""
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        Check if a string is a valid URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid
        """
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def is_valid_file_path(path: str) -> bool:
        """
        Check if a string is a valid file path.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid and exists
        """
        try:
            return Path(path).exists()
        except Exception:
            return False
    
    @staticmethod
    def is_valid_command_data(command_data: Dict[str, Any]) -> bool:
        """
        Validate command data structure.
        
        Args:
            command_data: Command data to validate
            
        Returns:
            True if command data is valid
        """
        required_fields = ['Phrases', 'Action', 'Command']
        
        if not isinstance(command_data, dict):
            return False
        
        # Check required fields
        for field in required_fields:
            if field not in command_data:
                return False
        
        # Validate phrases
        phrases = command_data.get('Phrases', [])
        if not isinstance(phrases, list) or not phrases:
            return False
        
        # Validate action
        action = command_data.get('Action', '')
        if action not in ['browser', 'command', 'keys']:
            return False
        
        # Validate command
        command = command_data.get('Command', '')
        if not isinstance(command, str) or not command.strip():
            return False
        
        return True


class StringUtils:
    """String manipulation utilities."""
    
    @staticmethod
    def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate a string to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add if truncated
            
        Returns:
            Truncated string
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename by removing invalid characters.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        import re
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove leading/trailing periods and spaces
        sanitized = sanitized.strip('. ')
        return sanitized or 'unnamed'
    
    @staticmethod
    def format_command_string(template: str, query: str) -> str:
        """
        Format command string by replacing placeholders.
        
        Args:
            template: Command template with placeholders
            query: Query text to substitute
            
        Returns:
            Formatted command string
        """
        # Replace common placeholders
        formatted = template.replace('{query}', query.replace(" ", "+"))
        formatted = formatted.replace('{raw_query}', query)
        
        # URL encode if needed
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote_plus(query)
            formatted = formatted.replace('{encoded_query}', encoded_query)
        except ImportError:
            # Fallback: just replace spaces with +
            formatted = formatted.replace('{encoded_query}', query.replace(" ", "+"))
        
        return formatted


class ConfigUtils:
    """Configuration utilities."""
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge user configuration with base configuration.
        
        Args:
            base_config: Base configuration
            user_config: User configuration
            
        Returns:
            Merged configuration
        """
        merged = base_config.copy()
        
        def merge_dict(base: Dict, user: Dict) -> Dict:
            result = base.copy()
            for key, value in user.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        return merge_dict(merged, user_config)
    
    @staticmethod
    def get_nested_value(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
        """
        Get nested value from dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key_path: Dot-separated key path
            default: Default value if key not found
            
        Returns:
            Value or default
        """
        try:
            keys = key_path.split('.')
            value = data
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    @staticmethod
    def set_nested_value(data: Dict[str, Any], key_path: str, value: Any) -> None:
        """
        Set nested value in dictionary using dot notation.
        
        Args:
            data: Dictionary to modify
            key_path: Dot-separated key path
            value: Value to set
        """
        keys = key_path.split('.')
        current = data
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[keys[-1]] = value
