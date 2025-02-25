import octoprint.plugin
from .event_handler import EventHandler
from .additv_client import AdditvClient
from .telemetry_handler import TelemetryHandler
from .job_handler import JobHandler
from .printer_commands import PrinterCommands


class AdditivPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.ProgressPlugin,
):

    def __init__(self):
        super().__init__()
        self.additv_client = None
        self.event_handler = None
        self.telemetry_handler = None
        self.job_handler = None
        self.printer_commands = None
        self._on_ready = None
        self._on_not_ready = None

    def gcode_sent_hook(self, comm, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
        """Process sent GCODE lines through job handler for filament tracking"""
        try:
            if self.job_handler:
                self.job_handler.process_gcode_line(cmd)
        except Exception:
            # Logging is too expensive on gcode hooks
            pass
        return cmd

    def gcode_received_hook(self, comm, line, *args, **kwargs):
        """Process received GCODE lines through event and telemetry handlers"""
        try:
            if self.event_handler:
                self.event_handler.process_gcode_received_hook(line)
            
            if self.telemetry_handler:
                self.telemetry_handler.process_gcode_received_hook(line)
        except Exception:
            # Logging is too expensive on gcode_received_hook
            pass
        
        return line

    def on_startup(self, host, port):
        """Initialize the Additv client and event handler."""
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
            
            # Ensure the client is fully initialized
            if not self.additv_client.is_initialized():
                self._logger.error("Additv client failed to initialize completely")
                self.additv_client = None
                return
            
            # Initialize printer communication components first
            self.printer_commands = PrinterCommands(self._printer, printer_name, self._logger)
            
            # Initialize handlers
            self.job_handler = JobHandler(self)
            self.event_handler = EventHandler(self.additv_client, self.job_handler, self._logger)
            self.telemetry_handler = TelemetryHandler(self.additv_client, self._printer_profile_manager, self._logger)
            
            # Set up action handlers
            self._on_ready = lambda: (
                self.printer_commands.send_ready_state(1),
                self.job_handler.start_next_job()
            )
            self._on_not_ready = lambda: self.printer_commands.send_ready_state(0)
            
            self._logger.info("Additv handlers initialized")
            self._check_printer_startup_state()
        except Exception as e:
            self._logger.error(f"Error during startup: {str(e)}")
            # Reset all handlers and client if initialization fails
            self.additv_client = None
            self.event_handler = None
            self.telemetry_handler = None
            self.job_handler = None
            self.printer_commands = None
            self._on_ready = None
            self._on_not_ready = None
        
        if not self.additv_client or not self.additv_client.is_initialized():
            self._logger.warning("Additv client not initialized. Handlers will not be set up.")

    def _check_printer_startup_state(self):
        """Check printer state during startup and send appropriate connection event."""
        state_id = self._printer.get_state_id()
        self._logger.debug(f"Checking printer state during startup: {state_id}")
        
        if state_id == "OPERATIONAL":
            self._logger.debug("Printer is operational, sending Connected event")
            self.event_handler.handle_event("Connected", {})
        else:
            self._logger.debug(f"Printer is not operational ({state_id}), sending Disconnected event")
            self.event_handler.handle_event("Disconnected", {})
                    
    def on_event(self, event, payload):
        """Handle OctoPrint events by passing them to our event handler"""
        if self.event_handler:
            self.event_handler.handle_event(event, payload)

    def get_settings_defaults(self):
        """Define default settings for the plugin."""
        return dict()

    def on_after_startup(self):
        """Start background tasks after plugin startup"""
        if self.printer_commands:
            self.printer_commands.start_ping_loop()

    def on_shutdown(self):
        """Clean up resources on shutdown"""
        if self.printer_commands:
            self.printer_commands.stop_ping_loop()
        if self.telemetry_handler:
            self.telemetry_handler.on_shutdown()
        if self.additv_client:
            self.additv_client.stop()
            self._logger.info("Stopped Additv client queue processor")

    def on_print_progress(self, storage, path, progress):
        """Handle print progress updates"""
        if self.job_handler:
            self.job_handler.report_job_progress(progress=progress)

    def action_hook(self, comm, line, action, *args, **kwargs):
        """Handle action commands from Printer LCD"""
        if action is None:
            return None

        self._logger.debug(f"Action received: {action}")

        if ";" in action:
            action = action.split(";")[0].strip()

        if action == "ready" and self._on_ready:
            self._logger.debug("Action Received from Printer: Ready")
            self.printer_commands.send_ready_state(1), #Send not-ready state to the printer
            if self._printer.is_ready():
                self.job_handler.start_next_job()
        elif action == "not_ready" and self._on_not_ready:
            self._logger.debug("Action Received from Printer: Not Ready")
            self._on_not_ready()

        return None


__plugin_name__ = "Additv Plugin"
__plugin_pythoncompat__ = ">=3.11,<4"
__plugin_implementation__ = AdditivPlugin()


def __plugin_load__():
    global __plugin_implementation__
    plugin = __plugin_implementation__
    
    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.gcode.received": plugin.gcode_received_hook,
        "octoprint.comm.protocol.gcode.sent": plugin.gcode_sent_hook,
        "octoprint.comm.protocol.action": plugin.action_hook
    }
