"""
Subprocess Steganography Wrapper (v4.0.0)

Runs stegasoo operations in isolated subprocesses to prevent crashes
from taking down the Flask server.

CHANGES in v4.0.0:
- Added channel_key parameter to encode() and decode() methods
- Channel keys enable deployment/group isolation

Usage:
    from subprocess_stego import SubprocessStego

    stego = SubprocessStego()

    # Encode with channel key
    result = stego.encode(
        carrier_data=carrier_bytes,
        reference_data=ref_bytes,
        message="secret message",
        passphrase="my passphrase",
        pin="123456",
        embed_mode="dct",
        channel_key="auto",  # or "none", or explicit key
    )

    if result.success:
        stego_bytes = result.stego_data
        extension = result.extension
    else:
        error_message = result.error

    # Decode
    result = stego.decode(
        stego_data=stego_bytes,
        reference_data=ref_bytes,
        passphrase="my passphrase",
        pin="123456",
        channel_key="auto",
    )

    # Compare modes (capacity)
    result = stego.compare_modes(carrier_bytes)
"""

import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Default timeout for operations (seconds)
DEFAULT_TIMEOUT = 120

# Path to worker script - adjust if needed
WORKER_SCRIPT = Path(__file__).parent / "stego_worker.py"


@dataclass
class EncodeResult:
    """Result from encode operation."""

    success: bool
    stego_data: bytes | None = None
    filename: str | None = None
    stats: dict[str, Any] | None = None
    # Channel info (v4.0.0)
    channel_mode: str | None = None
    channel_fingerprint: str | None = None
    error: str | None = None
    error_type: str | None = None


@dataclass
class DecodeResult:
    """Result from decode operation."""

    success: bool
    is_file: bool = False
    message: str | None = None
    file_data: bytes | None = None
    filename: str | None = None
    mime_type: str | None = None
    error: str | None = None
    error_type: str | None = None


@dataclass
class CompareResult:
    """Result from compare_modes operation."""

    success: bool
    width: int = 0
    height: int = 0
    lsb: dict[str, Any] | None = None
    dct: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class CapacityResult:
    """Result from capacity check operation."""

    success: bool
    fits: bool = False
    payload_size: int = 0
    capacity: int = 0
    usage_percent: float = 0.0
    headroom: int = 0
    mode: str = ""
    error: str | None = None


@dataclass
class ChannelStatusResult:
    """Result from channel status check (v4.0.0)."""

    success: bool
    mode: str = "public"
    configured: bool = False
    fingerprint: str | None = None
    source: str | None = None
    key: str | None = None
    error: str | None = None


