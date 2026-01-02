"""
Stegasoo Debugging Utilities

Debugging, logging, and performance monitoring tools.
Can be disabled for production use.
"""

import sys
import time
import traceback
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

# Global debug configuration
DEBUG_ENABLED = False  # Set to True to enable debug output
LOG_PERFORMANCE = True  # Log function timing
VALIDATION_ASSERTIONS = True  # Enable runtime validation assertions


def enable_debug(enable: bool = True) -> None:
    """Enable or disable debug mode globally."""
    global DEBUG_ENABLED
    DEBUG_ENABLED = enable


def enable_performance_logging(enable: bool = True) -> None:
    """Enable or disable performance timing."""
    global LOG_PERFORMANCE
    LOG_PERFORMANCE = enable


def enable_assertions(enable: bool = True) -> None:
    """Enable or disable validation assertions."""
    global VALIDATION_ASSERTIONS
    VALIDATION_ASSERTIONS = enable


def debug_print(message: str, level: str = "INFO") -> None:
    """Print debug message with timestamp if debugging is enabled."""
    if DEBUG_ENABLED:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)


def debug_data(data: bytes, label: str = "Data", max_bytes: int = 32) -> str:
    """Format bytes for debugging."""
    if not DEBUG_ENABLED:
        return ""

    if not data:
        return f"{label}: Empty"

    if len(data) <= max_bytes:
        return f"{label} ({len(data)} bytes): {data.hex()}"
    else:
        return f"{label} ({len(data)} bytes): {data[:max_bytes//2].hex()}...{data[-max_bytes//2:].hex()}"


def debug_exception(e: Exception, context: str = "") -> None:
    """Log exception with context for debugging."""
    if DEBUG_ENABLED:
        debug_print(f"Exception in {context}: {type(e).__name__}: {e}", "ERROR")
        if DEBUG_ENABLED:
            traceback.print_exc()


def time_function(func: Callable) -> Callable:
    """Decorator to time function execution for performance debugging."""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        if not (DEBUG_ENABLED and LOG_PERFORMANCE):
            return func(*args, **kwargs)

        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end = time.perf_counter()
            debug_print(f"{func.__name__} took {end - start:.6f}s", "PERF")

    return wrapper


def validate_assertion(condition: bool, message: str) -> None:
    """Runtime validation that can be disabled in production."""
    if VALIDATION_ASSERTIONS and not condition:
        raise AssertionError(f"Validation failed: {message}")


def memory_usage() -> dict[str, float | str]:
    """Get current memory usage (if psutil is available)."""
    try:
        import os

        import psutil

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        return {
            "rss_mb": mem_info.rss / 1024 / 1024,
            "vms_mb": mem_info.vms / 1024 / 1024,
            "percent": process.memory_percent(),
        }
    except ImportError:
        return {"error": "psutil not installed"}


def hexdump(data: bytes, offset: int = 0, length: int = 64) -> str:
    """Create hexdump string for debugging binary data."""
    if not data:
        return "Empty"

    result = []
    data_to_dump = data[:length]

    for i in range(0, len(data_to_dump), 16):
        chunk = data_to_dump[i : i + 16]
        hex_str = " ".join(f"{b:02x}" for b in chunk)
        hex_str = hex_str.ljust(47)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        result.append(f"{offset + i:08x}: {hex_str}  {ascii_str}")

    if len(data) > length:
        result.append(f"... ({len(data) - length} more bytes)")

    return "\n".join(result)


class Debug:
    """Debugging utility class."""

    def __init__(self):
        self.enabled = DEBUG_ENABLED

    def print(self, message: str, level: str = "INFO") -> None:
        """Print debug message."""
        debug_print(message, level)

    def data(self, data: bytes, label: str = "Data", max_bytes: int = 32) -> str:
        """Format bytes for debugging."""
        return debug_data(data, label, max_bytes)

    def exception(self, e: Exception, context: str = "") -> None:
        """Log exception with context."""
        debug_exception(e, context)

    def time(self, func: Callable) -> Callable:
        """Decorator to time function execution."""
        return time_function(func)

    def validate(self, condition: bool, message: str) -> None:
        """Runtime validation assertion."""
        validate_assertion(condition, message)

    def memory(self) -> dict[str, float | str]:
        """Get current memory usage."""
        return memory_usage()

    def hexdump(self, data: bytes, offset: int = 0, length: int = 64) -> str:
        """Create hexdump string."""
        return hexdump(data, offset, length)

    def enable(self, enable: bool = True) -> None:
        """Enable or disable debug mode."""
        enable_debug(enable)
        self.enabled = enable

    def enable_performance(self, enable: bool = True) -> None:
        """Enable or disable performance logging."""
        enable_performance_logging(enable)

    def enable_assertions(self, enable: bool = True) -> None:
        """Enable or disable validation assertions."""
        enable_assertions(enable)


# Create singleton instance
debug = Debug()
