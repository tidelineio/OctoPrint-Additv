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
            
            self._additv.insert("printer_events", {"event": event_type, "data": data})

        except Exception as e:
            self._logger.error(f"Error inserting event {event_type}: {str(e)}")
