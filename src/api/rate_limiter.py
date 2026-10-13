"""Thread-Safe Global Rate Limiter for Google Places API.

Enforces a global Queries-Per-Second (QPS) ceiling across all concurrent worker threads
to comply with Google Cloud API quotas and prevent HTTP 429 (Too Many Requests).
"""

import threading
import time
from typing import Optional


class ThreadSafeRateLimiter:
    """Token/time-interval based rate limiter across multiple concurrent threads."""

    def __init__(self, max_qps: float = 10.0) -> None:
        """Initialize rate limiter.

        Args:
            max_qps: Maximum allowable queries per second across all threads combined.
                     Default is 10.0 (equivalent to 600 QPM, standard Google Cloud quota).
        """
        self.max_qps = max(0.1, float(max_qps))
        self.min_interval = 1.0 / self.max_qps
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0

    def acquire(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Wait until an API request slot is permitted according to the QPS limit.

        Args:
            stop_event: Optional cancellation event to abort waiting immediately.

        Returns:
            True if permission was granted; False if cancelled via stop_event.
        """
        while True:
            if stop_event and stop_event.is_set():
                return False

            with self._lock:
                now = time.time()
                elapsed = now - self._last_request_time
                if elapsed >= self.min_interval:
                    self._last_request_time = now
                    return True
                sleep_needed = self.min_interval - elapsed

            # Sleep outside the lock so other threads are not blocked
            if stop_event:
                if stop_event.wait(sleep_needed):
                    return False
            else:
                time.sleep(sleep_needed)
