# Subprocess Isolation for Stegasoo WebUI

This update runs encode/decode/compare operations in isolated subprocesses
to prevent jpegio/scipy crashes from taking down the Flask server.

## Files

- **app.py** - Updated Flask app using subprocess isolation
- **subprocess_stego.py** - Flask-side wrapper with clean API  
- **stego_worker.py** - Subprocess script that does actual stegasoo operations

## Setup

1. Place all three files in your `webui/` directory (same level as templates/)

2. Make sure stego_worker.py is executable (optional):
   ```bash
   chmod +x stego_worker.py
   ```

3. Run the Flask app:
   ```bash
   python app.py
   ```

## How It Works

Instead of calling stegasoo functions directly in the Flask process:

```python
# OLD (crashes could kill Flask)
result = encode(...)
```

We now run them in subprocesses:

```python
# NEW (crashes only kill the subprocess)
result = subprocess_stego.encode(...)
```

If jpegio or scipy crashes due to memory corruption, only the subprocess
dies. Flask logs the error and continues running. The next request spawns
a fresh subprocess.

## Configuration

In `app.py`, you can adjust the timeout:

```python
subprocess_stego = SubprocessStego(timeout=180)  # 3 minutes
```

Larger images may need longer timeouts.

## Troubleshooting

If you see "Worker script not found" errors, make sure `stego_worker.py`
is in the same directory as `app.py`.

If subprocess operations fail, check the Flask logs for error details.
The subprocess wrapper captures both stdout and stderr from the worker.
