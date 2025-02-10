from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
import os
import json
from threading import Thread, Lock
from queue import Queue, Empty
import yaml
from supabase import create_client

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
            self._logger.debug(f"Loading settings from {self._settings_file}")
            try:
                with open(self._settings_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self._settings = ConnectionSettings(**data)
                        self._logger.debug("Settings loaded successfully")
                    else:
                        self._logger.debug("Settings file is empty")
            except Exception as e:
                self._logger.error(f"Failed to load settings: {str(e)}", exc_info=True)
        else:
            self._logger.debug("Settings file does not exist, using defaults")
    
    def _save_settings(self) -> None:
        """Save settings to yaml file."""
        try:
            # Ensure directory exists
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
            self._logger.debug(f"Saving settings to {self._settings_file}")
            
            settings_dict = {
                'url': self._settings.url,
                'registration_token': self._settings.registration_token,
                'service_user': self._settings.service_user,
                'printer_id': self._settings.printer_id,
                'access_key': self._settings.access_key,
                'refresh_token': self._settings.refresh_token,
                'anon_key': self._settings.anon_key
            }
            with open(self._settings_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(settings_dict, f)
            self._logger.debug("Settings saved successfully")
        except Exception as e:
            self._logger.error(f"Failed to save settings: {str(e)}", exc_info=True)
    
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
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.anon_key}"
            }
            data = {
                "token": registration_token,
                "name": printer_name
            }

            # Log request details
            self._logger.debug(f"Registering printer with URL: {register_url}")
            self._logger.debug(f"Request headers: {headers}")
            self._logger.debug(f"Request data: {data}")

            # Make request
            response = requests.post(register_url, headers=headers, json=data)
            
            # Log response
            self._logger.debug(f"Registration response status: {response.status_code}")
            self._logger.debug(f"Registration response headers: {dict(response.headers)}")
            
            response_data = response.json()
            self._logger.debug(f"Registration response data: {response_data}")

            # Update settings
            self.update_settings(
                url=url,
                registration_token=registration_token,
                printer_id=str(response_data["printer_id"]),
                service_user=response_data["service_user"],
                access_key=response_data["access_token"],
                refresh_token=response_data["refresh_token"]
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
    def __init__(self, printer_name: str, logger=None, 
                 on_token_refresh: Optional[Callable[[str], None]] = None, 
                 plugin_data_folder: Optional[str] = None,
                 max_retry_delay: float = 15.0):
        if not printer_name:
            raise ValueError("Printer name is required")
        if not plugin_data_folder:
            raise ValueError("Plugin data folder is required")
            
        self._logger = logger
        if self._logger:
            self._logger.debug(f"Initializing AdditvClient for printer: {printer_name}")
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
        self._initialized = False
        
        # Check for environment variables
        env_url = os.environ.get("ADDITV_URL")
        env_token = os.environ.get("ADDITV_REGISTRATION_TOKEN")
        env_anon_key = os.environ.get("ADDITV_ANON_KEY")
        
        if env_url:
            self._settings_manager.update_settings(url=env_url)
        if env_token:
            self._settings_manager.update_settings(registration_token=env_token)
        if env_anon_key:
            self._settings_manager.update_settings(anon_key=env_anon_key)
        
        # Initialize connection or register if needed
        self._initialize()

    def _initialize(self) -> None:
        """Initialize the client, handling registration if needed."""
        settings = self._settings_manager.settings
        self._logger.debug(f"Initializing with settings - URL: {settings.url}, Has token: {bool(settings.registration_token)}, Has anon key: {bool(settings.anon_key)}, Has printer ID: {bool(settings.printer_id)}")
        
        # Case 1: We have URL and registration token but no printer ID
        if (settings.url and settings.registration_token and settings.anon_key and
            not settings.printer_id):
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
        elif settings.url and settings.access_key and settings.refresh_token:
            self._connect()
            
        # Case 3: Missing required settings
        else:
            self._logger.warning("Registration failed: Requires URL, registration token and anon key")

    @property
    def settings(self) -> ConnectionSettings:
        """Get the current connection settings."""
        return self._settings_manager.settings

    def _connect(self):
        """Establish connection to Additv backend"""
        try:
            self._logger.debug(f"Connecting to Supabase at URL: {self.settings.url}")
            self._supabase = create_client(self.settings.url, self.settings.anon_key)
            
            # Set up auth state change listener
            def handle_auth_change(event, session):
                if event == 'TOKEN_REFRESHED' and session:
                    # Update and persist both tokens
                    self._settings_manager.update_settings(
                        access_key=session.access_token,
                        refresh_token=session.refresh_token
                    )
                    self._logger.debug("Saved updated tokens from Supabase refresh")
                    # Call the token refresh callback if configured
                    if self._on_token_refresh:
                        self._on_token_refresh(session.access_token)
            
            self._supabase.auth.on_auth_state_change(handle_auth_change)
            
            # Initial session setup
            self._logger.debug("Setting up initial Supabase session")
            self._supabase.auth.set_session(
                access_token=self.settings.access_key,
                refresh_token=self.settings.refresh_token
            )
            
            # Verify connection
            currentUser = self._supabase.auth.get_user()
            if currentUser.user.id != self.settings.service_user:
                raise Exception(f"User ID mismatch. Expected: {self.settings.service_user}, Got: {currentUser.user.id}")
                
            self._logger.info("Successfully established connection to Additv backend")
            self._initialized = True
            
        except Exception as e:
            self._logger.error(f"Connection failed: {str(e)}")
            self._initialized = False

    def _process_queue(self):
        """Process operations from the queue"""
        self._logger.debug("Starting queue processor")
        while self._running:
            try:
                operation = self._queue.get(timeout=1.0)
                try:
                    self._logger.debug("Processing queued operation")
                    operation()  # Execute the queued operation
                    self._logger.debug("Operation completed successfully")
                except Exception as e:
                    self._logger.error(f"Operation failed: {str(e)}", exc_info=True)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                self._logger.error(f"Error processing queue: {str(e)}", exc_info=True)

    def publish_printer_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish a printer event to the Additv backend"""
        if self._running and self._supabase:
            self._logger.debug(f"Queueing printer event: {event_type} with data: {data}")
            self._queue.put(
                lambda: self._supabase.table("printer_events")
                    .insert({"event": event_type, "data": data, "source_timestamp": datetime.now(timezone.utc).isoformat()})
                    .execute()
            )
        else:
            self._logger.warning(f"Skipping event {event_type}: client not running or not connected")

    def publish_telemetry_event(self, telemetry: Dict) -> None:
        """Publish a single telemetry event to the queue for processing"""
        if self._running and self._supabase:
            self._logger.debug(f"Queueing telemetry event with data: {telemetry}")
            self._queue.put(
                lambda: self._supabase.table("printer_telemetry")
                    .insert({"data": telemetry, "source_timestamp": datetime.now(timezone.utc).isoformat()})
                    .execute()
            )
        else:
            self._logger.warning("Skipping telemetry event: client not running or not connected")

    def publish_job_progress(self, job_id: int, progress: float) -> None:
        """Publish job progress to the queue for processing"""
        if self._running and self._supabase:
            self._logger.debug(f"Queueing job progress update: job_id={job_id}, progress={progress}")
            self._queue.put(
                lambda: self._supabase.table("jobs")
                    .update({"progress": progress})
                    .eq("id", job_id)
                    .execute()
            )
        else:
            self._logger.warning("Skipping job progress update: client not running or not connected")

    def call_edge_function(self, function_name: str, params: Dict = None) -> Any:
        """Call an edge function and return the result"""
        if not self._running or not self._supabase:
            self._logger.warning(f"Skipping edge function {function_name}: client not running or not connected")
            return None
            
        try:
            # Use the stored access token for authorization
            if not self.settings.access_key:
                self._logger.error("No access token available for edge function call")
                return None
                
            # Call the edge function with authorization
            response = self._supabase.functions.invoke(
                function_name=function_name,
                invoke_options={
                    "body": params or {},
                    "headers": {
                        "Authorization": f"Bearer {self.settings.access_key}",
                        "Content-Type": "application/json"
                    }
                }
            )
            
            # Check for 204 No Content response
            if hasattr(response, 'status_code') and response.status_code == 204:
                self._logger.debug(f"Edge function returned 204 No Content")
                return None
                
            # Log the raw response for debugging
            self._logger.debug(f"Edge function raw response: {response}")
            
            # Parse response data
            try:
                if hasattr(response, 'json'):
                    data = response.json()
                elif hasattr(response, 'data'):
                    data = response.data
                else:
                    data = response
                
                # Handle bytes response
                if isinstance(data, bytes):
                    try:
                        data = json.loads(data.decode('utf-8'))
                    except json.JSONDecodeError as e:
                        self._logger.error(f"Failed to decode JSON response: {str(e)}")
                        return None
                    except UnicodeDecodeError as e:
                        self._logger.error(f"Failed to decode bytes response: {str(e)}")
                        return None
                    
                # Check for error response
                if isinstance(data, dict) and 'error' in data:
                    self._logger.error(f"Edge function returned error: {data['error']}")
                    if 'details' in data:
                        self._logger.debug(f"Error details: {data['details']}")
                    return None
                    
                return data
            except Exception as e:
                self._logger.error(f"Failed to parse edge function response: {str(e)}")
                return None
        except Exception as e:
            self._logger.error(f"Error calling edge function {function_name}: {str(e)}")
            return None

    def stop(self):
        """Stop the queue processor"""
        self._logger.info("Stopping AdditvClient")
        with self._lock:
            self._running = False
        if self._worker_thread.is_alive():
            self._logger.debug("Waiting for worker thread to complete...")
            self._worker_thread.join(timeout=5.0)
            self._logger.info("AdditvClient stopped")
    
    def is_initialized(self) -> bool:
        """Check if the client is fully initialized"""
        return self._initialized
