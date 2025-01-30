from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
import logging
import time
from supabase import create_client

class AdditvClient:
    """Client for handling asynchronous communication with Additv backend services"""
    
    def __init__(self, url: str, access_key: str, refresh_token: str = None, logger=None):
        self._logger = logger or logging.getLogger(__name__)
        self._url = url
        self._access_key = access_key
        self._refresh_token = refresh_token
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Additv")
        
        # Initialize connection
        self._connect()

    def _connect(self):
        """Establish connection to Additv backend"""
        try:
            self._client = create_client(self._url, self._access_key)
            if self._refresh_token:
                self._client.auth.refresh_session(self._refresh_token)
            self._logger.info("_connect: Successfully established connection to Additv backend")
        except Exception as e:
            error_msg = f"_connect: Failed to connect to Additv backend - Error: {str(e)}, Type: {type(e).__name__}"
            self._logger.error(error_msg)
            raise type(e)(error_msg) from e

    def _execute_with_retry(self, operation, operation_name, *args, **kwargs):
        """Execute operation with retries"""
        retries = 3
        for attempt in range(retries):
            try:
                result = operation(*args, **kwargs)
                self._logger.debug(f"{operation_name}: Operation completed successfully")
                return result
            except Exception as e:
                if attempt == retries - 1:  # Last attempt
                    error_msg = f"{operation_name}: Operation failed after {retries} attempts - Error: {str(e)}, Type: {type(e).__name__}"
                    self._logger.error(error_msg)
                    raise type(e)(error_msg) from e
                self._logger.warning(f"{operation_name}: Attempt {attempt + 1}/{retries} failed - Error: {str(e)}, Type: {type(e).__name__}")
                time.sleep(1 * (attempt + 1))

    def insert(self, table: str, data: Dict[str, Any]) -> None:
        """Asynchronously insert data to Additv"""
        operation_name = f"insert(table='{table}')"
        self._logger.debug(f"{operation_name}: Starting insert operation with data: {data}")
        def _insert():
            return self._execute_with_retry(
                lambda: self._client.table(table).insert(data).execute(),
                operation_name
            )
        self._executor.submit(_insert)

    def upsert(self, table: str, data: Dict[str, Any], on_conflict: str) -> None:
        """Asynchronously upsert data to Additv"""
        operation_name = f"upsert(table='{table}', on_conflict='{on_conflict}')"
        self._logger.debug(f"{operation_name}: Starting upsert operation with data: {data}")
        def _upsert():
            return self._execute_with_retry(
                lambda: self._client.table(table).upsert(data, on_conflict=on_conflict).execute(),
                operation_name
            )
        self._executor.submit(_upsert)

    def update(self, table: str, data: Dict[str, Any], match: Dict[str, Any]) -> None:
        """Asynchronously update data in Additv"""
        operation_name = f"update(table='{table}', match={match})"
        self._logger.debug(f"{operation_name}: Starting update operation with data: {data}")
        def _update():
            try:
                query = self._client.table(table)
                for field, value in match.items():
                    query = query.eq(field, value)
                return self._execute_with_retry(
                    lambda: query.update(data).execute(),
                    operation_name
                )
            except Exception as e:
                error_msg = f"{operation_name}: Failed to build or execute update query - Error: {str(e)}, Type: {type(e).__name__}"
                self._logger.error(error_msg)
                raise type(e)(error_msg) from e
        self._executor.submit(_update)
