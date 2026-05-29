"""Task success/failure analyzer using heuristic signals and AI judgment."""

import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from claude_log_organizer.models.task_data import TaskInteraction
from claude_log_organizer.signals import SignalRegistry, get_default_registry


class TaskSuccessAnalyzer:
    """Analyzes task interactions to determine success/failure."""

    def __init__(self, signals: Optional[SignalRegistry] = None):
        """Initialize with a signal registry (defaults to bundled signals.yaml)."""
        self.signals = signals or get_default_registry()

    def extract_interactions(self, log_content: str) -> List[TaskInteraction]:
        """Extract ordered task interactions from a log file content.

        Splits content by [USER] boundaries and pairs each request
        with the assistant's work and the next user message (feedback).
        """
        # Split content into segments by [USER] tags
        # Each segment: [USER] message + subsequent [ASSISTANT]/[TOOL]/[THINKING] blocks
        segments = re.split(r'(?=\[USER\])', log_content)
        segments = [s for s in segments if s.strip() and '[USER]' in s]

        interactions = []
        for i, segment in enumerate(segments):
            # Extract user message
            user_match = re.search(r'\[USER\]\s*(.+?)(?=\n\[(?:THINKING|ASSISTANT|TOOL|TOOL_RESULT|DOCUMENT|SNAPSHOT|COMPACT|USAGE)\]|\n=|$)', segment, re.DOTALL)
            if not user_match:
                continue

            user_msg = user_match.group(1).strip()
            if len(user_msg) < 5:
                continue

            # Filter out non-user messages (system events, tool results, IDE events)
            skip_patterns = [
                r'^\[TOOL_RESULT\]',
                r'^<ide_',
                r'^\[Request interrupted',
                r'^<system',
                r'^This session is being continued from a previous',
                r'^\s*$',
            ]
            if any(re.match(p, user_msg) for p in skip_patterns):
                continue

            # Extract assistant responses in this segment
            assistant_responses = []
            for m in re.finditer(r'\[ASSISTANT\]\s*(.+?)(?=\n\[(?:USER|TOOL|ASSISTANT|THINKING|TOOL_RESULT|DOCUMENT|SNAPSHOT|COMPACT|USAGE)\]|\n=|$)', segment, re.DOTALL):
                resp = m.group(1).strip()
                if resp and len(resp) > 10:
                    assistant_responses.append(resp)

            # Extract tools used
            tools = []
            for m in re.finditer(r'\[TOOL\]\s*(\w+)\s*→\s*(.+?)(?=\n\[|\n\n|$)', segment, re.DOTALL):
                tools.append({'tool': m.group(1).strip(), 'action': m.group(2).strip()})

            # Extract tool results
            tool_results = []
            for m in re.finditer(r'\[TOOL_RESULT\]\s*(.+?)(?=\n\[(?:USER|TOOL|ASSISTANT|THINKING|TOOL_RESULT|DOCUMENT|SNAPSHOT|COMPACT|USAGE)\]|\n=|$)', segment, re.DOTALL):
                result = m.group(1).strip()
                if result:
                    tool_results.append(result[:300])

            # Get feedback (next real user message)
            feedback = None
            for j in range(i + 1, len(segments)):
                next_match = re.search(r'\[USER\]\s*(.+?)(?=\n\[|\n=|$)', segments[j], re.DOTALL)
                if next_match:
                    fb = next_match.group(1).strip()
                    if len(fb) > 3 and not any(re.match(p, fb) for p in skip_patterns):
                        feedback = fb
                        break

            interaction = TaskInteraction(
                request=user_msg,
                assistant_work=assistant_responses,
                tools_used=tools,
                tool_results=tool_results,
                feedback=feedback,
            )
            interactions.append(interaction)

        return interactions

    def extract_interactions_from_file(self, file_path: Path) -> List[TaskInteraction]:
        """Extract interactions from a log file."""
        content = file_path.read_text(encoding='utf-8', errors='replace')
        return self.extract_interactions(content)

    # ============================================================
    # Heuristic Analysis
    # ============================================================

    def analyze_heuristic(self, interactions: List[TaskInteraction]) -> List[TaskInteraction]:
        """Run heuristic signal analysis on all interactions."""
        for interaction in interactions:
            self._analyze_single_heuristic(interaction)
        return interactions

    def _analyze_single_heuristic(self, interaction: TaskInteraction):
        """Analyze a single interaction using heuristic signals."""
        if interaction.feedback is None:
            interaction.heuristic_result = "unknown"
            interaction.heuristic_confidence = 0.0
            interaction.heuristic_signals = ["마지막 메시지 (후속 피드백 없음)"]
            return

        feedback = interaction.feedback
        failure_score = 0.0
        success_score = 0.0
        signals = []

        # Check failure signals in feedback
        for sig in self.signals.failure_signals:
            if sig.pattern.search(feedback):
                failure_score += sig.weight
                signals.append(f"[실패 시그널] {sig.label}: /{sig.pattern.pattern}/")

        # Check success signals in feedback
        for sig in self.signals.success_signals:
            if sig.pattern.search(feedback):
                success_score += sig.weight
                signals.append(f"[성공 시그널] {sig.label}: /{sig.pattern.pattern}/")

        # Check tool results for errors
        for result in interaction.tool_results:
            for sig in self.signals.tool_error_signals:
                if sig.pattern.search(result):
                    failure_score += sig.weight * 0.5  # Lower weight for tool errors
                    signals.append(f"[도구 에러] {sig.label}")
                    break

        # Check if feedback is a topic change (success indicator)
        if self._is_topic_change(interaction.request, feedback):
            success_score += 0.4
            signals.append("[성공 시그널] 주제 전환 감지")

        # Check if feedback repeats the request (failure indicator)
        similarity = self._text_similarity(interaction.request, feedback)
        if similarity > 0.5:
            failure_score += 0.6
            signals.append(f"[실패 시그널] 유사 요청 반복 (유사도: {similarity:.0%})")

        # Determine result
        total = failure_score + success_score
        if total == 0:
            interaction.heuristic_result = "unknown"
            interaction.heuristic_confidence = 0.0
            signals.append("[판단 불가] 시그널 없음")
        elif failure_score > success_score:
            interaction.heuristic_result = "failure"
            interaction.heuristic_confidence = min(failure_score / max(total, 1), 1.0)
        elif success_score > failure_score:
            interaction.heuristic_result = "success"
            interaction.heuristic_confidence = min(success_score / max(total, 1), 1.0)
        else:
            interaction.heuristic_result = "partial"
            interaction.heuristic_confidence = 0.5

        interaction.heuristic_signals = signals

    def _is_topic_change(self, request: str, feedback: str) -> bool:
        """Detect if feedback introduces a completely different topic."""
        req_keywords = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', request.lower()))
        fb_keywords = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', feedback.lower()))

        if not req_keywords or not fb_keywords:
            return False

        overlap = len(req_keywords & fb_keywords) / max(len(req_keywords), 1)
        return overlap < 0.15

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple keyword-based similarity between two texts."""
        words1 = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text1.lower()))
        words2 = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    # ============================================================
    # AI-based Analysis
    # ============================================================

    def analyze_ai(self, interactions: List[TaskInteraction]) -> List[TaskInteraction]:
        """Run AI-based analysis on interactions using Claude CLI."""
        if not shutil.which("claude"):
            for interaction in interactions:
                interaction.ai_result = "unknown"
                interaction.ai_reasoning = "Claude CLI를 찾을 수 없습니다"
            return interactions

        # Build batch prompt for all interactions with feedback
        analyzable = [(i, inter) for i, inter in enumerate(interactions) if inter.feedback]

        if not analyzable:
            return interactions

        prompt = self._build_ai_prompt(analyzable)

        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json"],
                capture_output=True, text=True, timeout=120,
            )

            if result.returncode != 0:
                for _, inter in analyzable:
                    inter.ai_result = "unknown"
                    inter.ai_reasoning = f"Claude CLI 실행 실패: {result.stderr[:200]}"
                return interactions

            # Parse JSON output
            output = json.loads(result.stdout)
            response_text = output.get("result", "")

            # Extract JSON block from response
            json_match = re.search(r'\[[\s\S]*?\]', response_text)
            if json_match:
                ai_results = json.loads(json_match.group())
                for (idx, inter), ai_item in zip(analyzable, ai_results):
                    inter.ai_result = ai_item.get("result", "unknown")
                    inter.ai_confidence = ai_item.get("confidence", 0.0)
                    inter.ai_reasoning = ai_item.get("reasoning", "")
            else:
                for _, inter in analyzable:
                    inter.ai_result = "unknown"
                    inter.ai_reasoning = "AI 응답에서 JSON 파싱 실패"

        except subprocess.TimeoutExpired:
            for _, inter in analyzable:
                inter.ai_result = "unknown"
                inter.ai_reasoning = "Claude CLI 타임아웃"
        except (json.JSONDecodeError, KeyError) as e:
            for _, inter in analyzable:
                inter.ai_result = "unknown"
                inter.ai_reasoning = f"응답 파싱 에러: {e}"

        return interactions

    def _build_ai_prompt(self, analyzable: List[Tuple[int, TaskInteraction]]) -> str:
        """Build a prompt for Claude to analyze task success/failure."""
        items = []
        for idx, (_, inter) in enumerate(analyzable):
            assistant_summary = "\n".join(inter.assistant_work[:3])[:500]
            tools_summary = ", ".join(t['tool'] for t in inter.tools_used[:10])

            items.append(
                f"### Interaction {idx + 1}\n"
                f"**User Request**: {inter.request[:300]}\n"
                f"**Assistant Work**: {assistant_summary}\n"
                f"**Tools Used**: {tools_summary or 'none'}\n"
                f"**Next User Message**: {inter.feedback[:300]}\n"
            )

        interactions_text = "\n---\n".join(items)

        return f"""다음은 Claude Code 세션에서 추출한 사용자-어시스턴트 상호작용 목록입니다.
