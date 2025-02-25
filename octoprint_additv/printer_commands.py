import octoprint.util

class PrinterCommands:
    def __init__(self, printer, printer_name, logger=None):
        self._printer = printer
        self._printer_name = printer_name
        self._logger = logger
        self._ping_loop = None

    def send_lcd_message(self, message):
        """Send a message to the printer's LCD display"""
        self._printer.commands(f"M117 {message}")
    
    def send_ready_state(self, state):
        """Acknowledge Ready/Not Ready state to printer"""
        self._printer.commands(f"M72 S{state}")
    
    def send_ping(self):
        """Send a ping using first two letters of printer name"""
        first_two_letters = self._printer_name[:2]
        self._printer.commands(f'M79 S"{first_two_letters}"')

    def start_ping_loop(self):
        """Start the ping loop to keep printer connection alive"""
        if not self._ping_loop:
            interval = 20
            self._ping_loop = octoprint.util.RepeatedTimer(
                interval, 
                self.send_ping,
                run_first=True
            )
            self._ping_loop.start()
            if self._logger:
                self._logger.debug("Started printer ping loop")

    def stop_ping_loop(self):
        """Stop the ping loop"""
        if self._ping_loop:
            self._ping_loop.cancel()
            self._ping_loop = None
            if self._logger:
                self._logger.debug("Stopped printer ping loop")
