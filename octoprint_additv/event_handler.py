import logging
from typing import Optional, Dict, Any

# Printer event type constants matching database enum values
PRINTER_EVENT_PRINTSTARTED = "Job_Started"
PRINTER_EVENT_PRINTDONE = "Job_Complete"
PRINTER_EVENT_PRINTFAILED = "Job_Failed"
PRINTER_EVENT_PRINTPAUSED = "Job_Paused"


class EventHandler:
    def __init__(self, supabase_client, logger=None):
        self._supabase = supabase_client
        self._logger = logger or logging.getLogger(__name__)

    def _get_db(self):
        """Get the database client, ensuring we have a valid session"""
        try:
            session = self._supabase.auth.get_session()
            if not session:
                self._logger.error("No valid Supabase session")
                return None
            return self._supabase
        except Exception as e:
            self._logger.error(f"Error getting Supabase session: {str(e)}")
            return None

    def map_event(self, event: str, payload: Dict[str, Any]) -> Optional[str]:
        """Map OctoPrint events to printer_event_type enum values"""
        if event == "ZChange":
            return None

        match event:
            case "PrintStarted":
                return PRINTER_EVENT_PRINTSTARTED

            case "PrintDone":
                return PRINTER_EVENT_PRINTDONE

            case "PrintFailed" | "PrintCancelled":
                return PRINTER_EVENT_PRINTFAILED

            case "PrintPaused":
                return PRINTER_EVENT_PRINTPAUSED

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
            # printer_id is automatically set by the database trigger
            db = self._get_db()
            if not db:
                self._logger.error("Failed to get valid database connection")
                return
            
            db.table("printer_events").insert({"event": event_type}).execute()

        except Exception as e:
            self._logger.error(f"Error inserting event {event_type}: {str(e)}")