class SubprocessStego:
    """
    Subprocess-isolated steganography operations.

    All operations run in a separate Python process. If jpegio or scipy
    crashes, only the subprocess dies - Flask keeps running.
    """

    def __init__(
        self,
        worker_path: Path | None = None,
        python_executable: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize subprocess wrapper.

        Args:
            worker_path: Path to stego_worker.py (default: same directory)
            python_executable: Python interpreter to use (default: same as current)
            timeout: Default timeout in seconds
        """
        self.worker_path = worker_path or WORKER_SCRIPT
        self.python = python_executable or sys.executable
        self.timeout = timeout

        if not self.worker_path.exists():
            raise FileNotFoundError(f"Worker script not found: {self.worker_path}")

    def _run_worker(self, params: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        """
        Run the worker subprocess with given parameters.

        Args:
            params: Dictionary of parameters (will be JSON-encoded)
            timeout: Operation timeout in seconds

        Returns:
            Dictionary with results from worker
        """
        timeout = timeout or self.timeout
        input_json = json.dumps(params)

        try:
            result = subprocess.run(
                [self.python, str(self.worker_path)],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.worker_path.parent),
            )

            # DEBUG: Log worker stderr to main process stderr
            if result.stderr:
                print(result.stderr, file=sys.stderr, end='')

            if result.returncode != 0:
                # Worker crashed
                return {
                    "success": False,
                    "error": f"Worker crashed (exit code {result.returncode})",
                    "stderr": result.stderr,
                }

            if not result.stdout.strip():
                return {
                    "success": False,
                    "error": "Worker returned empty output",
                    "stderr": result.stderr,
                }

            return json.loads(result.stdout)

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Operation timed out after {timeout} seconds",
                "error_type": "TimeoutError",
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON from worker: {e}",
                "raw_output": result.stdout if "result" in dir() else None,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def encode(
        self,
        carrier_data: bytes,
        reference_data: bytes,
        message: str | None = None,
        file_data: bytes | None = None,
        file_name: str | None = None,
        file_mime: str | None = None,
        passphrase: str = "",
        pin: str | None = None,
        rsa_key_data: bytes | None = None,
        rsa_password: str | None = None,
        embed_mode: str = "lsb",
        dct_output_format: str = "png",
        dct_color_mode: str = "color",
        # Channel key (v4.0.0)
        channel_key: str | None = "auto",
        timeout: int | None = None,
    ) -> EncodeResult:
        """
        Encode a message or file into an image.

        Args:
            carrier_data: Carrier image bytes
            reference_data: Reference photo bytes
            message: Text message to encode (if not file)
            file_data: File bytes to encode (if not message)
            file_name: Original filename (for file payload)
            file_mime: MIME type (for file payload)
            passphrase: Encryption passphrase
            pin: Optional PIN
            rsa_key_data: Optional RSA key PEM bytes
            rsa_password: RSA key password if encrypted
            embed_mode: 'lsb' or 'dct'
            dct_output_format: 'png' or 'jpeg' (for DCT mode)
            dct_color_mode: 'grayscale' or 'color' (for DCT mode)
            channel_key: 'auto' (server config), 'none' (public), or explicit key (v4.0.0)
            timeout: Operation timeout in seconds

        Returns:
            EncodeResult with stego_data and extension on success
        """
        params = {
            "operation": "encode",
            "carrier_b64": base64.b64encode(carrier_data).decode("ascii"),
            "reference_b64": base64.b64encode(reference_data).decode("ascii"),
            "message": message,
            "passphrase": passphrase,
            "pin": pin,
            "embed_mode": embed_mode,
            "dct_output_format": dct_output_format,
            "dct_color_mode": dct_color_mode,
            "channel_key": channel_key,  # v4.0.0
        }

        if file_data:
            params["file_b64"] = base64.b64encode(file_data).decode("ascii")
            params["file_name"] = file_name
            params["file_mime"] = file_mime

        if rsa_key_data:
            params["rsa_key_b64"] = base64.b64encode(rsa_key_data).decode("ascii")
            params["rsa_password"] = rsa_password

        result = self._run_worker(params, timeout)

        if result.get("success"):
            return EncodeResult(
                success=True,
                stego_data=base64.b64decode(result["stego_b64"]),
                filename=result.get("filename"),
                stats=result.get("stats"),
                channel_mode=result.get("channel_mode"),
                channel_fingerprint=result.get("channel_fingerprint"),
            )
        else:
            return EncodeResult(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type"),
            )

    def decode(
        self,
        stego_data: bytes,
        reference_data: bytes,
        passphrase: str = "",
        pin: str | None = None,
        rsa_key_data: bytes | None = None,
        rsa_password: str | None = None,
        embed_mode: str = "auto",
        # Channel key (v4.0.0)
        channel_key: str | None = "auto",
        timeout: int | None = None,
    ) -> DecodeResult:
        """
        Decode a message or file from a stego image.

        Args:
            stego_data: Stego image bytes
            reference_data: Reference photo bytes
            passphrase: Decryption passphrase
            pin: Optional PIN
            rsa_key_data: Optional RSA key PEM bytes
            rsa_password: RSA key password if encrypted
            embed_mode: 'auto', 'lsb', or 'dct'
            channel_key: 'auto' (server config), 'none' (public), or explicit key (v4.0.0)
            timeout: Operation timeout in seconds

        Returns:
            DecodeResult with message or file_data on success
        """
        params = {
            "operation": "decode",
            "stego_b64": base64.b64encode(stego_data).decode("ascii"),
            "reference_b64": base64.b64encode(reference_data).decode("ascii"),
            "passphrase": passphrase,
            "pin": pin,
            "embed_mode": embed_mode,
            "channel_key": channel_key,  # v4.0.0
        }

        if rsa_key_data:
            params["rsa_key_b64"] = base64.b64encode(rsa_key_data).decode("ascii")
            params["rsa_password"] = rsa_password

        result = self._run_worker(params, timeout)

        if result.get("success"):
            if result.get("is_file"):
                return DecodeResult(
                    success=True,
                    is_file=True,
                    file_data=base64.b64decode(result["file_b64"]),
                    filename=result.get("filename"),
                    mime_type=result.get("mime_type"),
                )
            else:
                return DecodeResult(
                    success=True,
                    is_file=False,
                    message=result.get("message"),
                )
        else:
            return DecodeResult(
                success=False,
                error=result.get("error", "Unknown error"),
                error_type=result.get("error_type"),
            )

    def compare_modes(
        self,
        carrier_data: bytes,
        timeout: int | None = None,
    ) -> CompareResult:
        """
        Compare LSB and DCT capacity for a carrier image.

        Args:
            carrier_data: Carrier image bytes
            timeout: Operation timeout in seconds

        Returns:
            CompareResult with capacity information
        """
        params = {
            "operation": "compare",
            "carrier_b64": base64.b64encode(carrier_data).decode("ascii"),
        }

        result = self._run_worker(params, timeout)

        if result.get("success"):
            comparison = result.get("comparison", {})
            return CompareResult(
                success=True,
                width=comparison.get("width", 0),
                height=comparison.get("height", 0),
                lsb=comparison.get("lsb"),
                dct=comparison.get("dct"),
            )
        else:
            return CompareResult(
                success=False,
                error=result.get("error", "Unknown error"),
            )

    def check_capacity(
        self,
        carrier_data: bytes,
        payload_size: int,
        embed_mode: str = "lsb",
        timeout: int | None = None,
    ) -> CapacityResult:
        """
        Check if a payload will fit in the carrier.

        Args:
            carrier_data: Carrier image bytes
            payload_size: Size of payload in bytes
            embed_mode: 'lsb' or 'dct'
            timeout: Operation timeout in seconds

        Returns:
            CapacityResult with fit information
        """
        params = {
            "operation": "capacity",
            "carrier_b64": base64.b64encode(carrier_data).decode("ascii"),
            "payload_size": payload_size,
            "embed_mode": embed_mode,
        }

        result = self._run_worker(params, timeout)

        if result.get("success"):
            r = result.get("result", {})
            return CapacityResult(
                success=True,
                fits=r.get("fits", False),
                payload_size=r.get("payload_size", 0),
                capacity=r.get("capacity", 0),
                usage_percent=r.get("usage_percent", 0.0),
                headroom=r.get("headroom", 0),
                mode=r.get("mode", embed_mode),
            )
        else:
            return CapacityResult(
                success=False,
                error=result.get("error", "Unknown error"),
            )

    def get_channel_status(
        self,
        reveal: bool = False,
        timeout: int | None = None,
    ) -> ChannelStatusResult:
        """
        Get current channel key status (v4.0.0).

        Args:
            reveal: Include full key in response
            timeout: Operation timeout in seconds

        Returns:
            ChannelStatusResult with channel info
        """
        params = {
            "operation": "channel_status",
            "reveal": reveal,
        }

        result = self._run_worker(params, timeout)

        if result.get("success"):
            status = result.get("status", {})
            return ChannelStatusResult(
                success=True,
                mode=status.get("mode", "public"),
                configured=status.get("configured", False),
                fingerprint=status.get("fingerprint"),
                source=status.get("source"),
                key=status.get("key") if reveal else None,
            )
        else:
            return ChannelStatusResult(
                success=False,
                error=result.get("error", "Unknown error"),
            )


# Convenience function for quick usage
_default_stego: SubprocessStego | None = None


def get_subprocess_stego() -> SubprocessStego:
    """Get or create default SubprocessStego instance."""
    global _default_stego
    if _default_stego is None:
        _default_stego = SubprocessStego()
    return _default_stego
