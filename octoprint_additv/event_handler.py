import logging
from typing import Optional, Dict, Any

class EventHandler:
    # Events that will be handled and stored
    EVENTS_TO_HANDLE = {
        "Startup",
        "Shutdown",
        "Connected",
        "Disconnected",
        "Error",
        "PrinterStateChanged",
        "PrintStarted",
        "PrintFailed",
        "PrintDone",
        "PrintCancelled",
        "PrintPaused",
        "PrintResumed",
        "PrinterReset",
        "FirmwareData",
        # GCODE-specific events
        "FilamentRunout",
        "ThermalError",
        "XCrash",
        "YCrash",
        "ZCrash",
        "HotendFanError",
        "PartFanError",
    }

    def __init__(self, additv_client, logger=None):
        """
        Initialize the event handler
        
        Args:
            additv_client: The Additv client instance
            logger: Optional logger instance
        """
        self._additv = additv_client
        self._logger = logger or logging.getLogger(__name__)

    def handle_event(self, event: str, payload: Dict[str, Any]) -> None:
        """Handle an OctoPrint event by inserting it into the database if it's in the events_to_handle set"""
        try:
            if event in self.EVENTS_TO_HANDLE:
                # We should eventually filter the PrinterStateChanged events to only record the ones that are relevant
                # as this event duplicates some other events and we only care about the state of the USB connection
                # Logging all PrinterStateChanged events for now
                self._logger.debug(f"Recording event {event}")
                self.insert_event(event, payload)

        except Exception as e:
            self._logger.error(f"Error handling event {event}: {str(e)}")

    def insert_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Insert an event into the printer_events table"""
        try:
            if not self._additv:
                self._logger.error("No valid Additv connection")
                return
            
            self._additv.publish_printer_event(event_type, data)

        except Exception as e:
            self._logger.error(f"Error publishing event {event_type}: {str(e)}")

    def process_gcode_received_hook(self, line: str) -> None:
        """Process GCODE lines for specific events"""
        # Quick length check first
        if len(line) < 4:  # Minimum length for any of our patterns to quickly fail out if not met
            return
            
        # Check for crash events first (most critical)
        if "CRASH_DETECTED" in line:
            if "X" in line:
                self.handle_event("XCrash", {"line": line})
            elif "Y" in line:
                self.handle_event("YCrash", {"line": line})
            elif "Z" in line:
                self.handle_event("ZCrash", {"line": line})
                
        # Check for thermal error
        elif "TM: error" in line:
            self.handle_event("ThermalError", {"line": line})
            
        # Check for filament runout
        elif "Enqueing to the front:" in line and "M600" in line:
            self.handle_event("FilamentRunout", {"line": line})
            
        # Check for fan errors
        elif "fan speed is lower than expected" in line:
            if "Hotend" in line:
                self.handle_event("HotendFanError", {"line": line})
            elif "Print" in line:
                self.handle_event("PartFanError", {"line": line})
