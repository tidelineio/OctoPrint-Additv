from io import BytesIO
import requests

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

    def get_next_job(self):
        """
        Retrieves the next available job from the edge function.
        
        Returns:
            dict: The next job if available, None otherwise
        """
        try:
            if not self._additv_client:
                self._logger.error("Additv client not initialized")
                return None
                
            result = self._additv_client.call_edge_function("get-next-job")
            if not result:
                self._logger.debug("No jobs available")
                return None
            
            # Validate required job data fields
            required_fields = {'job_number', 'gcode_id', 'gcode_url', 'gcode_filename'}
            if not isinstance(result, dict):
                self._logger.error("Invalid job data format: expected dict, got %s", type(result).__name__)
                return None
                
            missing_fields = required_fields - set(result.keys())
            if missing_fields:
                self._logger.error("Missing required job data fields: %s", ', '.join(missing_fields))
                return None
                
            # Log all received fields for debugging
            self._logger.debug("Received job data fields: %s", ', '.join(result.keys()))
            self._logger.info("Retrieved job %s with gcode %s", result['job_number'], result['gcode_id'])
            return result
        except Exception as e:
            self._logger.error("Error getting next job: %s", str(e))
            return None

    def _download_gcode(self, gcode_url: str, gcode_id: str,) -> bool:
        """
        Downloads and saves a gcode file from the given URL using OctoPrint's file manager.
        
        Args:
            gcode_url (str): The URL to download the gcode from
            gcode_id (str): The ID of the gcode file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filename = f"{self._upload_folder}/{gcode_id}.gcode"
            
            # Check if file exists
            if self._file_storage.file_exists(filename):
                self._logger.info(f"Gcode file {filename} already exists, skipping download")
                return True
                
            # Download the file from the URL
            self._logger.info(f"Downloading gcode from {gcode_url}")
            response = requests.get(gcode_url, stream=True, timeout=30)
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

    def start_job_processing(self):
        """
        Initiates the job processing loop.
        Currently just retrieves the next job as a test.
        """
        job = self.get_next_job()
        if job:
            self._logger.info("Retrieved job: %s", job)
            self._download_gcode(job['gcode_url'], job['gcode_id'])
        else:
            self._logger.info("No job available")
