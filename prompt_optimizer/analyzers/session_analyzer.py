"""Session efficiency analyzer."""

import re
from pathlib import Path
from typing import Dict, List, Optional


class SessionAnalyzer:
    """Analyze session for prompt efficiency."""

    def __init__(self):
        """Initialize analyzer."""
        self.template_path = Path(__file__).parent.parent / "templates" / "efficiency_analysis.txt"

    def load_analysis_template(self) -> str:
        """Load efficiency analysis template.

        Returns:
            Template string
        """
        if not self.template_path.exists():
            # Fallback template
            return """다음은 세션 {session_id}의 로그입니다.

{full_content}

프롬프트 효율성을 분석해주세요:
1. 초기 요청 분석 (포함/부족 정보)
2. 왕복 횟수와 이유
3. 최적화된 대체 프롬프트 제안
4. 학습 포인트
"""

        return self.template_path.read_text(encoding='utf-8')

    def create_analysis_prompt(self, session_id: str, files: List[Path]) -> str:
        """Create analysis prompt for AI.

        Args:
            session_id: Session identifier
            files: List of task files in this session

        Returns:
            Analysis prompt string
        """
        # Combine all files
        combined_content = []
        combined_content.append(f"# Session: {session_id}\n")
        combined_content.append(f"파일 개수: {len(files)}\n\n")

        for file in sorted(files, key=lambda x: x.stat().st_mtime):
            combined_content.append(f"\n## 파일: {file.name}\n")
            content = file.read_text(encoding='utf-8')
            combined_content.append(content)
            combined_content.append("\n---\n")

        full_content = "\n".join(combined_content)

        # Load template
        template = self.load_analysis_template()

        # Format with session data
        prompt = template.format(
            session_id=session_id,
            full_content=full_content
        )

        return prompt

    def extract_metrics(self, task_files: List[Path]) -> Dict:
        """Extract basic metrics from task files.

        Args:
            task_files: List of task markdown files

        Returns:
            Dictionary with metrics
        """
        metrics = {
            "total_files": len(task_files),
            "total_size": sum(f.stat().st_size for f in task_files),
            "has_initial_request": False,
            "has_multiple_rounds": False,
            "response_count": 0
        }

        # Analyze first file for initial request
        if task_files:
            first_file = sorted(task_files, key=lambda x: x.stat().st_mtime)[0]
            content = first_file.read_text(encoding='utf-8')

            # Check for initial request
            if "**초기 요청**:" in content:
                metrics["has_initial_request"] = True

            # Count responses
            response_count = len(re.findall(r'\*\*응답 \d+\*\*:', content))
            metrics["response_count"] = response_count
            metrics["has_multiple_rounds"] = response_count > 3

        return metrics

    def calculate_efficiency_score(self, metrics: Dict) -> float:
        """Calculate efficiency score.

        Args:
            metrics: Metrics dictionary

        Returns:
            Score between 0-100
        """
        score = 100.0

        # Penalize multiple rounds
        if metrics["response_count"] > 3:
            score -= (metrics["response_count"] - 3) * 10

        # Penalize large file size (indicates long conversations)
        avg_size = metrics["total_size"] / max(metrics["total_files"], 1)
        if avg_size > 5000:  # More than 5KB per file
            score -= 10

        return max(0, min(100, score))
