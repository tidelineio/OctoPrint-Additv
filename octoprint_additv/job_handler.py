import logging
from .additv_client import AdditvClient

class JobHandler:
    def __init__(self, additv_client: AdditvClient):
        self._additv_client = additv_client
        self._logger = logging.getLogger("octoprint.plugins.additv.job_handler")

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
            required_fields = {'job_number', 'gcode_id', 'gcode_url'}
            
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

    def start_job_processing(self):
        """
        Initiates the job processing loop.
        Currently just retrieves the next job as a test.
        """
        job = self.get_next_job()
        if job:
            self._logger.info("Retrieved job: %s", job)
        else:
            self._logger.info("No job available")
