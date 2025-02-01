import time
from typing import Optional, Dict, List, Union
import logging

class TelemetryHandler:
    def __init__(self, additv_client, logger: Optional[logging.Logger] = None):
        self.additv_client = additv_client
        self._logger = logger or logging.getLogger(__name__)
        self._pending_temp = None
        self._pending_power = None

    def process_gcode_received_hook(self, line: str) -> None:
        if not line:
            return
            
        first_char = line[0]
        self._logger.debug(f"Processing gcode line: {line}")
        
        if first_char == 'T':  # Temperature
            if "T:" in line and "B:" in line:
                self._process_temperature(line)
        elif first_char == 'E':  # Power/Fan
            if "E0:" in line and "RPM" in line:
                self._process_power(line)

    def _process_temperature(self, line: str) -> None:
        self._logger.debug(f"Processing temperature line: {line}")
        self._pending_temp = line
        self._try_create_telemetry()

    def _process_power(self, line: str) -> None:
        self._logger.debug(f"Processing power/fan line: {line}")
        self._pending_power = line
        self._try_create_telemetry()

    def _try_create_telemetry(self) -> None:
        if self._pending_temp and self._pending_power:
            try:
                telemetry = self._parse_telemetry(self._pending_temp, self._pending_power)
                self.additv_client.publish_telemetry_event({"telemetry": telemetry})
                self._logger.debug(f"Published telemetry event: {telemetry}")
            except Exception as e:
                self._logger.error(f"Error creating telemetry event: {e}")
            finally:
                self._pending_temp = None
                self._pending_power = None

    def _scale_power(self, value: float) -> float:
        """Scale power value from 0-127 to 0-100%"""
        return round((value / 127) * 100, 2)

    def _parse_telemetry(self, temp_line: str, power_line: str) -> Dict:
        """Parse temperature and power lines into a single telemetry record
        
        Example temp line: T:22.6 /0.0 B:23.7 /0.0 T0:22.6 /0.0 @:0 B@:0 P:0.0 A:30.6
        Example power line: E0:0 RPM PRN1:0 RPM E0@:0 PRN1@:0
        """
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
                self._logger.error(f"Error parsing value for {key}: {e}")
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
                return extract_float(line[slash_pos:], "/", [" ", "T", "B"])
            except Exception as e:
                self._logger.error(f"Error parsing target temp for {key}: {e}")
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
                self._logger.debug(f"Parsed tool target temp: {tool_target}")
            
            # Bed temperature and target
            if bed_temp := extract_float(temp_line, "B:"):
                telemetry["bed_temp"] = bed_temp
                self._logger.debug(f"Parsed bed temp: {bed_temp}")
            
            # Parse bed target temp separately to ensure it's captured
            bed_target = extract_target_temp(temp_line, "B:")
            if bed_target is not None:
                telemetry["bed_target_temp"] = bed_target
                self._logger.debug(f"Parsed bed target temp: {bed_target}")

            # Tool and bed power values (scaled from 0-127 to 0-100%)
            if "@:" in temp_line:
                tool0_power = extract_float(temp_line, "@:")
                if tool0_power is not None:
                    telemetry["tool0_power"] = self._scale_power(tool0_power)
                    self._logger.debug(f"Parsed tool power: {tool0_power} -> {telemetry['tool0_power']}%")
            
            if "B@:" in temp_line:
                bed_power = extract_float(temp_line, "B@:")
                if bed_power is not None:
                    telemetry["bed_power"] = self._scale_power(bed_power)
                    self._logger.debug(f"Parsed bed power: {bed_power} -> {telemetry['bed_power']}%")

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

        except Exception as e:
            self._logger.error(f"Error parsing telemetry: {e}")
            raise

        # Remove None values
        return {k: v for k, v in telemetry.items() if v is not None}
