# coding=utf-8
from __future__ import annotations

import octoprint.plugin
import requests
import json
from supabase import create_client

class AdditivPlugin(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.SettingsPlugin):
    
    def __init__(self):
        super().__init__()
        self.url = None
        self.anon_key = None
        self.registration_token = None
        self.service_user = None
        self.printer_id = None
        self.access_key = None
        self.refresh_token = None
        self.supabase = None

    def get_settings_defaults(self):
        return dict(
            url="http://192.168.42.102:54321",
            anon_key="",
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

            # Store response data in settings
            self._settings.set(["printer_id"], response_data["printer_id"])
            self._settings.set(["service_user"], response_data["service_user"])
            self._settings.set(["access_key"], response_data["access_token"])
            self._settings.set(["refresh_token"], response_data["refresh_token"])
            self._settings.set(["anon_key"], response_data["anon_key"])
            self._settings.save()

            # Update instance variables
            self.printer_id = str(response_data["printer_id"])
            self.service_user = response_data["service_user"]
            self.access_key = response_data["access_token"]
            self.refresh_token = response_data["refresh_token"]
            self.anon_key = response_data["anon_key"]

            self._logger.warning("Successfully registered printer with Additv")
            return True
        except Exception as e:
            self._logger.error(f"Failed to register printer: {str(e)}")
            return False
      
    def on_after_startup(self):
        try:
            # Initialize settings
            self.url = self._settings.get(["url"])
            self.registration_token = self._settings.get(["registration_token"])
            self.service_user = self._settings.get(["service_user"])
            self.printer_id = self._settings.get(["printer_id"])
            self.access_key = self._settings.get(["access_key"])
            self.refresh_token = self._settings.get(["refresh_token"])
            self.anon_key = self._settings.get(["anon_key"])

            if self.service_user is None and self.printer_id is None:
                self._logger.warning("Printer not registered. Attempting to register printer to Additv.")
                self.register_printer()

            if self.url and self.access_key:
                self.supabase = create_client(self.url, self.anon_key)
                self.supabase.auth.set_session(self.access_key, self.refresh_token)
                session = self.supabase.auth.get_session()
                self._logger.info("Successfully connected to Supabase")
            else:
                self._logger.warning("Supabase URL or anon key not configured")
        except Exception as e:
            self._logger.error(f"Failed to connect to Supabase: {str(e)}")

    def get_template_configs(self):
        return [
            dict(type="navbar", custom_bindings=False),
            dict(type="settings", custom_bindings=False)
        ]

    ##~~ Softwareupdate hook
    def get_update_information(self):
        return {
            "additv": {
                "displayName": "Additv Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "you",
                "repo": "OctoPrint-Additv",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/you/OctoPrint-Additv/archive/{target_version}.zip",
            }
        }

__plugin_name__ = "Additv Plugin"
__plugin_pythoncompat__ = ">=3.7,<4" # Python 3.7+ required
__plugin_implementation__ = AdditivPlugin()
