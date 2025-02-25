from io import BytesIO
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
import requests
import zipfile
import hashlib
from octoprint.util import RepeatedTimer
from .filament_tracker import FilamentTracker

@dataclass
class Job:
    job_id: int
    gcode_id: int
    gcode_url_compressed: str
    gcode_filename: str
    file_hash: str
    estimated_print_time_seconds: int = 0
    octoprint_filename: str = None

    @classmethod
    def from_dict(cls, data: dict, logger) -> Optional['Job']:
        """
        Create a Job instance from a dictionary, with validation.
        
        Args:
            data: Dictionary containing job data
            logger: Logger instance for error reporting
            
        Returns:
            Job instance if valid, None otherwise
        """
        # Validate data is a dictionary
        if not isinstance(data, dict):
            logger.error("Invalid job data format: expected dict, got %s", type(data).__name__)
            return None
            
        # Validate required fields
        required_fields = {'job_id', 'gcode_id', 'gcode_url_compressed', 'gcode_filename', 'file_hash'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            logger.error("Missing required job data fields: %s", ', '.join(missing_fields))
            return None
            
        # Log all received fields for debugging
        logger.debug("Received job data fields: %s", ', '.join(data.keys()))
        logger.info("Retrieved job %s with gcode %s", data['job_id'], data['gcode_id'])
        
        try:
            return cls(
                job_id=data['job_id'],
                gcode_id=data['gcode_id'],
                gcode_url_compressed=data['gcode_url_compressed'],
                gcode_filename=data['gcode_filename'],
                file_hash=data['file_hash'],
                estimated_print_time_seconds=data['estimated_print_time_seconds']
            )
        except Exception as e:
            logger.error("Error creating Job object: %s", str(e))
            return None

class BytesIOWrapper:
    def __init__(self, bytes_io):
        self.bytes_io = bytes_io

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.bytes_io.getvalue())

