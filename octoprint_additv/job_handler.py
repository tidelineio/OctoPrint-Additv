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
                
            # Validate expected job data
            if not isinstance(result, dict) or not all(key in result for key in ['job_number', 'gcode_id', 'gcode_url']):
                self._logger.error("Invalid job data format in response")
                return None
                
            self._logger.info(f"Retrieved job {result['job_number']} with gcode {result['gcode_id']}")
            return result
        except Exception as e:
            self._logger.error(f"Error getting next job: {str(e)}")
            return None

    def start_job_processing(self):
        """
        Initiates the job processing loop.
        Currently just retrieves the next job as a test.
        """
        job = self.get_next_job()
        if job:
            self._logger.info(f"Retrieved job: {job}")
        else:
            self._logger.info("No job available")
