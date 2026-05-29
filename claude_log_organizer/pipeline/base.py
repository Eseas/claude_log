"""Pipeline core: context, step interface, and the runner."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class InvalidFileFormatError(Exception):
    """Raised when a file fails validation before parsing."""


class ParsingError(Exception):
    """Raised when parsing a log file fails."""


class PipelineContext:
    """Carries state through a pipeline run for a single file.

    Dependencies (config, parser_factory, generator, tracker) are injected once;
    steps fill in derived fields (task_id, task_data, output_path) as they run
    and may call `halt()` to stop the remaining steps early.
    """

    def __init__(self, file_path: Path, config, parser_factory, generator, tracker):
        self.file_path = file_path
        self.config = config
        self.parser_factory = parser_factory
        self.generator = generator
        self.tracker = tracker

        # Filled by steps
        self.task_id: Optional[str] = None
        self.task_data = None
        self.output_path: Optional[Path] = None

        self.halted = False

    def halt(self) -> None:
        """Signal that no further steps should run."""
        self.halted = True


class PipelineStep(ABC):
    """A single unit of work in a pipeline."""

    name = "step"

    def should_run(self, ctx: PipelineContext) -> bool:
        """Whether this step should execute for the given context."""
        return True

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> None:
        """Perform the step's work, mutating the context in place."""
        raise NotImplementedError


class Pipeline:
    """Runs an ordered list of steps until completion or an early halt."""

    def __init__(self, steps: Optional[List[PipelineStep]] = None):
        self._steps: List[PipelineStep] = list(steps) if steps else []

    def add_step(self, step: PipelineStep) -> "Pipeline":
        """Append a step; returns self for chaining."""
        self._steps.append(step)
        return self

    @property
    def steps(self) -> List[PipelineStep]:
        return list(self._steps)

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        """Run each step in order, stopping if the context is halted."""
        for step in self._steps:
            if ctx.halted:
                break
            if step.should_run(ctx):
                logger.debug("Pipeline step: %s", step.name)
                step.execute(ctx)
        return ctx