각 상호작용에 대해 "Next User Message"를 분석하여 이전 작업이 성공했는지 실패했는지 판단해주세요.

판단 기준:
- 사용자가 새로운 주제로 넘어가거나, 긍정적 반응을 보이면 → success
- 사용자가 같은 요청을 반복하거나, 수정을 요구하거나, 불만을 표시하면 → failure
- 부분적으로 성공했지만 추가 수정이 필요한 경우 → partial
- 판단이 어려운 경우 → unknown

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요:
[
  {{"result": "success|failure|partial|unknown", "confidence": 0.0~1.0, "reasoning": "한 줄 설명"}}
]

---

{interactions_text}"""

    # ============================================================
    # Full analysis pipeline
    # ============================================================

    def analyze_log_file(self, file_path: Path, use_ai: bool = True) -> List[TaskInteraction]:
        """Full analysis pipeline for a single log file."""
        interactions = self.extract_interactions_from_file(file_path)
        self.analyze_heuristic(interactions)
        if use_ai:
            self.analyze_ai(interactions)
        return interactions

    def analyze_log_files(self, file_paths: List[Path], use_ai: bool = True) -> List[TaskInteraction]:
        """Analyze multiple log files."""
        all_interactions = []
        for fp in file_paths:
            try:
                interactions = self.analyze_log_file(fp, use_ai=use_ai)
                all_interactions.extend(interactions)
            except Exception:
                continue
        return all_interactions

    # ============================================================
    # Report generation
    # ============================================================

    def generate_report(self, interactions: List[TaskInteraction]) -> List[str]:
        """Generate markdown report lines from analyzed interactions."""
        if not interactions:
            return ["분석 가능한 상호작용이 없습니다."]

        lines = [
            "## Task Success/Failure Analysis",
            "",
        ]

        # --- Summary stats ---
        analyzed = [i for i in interactions if i.feedback]
        total = len(analyzed)

        if total == 0:
            lines.append("피드백이 있는 상호작용이 없어 분석할 수 없습니다.")
            return lines

        # Heuristic stats
        h_success = sum(1 for i in analyzed if i.heuristic_result == "success")
        h_failure = sum(1 for i in analyzed if i.heuristic_result == "failure")
        h_partial = sum(1 for i in analyzed if i.heuristic_result == "partial")
        h_unknown = sum(1 for i in analyzed if i.heuristic_result == "unknown")

        # AI stats
        has_ai = any(i.ai_result and i.ai_result != "unknown" for i in analyzed)
        a_success = sum(1 for i in analyzed if i.ai_result == "success")
        a_failure = sum(1 for i in analyzed if i.ai_result == "failure")
        a_partial = sum(1 for i in analyzed if i.ai_result == "partial")
        a_unknown = sum(1 for i in analyzed if i.ai_result in ("unknown", None))

        # --- Overview ---
        lines.append("### Overview")
        lines.append(f"- **총 상호작용**: {len(interactions)}개 (피드백 있음: {total}개)")
        lines.append("")

        h_rate = (h_success / total * 100) if total > 0 else 0
        lines.append(f"| 구분 | Success | Failure | Partial | Unknown | 성공률 |")
        lines.append(f"|------|---------|---------|---------|---------|--------|")
        lines.append(
            f"| **시그널 분석** | {h_success} | {h_failure} | {h_partial} | {h_unknown} "
            f"| {h_rate:.0f}% |"
        )
        if has_ai:
            a_rate = (a_success / total * 100) if total > 0 else 0
            lines.append(
                f"| **AI 분석** | {a_success} | {a_failure} | {a_partial} | {a_unknown} "
                f"| {a_rate:.0f}% |"
            )
        lines.append("")

        # --- Heuristic detail ---
        lines.append("### Signal-based Analysis (시그널 기반)")
        lines.append("")

        for idx, inter in enumerate(interactions, 1):
            if not inter.feedback:
                continue

            result_emoji = {
                "success": "✅", "failure": "❌", "partial": "⚠️", "unknown": "❓"
            }.get(inter.heuristic_result, "❓")

            conf = inter.heuristic_confidence
            request_preview = inter.request[:80] + ("..." if len(inter.request) > 80 else "")
            feedback_preview = inter.feedback[:80] + ("..." if len(inter.feedback) > 80 else "")

            lines.append(f"#### {idx}. {result_emoji} {inter.heuristic_result} (확신도: {conf:.0%})")
            lines.append(f"- **요청**: {request_preview}")
            lines.append(f"- **피드백**: {feedback_preview}")
            if inter.heuristic_signals:
                lines.append(f"- **시그널**:")
                for sig in inter.heuristic_signals:
                    lines.append(f"  - {sig}")
            lines.append("")

        # --- AI detail ---
        if has_ai:
            lines.append("### AI-based Analysis (AI 기반)")
            lines.append("")

            for idx, inter in enumerate(interactions, 1):
                if not inter.feedback or not inter.ai_result:
                    continue

                result_emoji = {
                    "success": "✅", "failure": "❌", "partial": "⚠️", "unknown": "❓"
                }.get(inter.ai_result, "❓")

                request_preview = inter.request[:80] + ("..." if len(inter.request) > 80 else "")

                lines.append(f"#### {idx}. {result_emoji} {inter.ai_result} (확신도: {inter.ai_confidence:.0%})")
                lines.append(f"- **요청**: {request_preview}")
                lines.append(f"- **AI 판단**: {inter.ai_reasoning}")
                lines.append("")

        # --- Disagreement analysis ---
        if has_ai:
            disagreements = [
                i for i in analyzed
                if i.heuristic_result and i.ai_result
                and i.heuristic_result != i.ai_result
                and i.heuristic_result != "unknown" and i.ai_result != "unknown"
            ]

            if disagreements:
                lines.append("### Disagreements (시그널 vs AI 판단 불일치)")
                lines.append("")
                lines.append("| # | 요청 | 시그널 | AI | 시그널 근거 | AI 근거 |")
                lines.append("|---|------|--------|-----|------------|---------|")

                for inter in disagreements:
                    idx = interactions.index(inter) + 1
                    req = inter.request[:40] + "..." if len(inter.request) > 40 else inter.request
                    h_sig = inter.heuristic_signals[0] if inter.heuristic_signals else "-"
                    lines.append(
                        f"| {idx} | {req} | {inter.heuristic_result} "
                        f"| {inter.ai_result} | {h_sig} | {inter.ai_reasoning[:50]} |"
                    )
                lines.append("")

        return lines
