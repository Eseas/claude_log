"""Loads signal patterns and step-classification keywords from signals.yaml.

Lookup order (first existing file wins for the whole document):
  1. explicit path passed to SignalRegistry(path=...)
  2. ./signals.yaml in the current working directory
  3. ~/.claude_log/signals.yaml
  4. the bundled default next to this module

Externalizing these patterns lets users tune success/failure detection and
step classification without editing code.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Tuple

import yaml

BUNDLED_PATH = Path(__file__).parent / "signals.yaml"


@dataclass(frozen=True)
class Signal:
    """A weighted, labeled regex signal compiled for case-insensitive search."""
    pattern: Pattern
    label: str
    weight: float


def _candidate_paths(explicit: Optional[Path]) -> List[Path]:
    paths = []
    if explicit:
        paths.append(Path(explicit))
    paths.append(Path.cwd() / "signals.yaml")
    paths.append(Path.home() / ".claude_log" / "signals.yaml")
    paths.append(BUNDLED_PATH)
    return paths


class SignalRegistry:
    """Provides compiled heuristic signals and step-classification patterns."""

    def __init__(self, path: Optional[Path] = None):
        self._data = self._load(path)
        self._failure = self._compile(self._data.get("failure_signals", []))
        self._success = self._compile(self._data.get("success_signals", []))
        # Tool-error patterns are matched case-sensitively (they enumerate cases
        # explicitly, e.g. Error|ERROR|error) to preserve original behavior.
        self._tool_error = self._compile(self._data.get("tool_error_signals", []), ignore_case=False)
        self._step = self._compile_step(self._data.get("step_classification", {}))

    @staticmethod
    def _load(path: Optional[Path]) -> dict:
        for candidate in _candidate_paths(path):
            if candidate and candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        return {}

    @staticmethod
    def _compile(entries: List[dict], ignore_case: bool = True) -> List[Signal]:
        flags = re.IGNORECASE if ignore_case else 0
        signals = []
        for e in entries:
            signals.append(Signal(
                pattern=re.compile(e["pattern"], flags),
                label=e["label"],
                weight=float(e["weight"]),
            ))
        return signals

    @staticmethod
    def _compile_step(groups: Dict[str, str]) -> Dict[str, Pattern]:
        return {key: re.compile(body) for key, body in groups.items()}

    # --- Heuristic signals (used by TaskSuccessAnalyzer) ---

    @property
    def failure_signals(self) -> List[Signal]:
        return self._failure

    @property
    def success_signals(self) -> List[Signal]:
        return self._success

    @property
    def tool_error_signals(self) -> List[Signal]:
        return self._tool_error

    # --- Step classification (used by timeline data_extraction) ---

    def classify_step(self, summary: str) -> str:
        """Classify a step summary into one of the five process-step types."""
        s = summary.lower()
        step = self._step

        verify = step.get("verification")
        if verify and verify.search(s):
            impl_override = step.get("verification_impl_override")
            if impl_override and impl_override.search(s):
                return "implementation"
            return "verification"

        decision = step.get("decision")
        if decision and decision.search(s):
            return "decision"

        implementation = step.get("implementation")
        if implementation and implementation.search(s):
            return "implementation"

        summary_pat = step.get("summary")
        if summary_pat and summary_pat.search(s):
            return "summary"

        analysis = step.get("analysis")
        if analysis and analysis.search(s):
            return "analysis"

        return "analysis"


# Shared default registry (bundled patterns). Cheap to construct; reused widely.
_default_registry: Optional[SignalRegistry] = None


def get_default_registry() -> SignalRegistry:
    """Return a lazily-constructed shared SignalRegistry from default lookup."""
    global _default_registry
    if _default_registry is None:
        _default_registry = SignalRegistry()
    return _default_registry
