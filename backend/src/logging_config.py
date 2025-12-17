"""Logging configuration for the backend.

This module configures the root logger to write to a rotating file at
`backend/logs/backend.log` and also to the console. It also redirects
stdout/stderr to the logging system so that prints appear in the log file.

Importing this module (e.g., `from src import logging_config`) will set up
logging immediately.
"""
import logging
import logging.handlers
import os
import sys


def setup_logging():
    # Allow toggling file logging via environment variables.
    # Defaults:
    #  - In production (ENV=production), file logging is disabled unless LOG_TO_FILE=1|true is set.
    #  - In other environments, file logging is enabled unless LOG_TO_FILE=0|false is set.
    ENV = os.environ.get("ENV", "development").lower()
    raw = os.environ.get("LOG_TO_FILE")
    if raw is not None:
        LOG_TO_FILE = raw.lower() not in ("0", "false", "no")
    else:
        LOG_TO_FILE = ENV != "production"

    # Place logs in the top-level backend/logs directory
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, "backend.log")

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Capture the real stdout/stderr before we redirect them to logging
    real_stdout = sys.stdout
    real_stderr = sys.stderr

    # Console handler (use real stdout to avoid recursion when we replace sys.stdout later)
    ch = logging.StreamHandler(real_stdout)
    ch.setFormatter(formatter)
    ch.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates when reloading
    if root.handlers:
        root.handlers = []

    # Conditionally add file handler
    if LOG_TO_FILE:
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(formatter)
        fh.setLevel(logging.DEBUG)
        root.addHandler(fh)
    else:
        # Informational message will go to console handler
        ch.setLevel(logging.INFO)
        root.addHandler(ch)
        logging.getLogger(__name__).info("File logging disabled (ENV=%s, LOG_TO_FILE=%s)", ENV, raw)

    # Ensure console handler is present (avoid duplicate if fh was added above)
    if LOG_TO_FILE:
        # make sure console logs are still added at INFO level
        root.addHandler(ch)

    # Ensure common libraries propagate into our logger
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.propagate = True

    # Redirect prints (stdout/stderr) into logging
    class StreamToLogger:
        def __init__(self, logger, level=logging.INFO):
            self.logger = logger
            self.level = level
            # some libraries check these attributes/methods (e.g., uvicorn uses isatty())
            self.encoding = "utf-8"

        def write(self, message):
            # logging module will be fed line-wise; ensure trailing newlines are stripped
            message = message.rstrip('\n')
            if not message:
                return

            # Prevent recursive re-entry: if we're already handling a write call,
            # write directly to the real streams to avoid infinite recursion.
            if getattr(self, "_writing", False):
                try:
                    if self.level >= logging.ERROR:
                        real_stderr.write(message + "\n")
                        real_stderr.flush()
                    else:
                        real_stdout.write(message + "\n")
                        real_stdout.flush()
                except Exception:
                    # Best-effort fallback; swallow to avoid raising during logging
                    try:
                        sys.__stderr__.write(message + "\n")
                        sys.__stderr__.flush()
                    except Exception:
                        pass
                return

            self._writing = True
            try:
                # Normal path: send message into logging
                self.logger.log(self.level, message)
            except Exception:
                # If logging fails (e.g., handler emit raises), fallback to original streams
                try:
                    if self.level >= logging.ERROR:
                        real_stderr.write(message + "\n")
                        real_stderr.flush()
                    else:
                        real_stdout.write(message + "\n")
                        real_stdout.flush()
                except Exception:
                    try:
                        sys.__stderr__.write(message + "\n")
                        sys.__stderr__.flush()
                    except Exception:
                        # swallow everything to avoid further errors
                        pass
            finally:
                self._writing = False

        def flush(self):
            pass

        def isatty(self):
            # Return False so libraries know stdout is not a TTY
            return False

        def fileno(self):
            # Not a real file descriptor; raise to mimic non-file-like behaviour
            raise OSError("StreamToLogger does not have a file descriptor")

    sys.stdout = StreamToLogger(logging.getLogger("STDOUT"), logging.INFO)
    sys.stderr = StreamToLogger(logging.getLogger("STDERR"), logging.ERROR)

    logging.getLogger(__name__).info("Logging initialized. File: %s", log_file)


# Run setup when module is imported
setup_logging()
