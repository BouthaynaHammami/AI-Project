import os
import threading
import time
from collections import deque


class GroqGlobalLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__("Groq global request limit reached.")


_requests_per_minute = max(1, int(os.getenv("GROQ_GLOBAL_RPM", "20")))
_window_seconds = 60.0
_request_times: deque[float] = deque()
_lock = threading.Lock()


def acquire_groq_slot() -> None:
    now = time.monotonic()
    with _lock:
        while _request_times and now - _request_times[0] >= _window_seconds:
            _request_times.popleft()
        if len(_request_times) >= _requests_per_minute:
            retry_after = int(_window_seconds - (now - _request_times[0])) + 1
            raise GroqGlobalLimitExceeded(retry_after)
        _request_times.append(now)


def clear_groq_slots() -> None:
    with _lock:
        _request_times.clear()
