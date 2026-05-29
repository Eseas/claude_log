"""User-facing terminal output — the single chokepoint for CLI messages.

This is intentionally separate from `logging`, which handles system and
diagnostic logs (to file/stderr). Everything the *user* sees in the terminal
flows through `OutputWriter`, so it can be captured in tests and later swapped
for a richer renderer (e.g. Rich) by changing one class.
"""

import sys
from typing import Optional, TextIO


class OutputWriter:
    """Writes user-facing messages to a configurable stream."""

    def __init__(self, stream: Optional[TextIO] = None, err_stream: Optional[TextIO] = None):
        self._stream = stream if stream is not None else sys.stdout
        self._err = err_stream if err_stream is not None else sys.stderr

    def set_streams(self, stream: TextIO, err_stream: Optional[TextIO] = None) -> None:
        """Redirect output (used by tests to capture, or to swap renderers)."""
        self._stream = stream
        if err_stream is not None:
            self._err = err_stream

    def print(self, *args, file: Optional[TextIO] = None, **kwargs) -> None:
        """Drop-in replacement for builtins.print routed through this writer.

        Honors `file=sys.stderr` by redirecting to the configured error stream;
        all other calls go to the standard output stream.
        """
        if file is sys.stderr:
            target = self._err
        elif file is None:
            target = self._stream
        else:
            target = file
        print(*args, file=target, **kwargs)

    # --- Semantic helpers (consistent markers for new code) ---

    def blank(self) -> None:
        """Emit a blank line."""
        self.print()

    def info(self, msg: str) -> None:
        self.print(msg)

    def success(self, msg: str) -> None:
        self.print(f"✓ {msg}")

    def error(self, msg: str) -> None:
        self.print(f"❌ {msg}", file=sys.stderr)

    def warning(self, msg: str) -> None:
        self.print(f"⚠️  {msg}")


# Shared default instance. Modules import this; tests can capture via
# `out.set_streams(io.StringIO())` since the object identity is shared.
out = OutputWriter()
