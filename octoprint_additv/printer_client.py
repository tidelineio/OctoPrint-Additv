class PrinterClient:
    def __init__(self, printer, printer_name, job_handler=None, logger=None):
        """Initialize the PrinterCommunicator with a printer instance and name.
        
        Args:
            printer: The OctoPrint printer instance
            printer_name: The name of the printer for identification
            job_handler: The job handler instance for processing jobs
            logger: The logger instance for debug output
        """
        self._printer = printer
        self._printer_name = printer_name
        self._job_handler = job_handler
        self._logger = logger

    def send_ping(self):
        """Send a ping to the printer to let it know we're connected.
        Uses the first two letters of the printer name."""
        first_two_letters = self._printer_name[:2]
        self._printer.commands(f'M79 S"{first_two_letters}"')

    def send_ready_state(self, state, send_lcd_message=True):
        """Acknowledge the Ready / Not Ready state to the Printer.
        
        Args:
            state: 1 for Ready, 0 for Not Ready
            send_lcd_message: Whether to send an LCD message when ready (default: True)
        """
        if state == 1 and send_lcd_message:
            self.send_lcd_message("Fetching next Job...")
        self._printer.commands(f"M72 S{state}")

    def send_lcd_message(self, message):
        """Send a message to the printer's LCD display.
        
        Args:
            message: The message to display on the LCD
        """
        self._printer.commands(f"M117 {message}")

    def action_handler(self, comm, line, action, *args, **kwargs):
        """Handle action commands from Printer LCD.
        
        Args:
            comm: The communication instance
            line: The received line
            action: The action command
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments
        """
        if self._logger:
            self._logger.debug(f"action_handler - Action received: {action}")

        if ";" in action:
            action = action.split(";")[0]
            action = action.strip()

        if action == "ready":
            if self._logger:
                self._logger.debug("action_handler - Action Received from Printer: Ready")
            self.send_ready_state(1)

            # Go find the next job and start it
            # Test this in the Virtual Printer with this gcode
            # !!DEBUG:action_custom ready
            if self._job_handler:
                self._job_handler.start_next_job()

        elif action == "not_ready":
            if self._logger:
                self._logger.debug("action_handler - Action Received from Printer: Not Ready")
            self.send_ready_state(0)
