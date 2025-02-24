class PrinterActionHandler:
    def __init__(self, logger=None):
        self._logger = logger
        self._on_ready = None
        self._on_not_ready = None
    
    def register_handlers(self, on_ready=None, on_not_ready=None):
        """Register callback handlers for printer actions"""
        self._on_ready = on_ready
        self._on_not_ready = on_not_ready
    
    def handle_action(self, comm, line, action, *args, **kwargs):
        """Handle action commands from Printer LCD"""
        if self._logger:
            self._logger.debug(f"Action received: {action}")

        if ";" in action:
            action = action.split(";")[0].strip()

        if action == "ready" and self._on_ready:
            if self._logger:
                self._logger.debug("Action Received from Printer: Ready")
            self._on_ready()
        elif action == "not_ready" and self._on_not_ready:
            if self._logger:
                self._logger.debug("Action Received from Printer: Not Ready")
            self._on_not_ready()
