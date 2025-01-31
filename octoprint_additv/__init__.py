import octoprint.plugin
from .event_handler import EventHandler
from .additv_client import AdditvClient


class AdditivPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SettingsPlugin,
):    
    def __init__(self):
        super().__init__()
        self.additv_client = None
        self.event_handler = None
      
    def on_after_startup(self):
        """Initialize the Additv client and event handler."""
        # First try to create and initialize the Additv client
        try:
            printer_name = self._settings.global_get(["appearance", "name"])
            if not printer_name:
                self._logger.error("Printer name not configured in OctoPrint settings")
                return
                
            plugin_data_folder = self.get_plugin_data_folder()
            self.additv_client = AdditvClient(
                printer_name=printer_name,
                logger=self._logger,
                plugin_data_folder=plugin_data_folder
            )
        except Exception as e:
            self._logger.error(f"Failed to initialize Additv client: {str(e)}")
            return

        # If client initialized and connected successfully, set up event handler
        if self.additv_client._client:
            try:
                self.event_handler = EventHandler(self.additv_client, self._logger)
                self._logger.info("Additv event handler initialized")
            except Exception as e:
                self._logger.error(f"Failed to initialize event handler: {str(e)}")

    def on_event(self, event, payload):
        """Handle OctoPrint events by passing them to our event handler"""
        if self.event_handler:
            self.event_handler.handle_event(event, payload)

    def get_settings_defaults(self):
        """Define default settings for the plugin."""
        return dict()

__plugin_name__ = "Additv Plugin"
__plugin_pythoncompat__ = ">=3.11,<4"
__plugin_implementation__ = AdditivPlugin()
