from io import BytesIO
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
import requests
from .filament_tracker import FilamentTracker

@dataclass
class Job:
    job_id: int
    gcode_id: int
    gcode_url: str
    gcode_filename: str
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
        required_fields = {'job_id', 'gcode_id', 'gcode_url', 'gcode_filename'}
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
                gcode_url=data['gcode_url'],
                gcode_filename=data['gcode_filename']
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
        self._job = None
        self._filament_tracker = FilamentTracker()
        self._last_reported_e = Decimal('0.0')

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
            self._logger.info(f"Downloading gcode from {job.gcode_url}")
            response = requests.get(job.gcode_url, stream=True, timeout=30)
            response.raise_for_status()
            # Stream the downloaded content into a BytesIO buffer
            file_obj = BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
            file_obj.seek(0)
            
            # Wrap the BytesIO object with our custom wrapper that provides the save method
            wrapped_file_obj = BytesIOWrapper(file_obj)
            
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
            return False

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
            # Select the file for printing
            self._printer.select_file(job.octoprint_filename, False, printAfterSelect=True)

            self._logger.info("Started print for job %s with file %s", job.job_id, job.octoprint_filename)
            return True
        except Exception as e:
            self._logger.error("Error starting print for job %s: %s", job.job_id, str(e))
            return False

    def start_next_job(self):
        """
        Gets a job from Additv, loads and starts it
        """
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
