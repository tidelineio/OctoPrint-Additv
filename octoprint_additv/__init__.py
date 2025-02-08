import octoprint.plugin
from .event_handler import EventHandler
from .additv_client import AdditvClient
from .telemetry_handler import TelemetryHandler
from .filament_tracker import FilamentTracker


class AdditivPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SettingsPlugin,
):
    def gcode_received_hook(self, comm, line, *args, **kwargs):
        """Process received GCODE lines through all handlers"""
        try:
            if self.filament_tracker:
                self.filament_tracker.process_gcode_received_hook(line)
            
            if self.event_handler:
                self.event_handler.process_gcode_received_hook(line)
            
            if self.telemetry_handler:
                self.telemetry_handler.process_gcode_received_hook(line)
            
        except Exception:
            # Logging is too expensive on gcode_received_hook
            pass
        
        return line
            
    def __init__(self):
        super().__init__()
        self.additv_client = None
        self.event_handler = None
        self.telemetry_handler = None
        self.filament_tracker = None
      
        

    def on_startup(self, host, port):
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

        # If client initialized successfully, set up handlers
        if self.additv_client and self.additv_client._supabase:
            try:
                self.event_handler = EventHandler(self.additv_client, self._logger)
                self.telemetry_handler = TelemetryHandler(self.additv_client, self._printer_profile_manager, self._logger)
                self.filament_tracker = FilamentTracker(self._logger)
                self._logger.info("Additv handlers initialized")
                
                # Check printer state and send appropriate event
                state_id = self._printer.get_state_id()
                self._logger.debug(f"Checking printer state during startup: {state_id}")
                if state_id == "OPERATIONAL":
                    self._logger.debug("Printer is operational, sending Connected event")
                    self.event_handler.handle_event("Connected", {})
                else:
                    self._logger.debug(f"Printer is not operational ({state_id}), sending Disconnected event")
                    self.event_handler.handle_event("Disconnected", {})
                    
            except Exception as e:
                self._logger.error(f"Failed to initialize handlers: {str(e)}")

    def on_event(self, event, payload):
        """Handle OctoPrint events by passing them to our event handler"""
        if self.event_handler:
            self.event_handler.handle_event(event, payload)

    def get_settings_defaults(self):
        """Define default settings for the plugin."""
        return dict()

    def on_shutdown(self):
        """Clean up resources on shutdown"""
        if self.additv_client:
            self.additv_client.stop()
            self._logger.info("Stopped Additv client queue processor")


__plugin_name__ = "Additv Plugin"
__plugin_pythoncompat__ = ">=3.11,<4"
__plugin_implementation__ = AdditivPlugin()


def __plugin_load__():
    global __plugin_implementation__
    plugin = __plugin_implementation__
    
    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.received": plugin.gcode_received_hook,
    }