class JobHandler:
    def __init__(self, additv_plugin):
        self._octoprint = additv_plugin
        self._additv_client = additv_plugin.additv_client
        self._logger = additv_plugin._logger
        self._file_storage = additv_plugin._file_manager._storage_managers['local']
        self._upload_folder = "Additv"
        self._printer = additv_plugin._printer
        self._printer_commands = additv_plugin.printer_commands
        self._job = None
        self._filament_tracker = FilamentTracker()
        self._last_reported_e = Decimal('0.0')
        self.preheat_timer = None
        self.delay_time_remaining = 0

    def report_job_progress(self, progress: float):
        """
        Report print job progress and job-specific filament usage to Additv
        Args:
            progress (float): Progress percentage (0-100)
        
        The odometer readings track filament usage for this specific job,
        resetting at the start of each new job.
        """
        if self._job is None:
            self._logger.warning("Cannot report job progress: No active job")
            return

        self._logger.info(f"Print progress: {progress}% for job {self._job.job_id}")
        
        try:
            current_e = self._filament_tracker.total_extrusion
            odometer_readings = [{
                "e_last_reported": float(self._last_reported_e),
                "e_current": float(current_e)
            }]
            
            self._additv_client.publish_job_progress(
                self._job.job_id,
                progress,
                odometer_readings
            )
            self._last_reported_e = current_e
        except Exception as e:
            self._logger.error(f"Error publishing progress: {str(e)}")

    def _get_next_job(self) -> Optional[Job]:
        """
        Retrieves the next available job from the edge function.
        
        Returns:
            Job: The next job if available, None otherwise
        """
        try:
            if not self._additv_client:
                self._logger.error("Additv client not initialized")
                return None
                
            result = self._additv_client.call_edge_function("get-next-job")
            if not result:
                self._logger.debug("No jobs available")
                self._printer_commands.send_lcd_message("No suitable jobs")
                return None
            
            return Job.from_dict(result, self._logger)
            
        except Exception as e:
            self._logger.error("Error getting next job: %s", str(e))
            return None

    def _download_gcode(self, job: Job) -> bool:
        """
        Downloads and saves a gcode file from the given URL using OctoPrint's file manager.
        
        Args:
            job (Job): The job object containing gcode information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Extract base filename without extension
            base_filename = job.gcode_filename.split('.')[0]
            filename = f"{self._upload_folder}/{base_filename}_id-{job.gcode_id}.gcode"
            job.octoprint_filename = filename
            
            # Check if file exists
            if self._file_storage.file_exists(filename):
                self._logger.info(f"Gcode file {filename} already exists, skipping download")
                return True
                
            # Download the file from the URL
            self._logger.info(f"Downloading gcode from {job.gcode_url_compressed}")
            response = requests.get(job.gcode_url_compressed, stream=True, timeout=30)
            response.raise_for_status()
            # Stream the downloaded content into a BytesIO buffer
            zip_obj = BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    zip_obj.write(chunk)
            zip_obj.seek(0)
            
            # Extract the gcode file from the zip
            with zipfile.ZipFile(zip_obj) as zip_file:
                # Get the first file in the zip (assuming it's the gcode file)
                gcode_filename = zip_file.namelist()[0]
                self._logger.info(f"Extracting {gcode_filename} from zip file")
                gcode_content = zip_file.read(gcode_filename)
                self._logger.info(f"Successfully extracted gcode file from zip")
                
                # Verify file hash
                file_hash = hashlib.sha256(gcode_content).hexdigest()
                if file_hash != job.file_hash:
                    error_msg = f"Hash mismatch for gcode file. Expected: {job.file_hash}, Got: {file_hash}"
                    self._logger.error(error_msg)
                    # Trigger PrintCancelled event with hash verification failure details
                    self._octoprint.event_handler.handle_event("Error", {
                        "error": "hash_verification_failed",
                        "message": error_msg,
                        "job_id": job.job_id,
                        "gcode_id": job.gcode_id
                    })
                    return False
                self._logger.info("File hash verification successful")
            
            # Create a new BytesIO object with the extracted gcode content
            gcode_obj = BytesIO(gcode_content)
            
            # Wrap the BytesIO object with our custom wrapper that provides the save method
            wrapped_file_obj = BytesIOWrapper(gcode_obj)
            
            # Save the downloaded file using LocalFileStorage
            self._logger.info(f"Saving downloaded gcode as {filename}")
            self._file_storage.add_folder(self._upload_folder)
            self._file_storage.add_file(
                filename,
                wrapped_file_obj,
                allow_overwrite=True
            )
            
            self._logger.info(f"Successfully downloaded gcode file {filename}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error downloading gcode file: {str(e)}")
            
            self._octoprint.event_handler.handle_event("Error", {
            "error": "download_gcode_failed",
            "message": error_msg,
            "job_id": job.job_id,
            "gcode_id": job.gcode_id
                    })
            
            return False

    def _handle_preheat_countdown(self):
        """Handle the preheat countdown and temperature monitoring"""
        current_temps = self._printer.get_current_temperatures()
        nozzle_temp = float(current_temps.get('tool0', {}).get('actual', 0))
        bed_temp = float(current_temps.get('bed', {}).get('actual', 0))
        bed_target_temp = float(current_temps.get('bed', {}).get('target', 0))

        if nozzle_temp > 160:
            if self.delay_time_remaining > 0:
                if bed_temp > 80 or bed_target_temp == 85:
                    self._printer_commands.send_lcd_message(f"Heat soak - {self.delay_time_remaining} sec")
                    self.delay_time_remaining -= 1
                else:
                    self._printer.set_temperature("bed", 85)
            else:
                if self.preheat_timer:
                    self.preheat_timer.cancel()
                    self.preheat_timer = None
                # Now safe to start the print
                self._printer.select_file(self._job.octoprint_filename, sd=False, printAfterSelect=True)
                self._logger.info(f"Started print for job {self._job.job_id} with file {self._job.octoprint_filename}")
        else:
            self._logger.debug("Waiting for nozzle to reach temperature...")

    def _start_preheat_sequence(self, estimated_print_time: int) -> None:
        """Start the preheat sequence if print time exceeds threshold"""
        self.delay_time_remaining = 600 if estimated_print_time > 10800 else 0  # 10 min delay for prints > 3 hours
        
        # Send preheat event to Additv
        self._octoprint.event_handler.handle_event("Preheat", {
            "job_id": self._job.job_id,
            "gcode_id": self._job.gcode_id,
        })

        self._printer.set_temperature("tool0", 170)
        self._printer_commands.send_lcd_message("Clean nozzle")
        
        if self.delay_time_remaining > 0:
            self.preheat_timer = RepeatedTimer(1, self._handle_preheat_countdown)
            self.preheat_timer.start()
            self._logger.info(f"Started preheat sequence with {self.delay_time_remaining} second delay")

    def _start_print(self, job: Job) -> bool:
        """
        Loads and starts printing the specified job's gcode file.
        
        Args:
            job (Job): The job containing the file to print
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not job.octoprint_filename:
            self._logger.error("No OctoPrint filename set for job %s", job.job_id)
            return False

        try:
            # Start preheat sequence based on estimated print time
            estimated_time = job.estimated_print_time_seconds
            self._start_preheat_sequence(estimated_time)
            return True
        except Exception as e:
            self._logger.error("Error starting print for job %s: %s", job.job_id, str(e))
            return False

    def start_next_job(self):
        """
        Gets a job from Additv, loads and starts it
        """
        if not self.preheat_timer:
            self._printer_commands.send_lcd_message("Fetching next Job...")
            job = self._get_next_job()
            if job:
                self._job = job
                self._filament_tracker.reset()  # Reset extrusion tracking for new job
                self._last_reported_e = Decimal('0.0')
                self._logger.info("Retrieved job: %s", job)
                self._download_gcode(job)
                self._start_print(job)
            else:
                self._logger.info("No job available")
        else:
            self._logger.error("Preheat already in progress, cannot start new job")

    def cancel_preheat(self):
        """Cancel any active preheat timer and reset delay time"""
        if self.preheat_timer:
            self.preheat_timer.cancel()
            self.preheat_timer = None
            self.delay_time_remaining = 0

    def process_gcode_line(self, line: str):
        """
        Process a line of gcode to track extrusion
        Args:
            line (str): The gcode line to process
        Returns:
            float or None: Current total extrusion if line contained extrusion, None otherwise
        """
        if self._job is None:
            return None
            
        return self._filament_tracker.process_line(line)
