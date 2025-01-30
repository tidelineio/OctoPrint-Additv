# coding=utf-8
from __future__ import annotations

import octoprint.plugin
import requests
import os
import yaml
from pathlib import Path
from supabase import create_client
from .event_handler import EventHandler


class AdditivPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.EventHandlerPlugin,
):    
    def __init__(self):
        super().__init__()
        self.url = None
        self.registration_token = None
        self.service_user = None
        self.printer_id = None
        self.access_key = None
        self.refresh_token = None
        self.supabase = None
        self._settings_file = None
        self.event_handler = None

    def initialize(self):
        self._settings_file = Path(self.get_plugin_data_folder()) / "additv.yaml"
        self._load_settings()

    def _load_settings(self):
        """Load settings from additv.yaml file"""
        if self._settings_file.exists():
            try:
                with open(self._settings_file, 'r') as f:
                    settings = yaml.safe_load(f)
                    if settings:
                        for key, value in settings.items():
                            if hasattr(self, key):
                                setattr(self, key, value)
            except Exception as e:
                self._logger.error(f"Failed to load settings: {str(e)}")

    def _save_settings(self):
        """Save settings to additv.yaml file"""
        try:
            settings = {
                'url': self.url,
                'registration_token': self.registration_token,
                'service_user': self.service_user,
                'printer_id': self.printer_id,
                'access_key': self.access_key,
                'refresh_token': self.refresh_token
            }
            
            with open(self._settings_file, 'w') as f:
                yaml.safe_dump(settings, f)
        except Exception as e:
            self._logger.error(f"Failed to save settings: {str(e)}")

    def get_settings_defaults(self):
        return dict(
            url="",
            registration_token="",
            service_user="",
            printer_id="",
            access_key="",
            refresh_token=""
        )

    def register_printer(self):
        try:
            # Get printer name from OctoPrint settings
            printer_name = self._settings.global_get(["appearance", "name"])
            if not printer_name:
                self._logger.error("Printer name not configured. Please set a printer name in OctoPrint settings.")
                return False

            # Prepare request
            url = f"{self.url}/functions/v1/register-printer"
            headers = {"Content-Type": "application/json"}
            data = {
                "token": self.registration_token,
                "name": printer_name
            }

            # Make request
            response = requests.post(url, headers=headers, json=data)
            response_data = response.json()

            # Update instance variables and save to file
            self.printer_id = str(response_data["printer_id"])
            self.service_user = response_data["service_user"]
            self.access_key = response_data["access_token"]
            self.refresh_token = response_data["refresh_token"]
            # Save settings to file
            self._save_settings()
            
            self._logger.info("Successfully registered printer with Additv")
            return True
        except Exception as e:
            self._logger.error(f"Failed to register printer: {str(e)}")
            return False
      
    def on_after_startup(self):
        try:
            # Initialize the settings file and load settings
            self.initialize()
            
            # Override with environment variables if present
            self.url = os.environ.get("ADDITV_URL", self.url or "")
            self.registration_token = os.environ.get("ADDITV_REGISTRATION_TOKEN", self.registration_token or "")

            if not self.service_user and not self.printer_id:
                self._logger.warning("Printer not registered. Attempting to register printer to Additv.")
                self.register_printer()

            if self.url and self.access_key:
                self.supabase = create_client(self.url, self.access_key)
                self.supabase.auth.refresh_session(self.refresh_token)
                self.event_handler = EventHandler(self.supabase, self._logger)
                self._logger.info("Successfully connected to Additv")
            else:
                self._logger.warning("Additv URL or access key not configured")
        except Exception as e:
            self._logger.error(f"Failed to connect to Additv: {str(e)}")

    def on_event(self, event, payload):
        """Handle OctoPrint events by passing them to our event handler"""
        if event == "ZChange":
            return None
        if self.event_handler:
            self.event_handler.handle_event(event, payload)

__plugin_name__ = "Additv Plugin"
__plugin_pythoncompat__ = ">=3.7,<4" # Python 3.7+ required
__plugin_implementation__ = AdditivPlugin()
