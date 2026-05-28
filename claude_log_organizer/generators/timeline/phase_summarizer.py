"""Process step summarization — algorithmic grouping and optional AI refinement."""

import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict

from claude_log_organizer.models.task_data import ProcessPhase
from claude_log_organizer.generators.timeline.styles import ProcessStep, STEP_TYPE_STYLES

logger = logging.getLogger(__name__)


def summarize_process_steps(steps: List[ProcessStep]) -> List[ProcessPhase]:
    """Two-stage summarization: algorithmic grouping + optional AI refinement."""
    # Stage 1: algorithmic grouping (merge consecutive same-type)
    phases = group_consecutive_steps(steps)

    # If already compact enough, return
    if len(phases) <= 8:
        return phases

    # Stage 2: AI summarization
    steps_hash = get_steps_hash(steps)
    cached = load_cached_phases(steps_hash)
    if cached is not None:
        logger.info(f"Using cached phase summary ({len(cached)} phases)")
        return cached

    ai_phases = ai_summarize_phases(steps)
    if ai_phases is not None:
        logger.info(f"AI summarized {len(steps)} steps into {len(ai_phases)} phases")
        save_cached_phases(steps_hash, ai_phases)
        return ai_phases

    # Stage 3: Algorithmic condensation (fallback when AI unavailable)
    condensed = condense_phases(phases)
    logger.info(f"Algorithmically condensed {len(phases)} phases into {len(condensed)} phases")
    return condensed


def group_consecutive_steps(steps: List[ProcessStep]) -> List[ProcessPhase]:
    """Group consecutive same-type steps into phases."""
    if not steps:
        return []

    phases = []
    current_type = None
    current_steps: List[ProcessStep] = []

    for step in steps:
        step_type = step.type if isinstance(step, ProcessStep) else "analysis"
        if step_type != current_type and current_steps:
            phases.append(steps_to_phase(current_steps, current_type))
            current_steps = []
        current_type = step_type
        current_steps.append(step)

    if current_steps:
        phases.append(steps_to_phase(current_steps, current_type))

    return phases


def steps_to_phase(steps: List[ProcessStep], step_type: str) -> ProcessPhase:
    """Convert a group of same-type steps into a single ProcessPhase."""
    first = steps[0]
    summary = first.summary if isinstance(first, ProcessStep) else str(first)

    # Collect key details from steps that have them
    details = []
    for s in steps:
        if isinstance(s, ProcessStep) and s.details:
            for d in s.details[:2]:
                if d not in details:
                    details.append(d)
                    if len(details) >= 5:
                        break
        if len(details) >= 5:
            break

    icon = STEP_TYPE_STYLES.get(step_type, STEP_TYPE_STYLES["analysis"])[2]
    type_label = step_type.capitalize()

    return ProcessPhase(
        phase_name=f"{summary}" if len(steps) == 1 else f"{type_label}: {summary}",
        primary_type=step_type,
        step_count=len(steps),
        summary=summary,
        key_details=details,
    )


