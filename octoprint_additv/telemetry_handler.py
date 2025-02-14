import time
from typing import Optional, Dict, List, Union
import logging
from datetime import datetime, timezone

class TelemetryHandler:
    def __init__(self, additv_client, printer_profile_manager, logger: Optional[logging.Logger] = None):
        self.additv_client = additv_client
        self._logger = logger or logging.getLogger(__name__)
        self._pending_temp = None
        self._pending_power = None
        # Track last sent temperatures for filtering
        self._last_tool_temp = None
        self._last_bed_temp = None
        
        # Get printer model from profile
        printer_profile = printer_profile_manager.get_current_or_default()
        self.telemetry_type = printer_profile.get("model", "Unknown")
        
        # Initialize telemetry buffer
        self._telemetry_buffer = []
        self.BUFFER_SIZE = 10


    def process_gcode_received_hook(self, line: str) -> None:
        if not line:
            return
        if self.telemetry_type == "Virtual":
            self.process_virtual_telemetry(line)
        elif self.telemetry_type == "PrusaMK3":
            self.process_prusa_mk3_telemetry(line)

    def _should_send_telemetry(self, telemetry: Dict) -> bool:
        """
        Determine if telemetry should be sent based on temperature thresholds:
        - Always send if any temperature is above 30°C
        - Only send if temperature change > 0.3°C when below 30°C
        """
        tool_temp = telemetry.get('tool0_temp')
        bed_temp = telemetry.get('bed_temp')
        
        if self.telemetry_type == "Virtual": # Always send virtual printer telemetry
            return True

        # Always send if any temperature is above 30°C
        if (tool_temp and tool_temp > 30.0) or (bed_temp and bed_temp > 30.0):
            return True
            
        # Check for significant temperature changes (> 0.3°C)
        temp_changed = False
        if tool_temp and self._last_tool_temp is not None:
            temp_changed = abs(tool_temp - self._last_tool_temp) > 0.3
        if bed_temp and self._last_bed_temp is not None:
            temp_changed = temp_changed or abs(bed_temp - self._last_bed_temp) > 0.3
            
        return temp_changed

    def _scale_power(self, value: float) -> float:
        """Scale power value from 0-127 to 0-100%"""
        return round((value / 127) * 100, 2)

    def process_virtual_telemetry(self, line: str) -> None:
        """Process temperature line from Virtual printer
        
        Example line: T:21.30/ 0.00 B:21.30/ 0.00 @:64
        """
        if not ("T:" in line and "B:" in line):
            return

        telemetry = {}
        
        def extract_float(line: str, key: str, end_chars: List[str] = [" ", "/"]) -> Optional[float]:
            if key not in line:
                return None
            try:
                start = line.find(key) + len(key)
                end = len(line)
                for char in end_chars:
                    pos = line.find(char, start)
                    if pos != -1:
                        end = min(end, pos)
                value_str = line[start:end].strip()
                return float(value_str)
            except ValueError as e:
                self._logger.debug(f"Error parsing value for {key}: {e}")
                return None

        def extract_target_temp(line: str, key: str) -> Optional[float]:
            try:
                key_pos = line.find(key)
                if key_pos == -1:
                    return None
                slash_pos = line.find("/", key_pos)
                if slash_pos == -1:
                    return None
                value_str = line[slash_pos + 1:].strip()
                for end_char in [" ", "T", "B"]:
                    space_pos = value_str.find(end_char)
                    if space_pos != -1:
                        value_str = value_str[:space_pos]
                if value_str:  # Only try to convert if we have a non-empty string
                    return float(value_str)
                return None
            except Exception as e:
                self._logger.debug(f"Error parsing target temp for {key}: {e}")
                return None

        try:
            # Tool temperature
            if tool_temp := extract_float(line, "T:"):
                telemetry["tool0_temp"] = tool_temp
            
            # Tool target temperature
            tool_target = extract_target_temp(line, "T:")
            if tool_target is not None:
                telemetry["tool0_target_temp"] = tool_target
            
            # Bed temperature
            if bed_temp := extract_float(line, "B:"):
                telemetry["bed_temp"] = bed_temp
            
            # Bed target temperature
            bed_target = extract_target_temp(line, "B:")
            if bed_target is not None:
                telemetry["bed_target_temp"] = bed_target

            # Tool power
            if "@:" in line:
                tool0_power = extract_float(line, "@:")
                if tool0_power is not None:
                    telemetry["tool0_power"] = self._scale_power(tool0_power)

            if self._should_send_telemetry(telemetry):
                self._buffer_telemetry(telemetry)
                # Update last sent temperatures
                self._last_tool_temp = telemetry.get('tool0_temp')
                self._last_bed_temp = telemetry.get('bed_temp')

        except Exception as e:
            self._logger.debug(f"Error parsing virtual printer telemetry: {e}")

    def process_prusa_mk3_telemetry(self, line: str) -> None:
        """Process temperature and power lines from Prusa MK3 printer
        
        Example temp line: T:22.6 /0.0 B:23.7 /0.0 T0:22.6 /0.0 @:0 B@:0 P:0.0 A:30.6
        Example power line: E0:0 RPM PRN1:0 RPM E0@:0 PRN1@:0
        """
        first_char = line[0]
        if first_char == 'T' and "T:" in line and "B:" in line:
            self._pending_temp = line
            if self._pending_power:
                self._process_prusa_mk3_data()
        elif first_char == 'E' and "E0:" in line and "RPM" in line:
            self._pending_power = line
            if self._pending_temp:
                self._process_prusa_mk3_data()

    def _process_prusa_mk3_data(self) -> None:
        """Process collected temperature and power data for Prusa MK3"""
        if not self._pending_temp or not self._pending_power:
            return

        temp_line = self._pending_temp
        power_line = self._pending_power
        telemetry = {}
        
        def extract_float(line: str, key: str, end_chars: List[str] = [" "]) -> Optional[float]:
            """Extract float value from line with improved error handling"""
            if key not in line:
                return None
            try:
                start = line.find(key) + len(key)
                end = len(line)
                for char in end_chars:
                    pos = line.find(char, start)
                    if pos != -1:
                        end = min(end, pos)
                # Remove 'RPM' suffix if present
                value_str = line[start:end].replace('RPM', '').strip()
                return float(value_str)
            except ValueError as e:
                self._logger.debug(f"Error parsing value for {key}: {e}")
                return None

        def extract_target_temp(line: str, key: str) -> Optional[float]:
            """Extract target temperature value after the '/' character"""
            try:
                key_pos = line.find(key)
                if key_pos == -1:
                    return None
                slash_pos = line.find("/", key_pos)
                if slash_pos == -1:
                    return None
                value_str = line[slash_pos + 1:].strip()
                for end_char in [" ", "T", "B"]:
                    space_pos = value_str.find(end_char)
                    if space_pos != -1:
                        value_str = value_str[:space_pos]
                if value_str:  # Only try to convert if we have a non-empty string
                    return float(value_str)
                return None
            except Exception as e:
                self._logger.debug(f"Error parsing target temp for {key}: {e}")
                return None

        try:
            # Parse temperature line
            # Tool temperatures (try both T: and T0:)
            tool_temp = extract_float(temp_line, "T0:") or extract_float(temp_line, "T:")
            if tool_temp is not None:
                telemetry["tool0_temp"] = tool_temp
                
            # Tool target temperature
            tool_target = extract_target_temp(temp_line, "T0:") or extract_target_temp(temp_line, "T:")
            if tool_target is not None:
                telemetry["tool0_target_temp"] = tool_target
            
            # Bed temperature and target
            if bed_temp := extract_float(temp_line, "B:"):
                telemetry["bed_temp"] = bed_temp
            
            # Parse bed target temp separately to ensure it's captured
            bed_target = extract_target_temp(temp_line, "B:")
            if bed_target is not None:
                telemetry["bed_target_temp"] = bed_target

            # Tool and bed power values (scaled from 0-127 to 0-100%)
            if "@:" in temp_line:
                tool0_power = extract_float(temp_line, "@:")
                if tool0_power is not None:
                    telemetry["tool0_power"] = self._scale_power(tool0_power)
            
            if "B@:" in temp_line:
                bed_power = extract_float(temp_line, "B@:")
                if bed_power is not None:
                    telemetry["bed_power"] = self._scale_power(bed_power)

            # Ambient temperature
            if ambient_temp := extract_float(temp_line, "A:"):
                telemetry["ambient_temp"] = ambient_temp

            # Parse fan speeds (removing RPM suffix)
            if "E0:" in power_line:
                heatsink_fan = extract_float(power_line, "E0:")
                if heatsink_fan is not None:
                    telemetry["tool0_heatsink_fan_rpm"] = round(heatsink_fan, 2)
            
            if "PRN1:" in power_line:
                part_fan = extract_float(power_line, "PRN1:")
                if part_fan is not None:
                    telemetry["tool0_part_fan_rpm"] = round(part_fan, 2)

            if self._should_send_telemetry(telemetry):
                self._buffer_telemetry(telemetry)
                # Update last sent temperatures
                self._last_tool_temp = telemetry.get('tool0_temp')
                self._last_bed_temp = telemetry.get('bed_temp')

        except Exception as e:
            self._logger.debug(f"Error parsing Prusa MK3 telemetry: {e}")
        finally:
            self._pending_temp = None
            self._pending_power = None
            
    def _buffer_telemetry(self, telemetry: Dict) -> None:
        """Add telemetry to buffer and send if buffer is full"""
        timestamped_telemetry = {
            "data": telemetry,
            "source_timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._telemetry_buffer.append(timestamped_telemetry)
        self._logger.debug(f"Added telemetry to buffer. Buffer size: {len(self._telemetry_buffer)}")
        
        if len(self._telemetry_buffer) >= self.BUFFER_SIZE:
            self._send_buffered_telemetry()
    
    def _send_buffered_telemetry(self) -> None:
        """Send buffered telemetry and clear buffer"""
        if not self._telemetry_buffer:
            return
            
        try:
            self.additv_client.publish_telemetry_batch(self._telemetry_buffer)
            self._logger.debug(f"Published batch of {len(self._telemetry_buffer)} telemetry events")
        except Exception as e:
            self._logger.error(f"Failed to send telemetry batch: {e}")
        finally:
            self._telemetry_buffer = []
            
    def on_shutdown(self) -> None:
        """Flush any remaining telemetry on shutdown"""
        if self._telemetry_buffer:
            self._send_buffered_telemetry()
