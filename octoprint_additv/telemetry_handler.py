import time
from typing import Optional, Dict, List
import logging

class TelemetryHandler:
    def __init__(self, additv_client, logger: Optional[logging.Logger] = None):
        self.additv_client = additv_client
        self._logger = logger or logging.getLogger(__name__)
        self._pending_temp = None
        self._pending_power = None
        self._telemetry_buffer: List[Dict] = []
        self._last_send_time = 0
        self._SEND_INTERVAL = 10.0  # seconds
        self._MAX_BUFFER_SIZE = 1000  # Safety limit

    def process_gcode_received_hook(self, line: str) -> None:
        first_char = line[0] if line else ''
        
        if first_char == 'T':  # Temperature
            if "T:" in line and "B:" in line:
                self._process_temperature(line)
        elif first_char == 'E':  # Power
            if "E0:" in line and "RPM" in line:
                self._process_power(line)

    def _process_temperature(self, line: str) -> None:
        # Store the temperature line
        self._pending_temp = line
        self._try_create_telemetry()

    def _process_power(self, line: str) -> None:
        # Store the power line
        self._pending_power = line
        self._try_create_telemetry()

    def _try_create_telemetry(self) -> None:
        # If we have both readings, create a telemetry record
        if self._pending_temp and self._pending_power:
            telemetry = self._parse_telemetry(self._pending_temp, self._pending_power)
            
            self._telemetry_buffer.append({
                "printer_id": self.additv_client.settings.printer_id,
                "telemetry": telemetry,
                "timestamp": time.time()
            })
            
            # Clear pending readings
            self._pending_temp = None
            self._pending_power = None
            
            # Check if it's time to send or if buffer is getting too large
            current_time = time.time()
            if (current_time - self._last_send_time >= self._SEND_INTERVAL or 
                len(self._telemetry_buffer) >= self._MAX_BUFFER_SIZE):
                self._send_buffered_telemetry()

    def _send_buffered_telemetry(self) -> None:
        if not self._telemetry_buffer:
            return
            
        try:
            # Send all buffered telemetry as a batch
            self.additv_client.publish_telemetry_batch(self._telemetry_buffer)
            
            # Clear buffer and update last send time
            self._telemetry_buffer = []
            self._last_send_time = time.time()
            
        except Exception:
            # If send fails, keep the buffer but enforce max size
            while len(self._telemetry_buffer) >= self._MAX_BUFFER_SIZE:
                self._telemetry_buffer.pop(0)  # Remove oldest entries if buffer is full

    def _parse_telemetry(self, temp_line: str, power_line: str) -> Dict:
        """Parse temperature and power lines into a single telemetry record"""
        # Example temp line: T:210.0 /210.0 B:60.0 /60.0
        # Example power line: E0:12.34 RPM:5678
        
        telemetry = {}
        
        # Parse temperature line
        if "T:" in temp_line:
            t_start = temp_line.find("T:") + 2
            t_end = temp_line.find(" ", t_start)
            if t_end != -1:
                telemetry["hotend_temp"] = float(temp_line[t_start:t_end])
        
        if "B:" in temp_line:
            b_start = temp_line.find("B:") + 2
            b_end = temp_line.find(" ", b_start)
            if b_end != -1:
                telemetry["bed_temp"] = float(temp_line[b_start:b_end])
        
        # Parse power line
        if "E0:" in power_line:
            e_start = power_line.find("E0:") + 3
            e_end = power_line.find(" ", e_start)
            if e_end != -1:
                telemetry["extruder_power"] = float(power_line[e_start:e_end])
        
        if "RPM:" in power_line:
            rpm_start = power_line.find("RPM:") + 4
            rpm_end = power_line.find(" ", rpm_start)
            if rpm_end == -1:  # If RPM is at the end of the line
                rpm_end = len(power_line)
            telemetry["fan_rpm"] = float(power_line[rpm_start:rpm_end])
        
        return telemetry