def condense_phases(phases: List[ProcessPhase]) -> List[ProcessPhase]:
    """Condense many algorithmic phases into ~6 by equal-sized chunking."""
    if len(phases) <= 8:
        return phases

    target_count = 6
    chunk_size = max(1, len(phases) // target_count)
    condensed = []

    for i in range(0, len(phases), chunk_size):
        chunk = phases[i:i + chunk_size]

        # Dominant type by step_count
        type_counts: Dict[str, int] = {}
        for p in chunk:
            type_counts[p.primary_type] = type_counts.get(p.primary_type, 0) + p.step_count
        dominant_type = max(type_counts, key=type_counts.get)

        total_steps = sum(p.step_count for p in chunk)

        # Aggregate unique key_details (max 5)
        aggregated_details: List[str] = []
        for p in chunk:
            for d in p.key_details:
                if d not in aggregated_details:
                    aggregated_details.append(d)
                if len(aggregated_details) >= 5:
                    break
            if len(aggregated_details) >= 5:
                break

        condensed.append(ProcessPhase(
            phase_name=chunk[0].phase_name,
            primary_type=dominant_type,
            step_count=total_steps,
            summary=chunk[0].summary,
            key_details=aggregated_details,
        ))

    return condensed


def ai_summarize_phases(steps: List[ProcessStep]) -> Optional[List[ProcessPhase]]:
    """Use Claude CLI to summarize steps into 5-8 meaningful phases."""
    if shutil.which("claude") is None:
        logger.info("Claude CLI not available, using algorithmic grouping")
        return None

    prompt = build_summarization_prompt(steps)

    try:
        result = subprocess.run(
            ["claude", "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning(f"Claude CLI failed: {result.stderr[:200]}")
            return None

        return parse_ai_phases(result.stdout.strip())
    except subprocess.TimeoutExpired:
        logger.warning("Claude CLI timed out for phase summarization")
        return None
    except Exception as e:
        logger.warning(f"Claude CLI error: {e}")
        return None


def build_summarization_prompt(steps: List[ProcessStep]) -> str:
    """Build prompt for AI phase summarization."""
    # Limit to first 100 steps to avoid overly long prompts
    display_steps = steps[:100]
    step_lines = []
    for i, step in enumerate(display_steps, 1):
        if isinstance(step, ProcessStep):
            step_lines.append(f"{i}. [{step.type}] {step.summary}")
        else:
            step_lines.append(f"{i}. [analysis] {step}")

    if len(steps) > 100:
        step_lines.append(f"... (총 {len(steps)}개 중 처음 100개만 표시)")

    steps_text = "\n".join(step_lines)

    return f"""다음은 하나의 Claude 작업 세션에서 추출된 {len(steps)}개의 작업 단계입니다.
이 단계들을 5~8개의 의미 있는 작업 페이즈(phase)로 그룹화해주세요.

각 페이즈는 반드시 다음 형식으로 출력해주세요:
PHASE: [페이즈 이름]
TYPE: [analysis|decision|implementation|verification|summary]
STEPS: [시작번호]-[끝번호]
SUMMARY: [이 페이즈에서 한 일을 한 문장으로 요약]
DETAILS:
- [핵심 세부사항 1]
- [핵심 세부사항 2]
- [핵심 세부사항 3]
---

규칙:
- 반드시 5~8개의 페이즈로 그룹화
- 각 페이즈 사이에 "---"를 넣어주세요
- TYPE은 반드시 analysis, decision, implementation, verification, summary 중 하나
- STEPS는 시작번호와 끝번호를 하이픈으로 연결
- DETAILS는 최대 3개

작업 단계:
{steps_text}"""


def parse_ai_phases(response: str) -> Optional[List[ProcessPhase]]:
    """Parse structured AI response into ProcessPhase objects."""
    phases = []
    blocks = response.split("---")

    valid_types = {"analysis", "decision", "implementation", "verification", "summary"}

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        phase_match = re.search(r"PHASE:\s*(.+)", block)
        type_match = re.search(r"TYPE:\s*(\w+)", block)
        steps_match = re.search(r"STEPS:\s*(\d+)\s*-\s*(\d+)", block)
        summary_match = re.search(r"SUMMARY:\s*(.+)", block)

        if not all([phase_match, type_match, steps_match, summary_match]):
            continue

        phase_type = type_match.group(1).strip().lower()
        if phase_type not in valid_types:
            phase_type = "analysis"

        start_idx = int(steps_match.group(1))
        end_idx = int(steps_match.group(2))
        step_count = max(end_idx - start_idx + 1, 1)

        details = re.findall(r"^- (.+)$", block, re.MULTILINE)

        phases.append(ProcessPhase(
            phase_name=phase_match.group(1).strip(),
            primary_type=phase_type,
            step_count=step_count,
            summary=summary_match.group(1).strip(),
            key_details=details[:5],
        ))

    if len(phases) < 3 or len(phases) > 12:
        logger.warning(f"AI returned {len(phases)} phases (expected 3-12), falling back")
        return None

    return phases


# ===== Phase cache =====

def get_steps_hash(steps: List[ProcessStep]) -> str:
    content = "|".join(
        f"{s.type}:{s.summary[:50]}" if isinstance(s, ProcessStep) else str(s)[:50]
        for s in steps
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def load_cached_phases(steps_hash: str) -> Optional[List[ProcessPhase]]:
    cache_path = Path("summaries/.phase_cache.json")
    if not cache_path.exists():
        return None
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if steps_hash in cache:
            return [ProcessPhase(**p) for p in cache[steps_hash]]
    except Exception:
        pass
    return None


def save_cached_phases(steps_hash: str, phases: List[ProcessPhase]):
    cache_path = Path("summaries/.phase_cache.json")
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    except Exception:
        cache = {}
    cache[steps_hash] = [p.to_dict() for p in phases]
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to save phase cache: {e}")
