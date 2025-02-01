from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import time
import os
import yaml
import random
from supabase import create_client
from queue import Queue, Empty
from threading import Thread, Lock

@dataclass
class ConnectionSettings:
    """Manages connection settings for the Additv client.
    
    This class handles connection-related settings such as API tokens, URLs,
    and printer identification.
    """
    url: Optional[str] = None
    registration_token: Optional[str] = None
    service_user: Optional[str] = None
    printer_id: Optional[str] = None
    access_key: Optional[str] = None
    refresh_token: Optional[str] = None
    anon_key: Optional[str] = None

class SettingsManager:
    """Handles persistence and management of Additv connection settings."""
    
    def __init__(self, plugin_data_folder: str, logger=None):
        """Initialize settings manager with default settings file location."""
        self._settings_file: Path = Path(plugin_data_folder) / "additv.yaml"
        self._settings: ConnectionSettings = ConnectionSettings()
        self._logger = logger
        self._load_settings()
    
    @property
    def settings(self) -> ConnectionSettings:
        """Get the current connection settings."""
        return self._settings
    
    def _load_settings(self) -> None:
        """Load settings from yaml file."""
        if self._settings_file.exists():
            try:
                with open(self._settings_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self._settings = ConnectionSettings(**data)
            except Exception as e:
                self._logger.error(f"Failed to load settings: {str(e)}")
    
    def _save_settings(self) -> None:
        """Save settings to yaml file."""
        try:
            # Ensure directory exists
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            settings_dict = {
                'url': self._settings.url,
                'registration_token': self._settings.registration_token,
                'service_user': self._settings.service_user,
                'printer_id': self._settings.printer_id,
                'access_key': self._settings.access_key,
                'refresh_token': self._settings.refresh_token,
                'anon_key': self._settings.anon_key
            }
            with open(self._settings_file, 'w') as f:
                yaml.safe_dump(settings_dict, f)
        except Exception as e:
            self._logger.error(f"Failed to save settings: {str(e)}")
    
    def update_access_key(self, new_key: str) -> None:
        """Update the access key and save settings."""
        self._settings.access_key = new_key
        self._save_settings()

    def update_settings(self, **kwargs) -> None:
        """Update multiple settings at once."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self._save_settings()

    def register_printer(self, url: str, registration_token: str, printer_name: str) -> bool:
        """Register printer with Additv service and save credentials."""
        import requests
        try:
            # Prepare request
            register_url = f"{url}/functions/v1/register-printer"
            headers = {"Content-Type": "application/json"}
            data = {
                "token": registration_token,
                "name": printer_name
            }

            # Make request
            response = requests.post(register_url, headers=headers, json=data)
            response_data = response.json()

            # Update settings
            self.update_settings(
                url=url,
                registration_token=registration_token,
                printer_id=str(response_data["printer_id"]),
                service_user=response_data["service_user"],
                access_key=response_data["access_token"],
                refresh_token=response_data["refresh_token"],
                anon_key=response_data["anon_key"]
            )
            
            return True
        except Exception as e:
            self._logger.error(f"Failed to register printer: {str(e)}")
            return False

@dataclass
class QueuedOperation:
    """Represents a database operation in the queue"""
    type: str
    table: str
    data: Any
    extra: Dict[str, Any]
    retries: int = 0

class AdditvClient:
    """Client for handling asynchronous communication with Additv backend services"""
    """Client for handling asynchronous communication with Additv backend services"""
    
    def __init__(self, printer_name: str, logger=None, 
                 on_token_refresh: Optional[Callable[[str], None]] = None, 
                 plugin_data_folder: Optional[str] = None,
                 max_retry_delay: float = 15.0):
        if not printer_name:
            raise ValueError("Printer name is required")
        if not plugin_data_folder:
            raise ValueError("Plugin data folder is required")
            
        self._logger = logger
        self._max_retry_delay = max_retry_delay
        self._settings_manager = SettingsManager(plugin_data_folder, logger)
        self._supabase = None
        self._printer_name = printer_name
        self._on_token_refresh = on_token_refresh
        self._queue = Queue()
        self._running = True
        self._lock = Lock()
        self._worker_thread = Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        
        # Check for environment variables
        env_url = os.environ.get("ADDITV_URL")
        env_token = os.environ.get("ADDITV_REGISTRATION_TOKEN")
        
        if env_url:
            self._settings_manager.update_settings(url=env_url)
        if env_token:
            self._settings_manager.update_settings(registration_token=env_token)
        
        # Initialize connection or register if needed
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the client, handling registration if needed."""
        settings = self._settings_manager.settings
        
        # Case 1: We have URL and registration token but no access credentials
        if (settings.url and settings.registration_token and 
            not settings.access_key and not settings.printer_id):
            self._logger.info("Attempting to register printer with Additv")
            if not self._settings_manager.register_printer(
                settings.url, 
                settings.registration_token,
                self._printer_name
            ):
                self._logger.error("Failed to register printer")
                return
                
            # Registration successful, settings are updated, proceed to connect
            self._connect()
            
        # Case 2: We have connection credentials
        elif settings.url and settings.access_key:
            self._connect()
            
        # Case 3: Missing required settings
        else:
            self._logger.warning("URL or access credentials not configured")

    @property
    def settings(self) -> ConnectionSettings:
        """Get the current connection settings."""
        return self._settings_manager.settings

    def _connect(self):
        """Establish connection to Additv backend"""
        try:
            self._supabase = create_client(self.settings.url, self.settings.anon_key)
            
            # Set up auth state change listener
            def handle_auth_change(event, session):
                if event == 'TOKEN_REFRESHED' and session:
                    # Update and persist both tokens
                    self._settings_manager.update_settings(
                        access_key=session.access_token,
                        refresh_token=session.refresh_token
                    )
                    self._logger.info("Saved updated tokens from Supabase refresh")
                    # Call the token refresh callback if configured
                    if self._on_token_refresh:
                        self._on_token_refresh(session.access_token)
            
            self._supabase.auth.on_auth_state_change(handle_auth_change)
            
            # Initial session setup
            self._supabase.auth.set_session(
                access_token=self.settings.access_key,
                refresh_token=self.settings.refresh_token
            )
            
            # Verify connection
            currentUser = self._supabase.auth.get_user()
            if currentUser.user.id != self.settings.service_user:
                raise Exception(f"User ID mismatch. Expected: {self.settings.service_user}, Got: {currentUser.user.id}")
                
            self._logger.info("Successfully established connection to Additv backend")
        except Exception as e:
            self._logger.error(f"Connection failed: {str(e)}")

    def _process_queue(self):
        """Process operations from the queue"""
        while self._running:
            try:
                operation = self._queue.get(timeout=1.0)
                try:
                    operation()  # Execute the queued operation
                except Exception as e:
                    self._logger.error(f"Operation failed: {str(e)}")
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                self._logger.error(f"Error processing queue: {str(e)}")

    def publish_printer_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish a printer event to the Additv backend"""
        if self._running and self._supabase:
            self._queue.put(
                lambda: self._supabase.table("printer_events")
                    .insert({"event": event_type, "data": data, "source_timestamp": datetime.now(timezone.utc).isoformat()})
                    .execute()
            )

    def publish_telemetry_event(self, telemetry: Dict) -> None:
        """Publish a single telemetry event to the queue for processing"""
        if self._running and self._supabase:
            self._queue.put(
                lambda: self._supabase.table("printer_telemetry")
                    .insert({"data": telemetry, "source_timestamp": datetime.now(timezone.utc).isoformat()})
                    .execute()
            )

    def stop(self):
        """Stop the queue processor"""
        with self._lock:
            self._running = False
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
