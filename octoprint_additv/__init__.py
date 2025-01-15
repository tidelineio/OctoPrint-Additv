# coding=utf-8
from __future__ import annotations

import octoprint.plugin

class AdditivPlugin(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.SettingsPlugin):
    
    def get_settings_defaults(self):
        return dict(
            url="https://example.com"
        )
    
    def on_after_startup(self):
        self._logger.info(f"Hello World! (more: {self._settings.get(['url'])})")

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
