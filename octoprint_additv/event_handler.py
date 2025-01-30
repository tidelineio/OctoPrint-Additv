import logging
from typing import Optional, Dict, Any

# Printer event type constants matching database enum values
PRINTER_EVENT_JOB_STARTED = "Job_Started"
PRINTER_EVENT_JOB_COMPLETE = "Job_Complete"
PRINTER_EVENT_JOB_FAILED = "Job_Failed"
PRINTER_EVENT_JOB_PAUSED = "Job_Paused"


class EventHandler:
    def __init__(self, additv_client, logger=None):
        self._additv = additv_client
        self._logger = logger or logging.getLogger(__name__)

    def map_event(self, event: str, payload: Dict[str, Any]) -> Optional[str]:
        """Map OctoPrint events to printer_event_type enum values"""
        match event:
            case "PrintStarted":
                return PRINTER_EVENT_JOB_STARTED

            case "PrintDone":
                return PRINTER_EVENT_JOB_COMPLETE

            case "PrintFailed" | "PrintCancelled":
                return PRINTER_EVENT_JOB_FAILED

            case "PrintPaused":
                return PRINTER_EVENT_JOB_PAUSED

            case _:
                return None

    def handle_event(self, event: str, payload: Dict[str, Any]) -> None:
        """Handle an OctoPrint event by mapping it and inserting into the database"""
        try:
            if event != "ZChange":
                self._logger.debug(f"Handling event {event}")
                mapped_event = self.map_event(event, payload)
                if mapped_event:
                    self.insert_event(mapped_event, payload)

        except Exception as e:
            self._logger.error(f"Error handling event {event}: {str(e)}")

    def insert_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Insert an event into the printer_events table"""
        try:
            if not self._additv:
                self._logger.error("No valid Additv connection")
                return
            
            self._additv.insert("printer_events", {"event": event_type})

        except Exception as e:
            self._logger.error(f"Error inserting event {event_type}: {str(e)}")
