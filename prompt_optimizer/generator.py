"""Prompt generator for optimization."""

import re
from pathlib import Path
from typing import Optional, Dict, List
from .context import ContextInferrer


class PromptGenerator:
    """Generate optimized prompts from user input."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize prompt generator.

        Args:
            project_root: Project root directory
        """
        self.context = ContextInferrer(project_root)

    def generate(self, user_input: str, include_original: bool = True) -> str:
        """Generate optimized prompt from user input.

        Args:
            user_input: User's original input
            include_original: Whether to include original input

        Returns:
            Optimized prompt
        """
        # Extract keywords
        keywords = self._extract_keywords(user_input)

        # Detect request type
        request_type = self._detect_request_type(user_input)

        # Generate based on type
        if request_type == "bug_fix":
            optimized = self._generate_bug_fix_prompt(user_input, keywords)
        elif request_type == "feature_add":
            optimized = self._generate_feature_prompt(user_input, keywords)
        elif request_type == "investigation":
            optimized = self._generate_investigation_prompt(user_input, keywords)
        else:
            optimized = self._generate_generic_prompt(user_input, keywords)

        # Add original if requested
        if include_original:
            return f"{optimized}\n\n---\n### 원본 요청\n{user_input}"
        else:
            return optimized

    def _extract_keywords(self, user_input: str) -> List[str]:
        """Extract keywords from user input.

        Args:
            user_input: User's input

        Returns:
            List of keywords
        """
        # Common words to ignore
        stop_words = {
            '이', '그', '저', '것', '수', '등', '및', '를', '을', '가', '이',
            '에서', '으로', '부터', '까지', '확인', '해주세요', '부탁', '합니다'
        }

        # Extract words
        words = re.findall(r'\w+', user_input.lower())

        # Filter stop words
        keywords = [w for w in words if w not in stop_words and len(w) > 1]

        return keywords

    def _detect_request_type(self, user_input: str) -> str:
        """Detect type of request.

        Args:
            user_input: User's input

        Returns:
            Request type: bug_fix, feature_add, investigation, or generic
        """
        user_lower = user_input.lower()

        # Bug fix indicators
        bug_keywords = ['버그', '오류', '에러', 'error', '안됨', '작동', '이상', '문제']
        if any(k in user_lower for k in bug_keywords):
            return "bug_fix"

        # Feature add indicators
        feature_keywords = ['추가', '만들', '생성', '구현', '기능', 'add', 'create', 'implement']
        if any(k in user_lower for k in feature_keywords):
            return "feature_add"

        # Investigation indicators
        investigation_keywords = ['확인', '조사', '파악', '분석', '어떻게', '왜', 'check', 'investigate']
        if any(k in user_lower for k in investigation_keywords):
            return "investigation"

        return "generic"

    def _generate_bug_fix_prompt(self, user_input: str, keywords: List[str]) -> str:
        """Generate bug fix prompt.

        Args:
            user_input: User's input
            keywords: Extracted keywords

        Returns:
            Optimized prompt
        """
        # Infer file
        file_path = self.context.infer_file_from_keywords(keywords)

        # Try to find function
        line_num = None
        if file_path:
            for keyword in keywords:
                line_num = self.context.find_function_in_file(file_path, keyword)
                if line_num:
                    break

        # Build prompt
        parts = []

        # File and line
        if file_path:
            if line_num:
                parts.append(f"{file_path}:{line_num}")
            else:
                parts.append(f"{file_path}")

        # Issue
        issue = self._extract_issue(user_input)
        if issue:
            parts.append(f"현상: {issue}")

        # Expectation
        expectation = self._infer_expectation(user_input)
        if expectation:
            parts.append(f"기대: {expectation}")

        # Context
        ctx = self.context.get_context()
        if ctx["last_error"]:
            parts.append(f"에러: {ctx['last_error']}")

        return "\n".join(parts) if parts else user_input

    def _generate_feature_prompt(self, user_input: str, keywords: List[str]) -> str:
        """Generate feature addition prompt.

        Args:
            user_input: User's input
            keywords: Extracted keywords

        Returns:
            Optimized prompt
        """
        # Infer file
        file_path = self.context.infer_file_from_keywords(keywords)

        parts = []

        if file_path:
            parts.append(f"위치: {file_path}")

        # What to do
        action = self._extract_action(user_input)
        if action:
            parts.append(f"동작: {action}")

        # Reference pattern
        ctx = self.context.get_context()
        if ctx["recent_files"]:
            # Suggest similar file as reference
            ref_file = ctx["recent_files"][0]
            parts.append(f"참고: {ref_file} 패턴")

        return "\n".join(parts) if parts else user_input

    def _generate_investigation_prompt(self, user_input: str, keywords: List[str]) -> str:
        """Generate investigation prompt.

        Args:
            user_input: User's input
            keywords: Extracted keywords

        Returns:
            Optimized prompt
        """
        # Infer file
        file_path = self.context.infer_file_from_keywords(keywords)

        parts = []

        parts.append(f"목적: {self._extract_purpose(user_input)}")

        if file_path:
            parts.append(f"범위: {file_path}")

        # Specific question
        question = self._extract_question(user_input)
        if question:
            parts.append(f"질문: {question}")

        return "\n".join(parts) if parts else user_input

    def _generate_generic_prompt(self, user_input: str, keywords: List[str]) -> str:
        """Generate generic optimized prompt.

        Args:
            user_input: User's input
            keywords: Extracted keywords

        Returns:
            Optimized prompt
        """
        # Try to add file context
        file_path = self.context.infer_file_from_keywords(keywords)

        if file_path:
            return f"{file_path}\n{user_input}"
        else:
            return user_input

    def _extract_issue(self, user_input: str) -> str:
        """Extract issue description from user input."""
        # Remove common phrases
        issue = user_input
        for phrase in ['확인해주세요', '부탁드립니다', '해주세요']:
            issue = issue.replace(phrase, '')

        return issue.strip()

    def _infer_expectation(self, user_input: str) -> str:
        """Infer expected behavior from user input."""
        # Simple heuristics
        if '안됨' in user_input or '안 ' in user_input:
            return "정상 동작"
        if '이상' in user_input:
            return "정상 동작"

        return ""

    def _extract_action(self, user_input: str) -> str:
        """Extract action from user input."""
        return user_input.strip()

    def _extract_purpose(self, user_input: str) -> str:
        """Extract purpose from user input."""
        # Remove question words
        purpose = re.sub(r'(어떻게|왜|무엇을|확인|조사)', '', user_input)
        return purpose.strip()

    def _extract_question(self, user_input: str) -> str:
        """Extract specific question from user input."""
        # Look for question pattern
        question_match = re.search(r'(.+?)\?', user_input)
        if question_match:
            return question_match.group(1)

        return user_input.strip()

    def generate_context_only(self, user_input: str) -> str:
        """Generate only additional context (not full prompt).

        This is used by hooks to add context to user prompts
        without replacing the original prompt.

        Args:
            user_input: User's original input

        Returns:
            Additional context string
        """
        keywords = self._extract_keywords(user_input)
        request_type = self._detect_request_type(user_input)

        parts = []

        # Add file context
        file_path = self.context.infer_file_from_keywords(keywords)
        if file_path:
            parts.append(f"📍 Relevant file: {file_path}")

        # Add context based on type
        ctx = self.context.get_context()

        if request_type == "bug_fix" and ctx["last_error"]:
            parts.append(f"⚠️ Recent error: {ctx['last_error'][:100]}")

        # Add recent files (filesystem mtime)
        if ctx["recent_files"]:
            recent = ", ".join(ctx["recent_files"][:3])
            parts.append(f"📝 Recent files: {recent}")

        # Add modified files
        if ctx["modified_files"]:
            modified = ", ".join(ctx["modified_files"][:3])
            parts.append(f"✏️ Modified: {modified}")

        return "\n".join(parts) if parts else ""

    def calculate_quality(self, prompt: str) -> float:
        """Calculate quality score of generated prompt.

        Args:
            prompt: Generated prompt

        Returns:
            Quality score (0-1)
        """
        score = 0.0

        # File:line format (+0.3)
        if re.search(r'\w+\.(py|js|java|ts|vue):\d+', prompt):
            score += 0.3

        # Has "현상:" (+0.2)
        if '현상:' in prompt:
            score += 0.2

        # Has "기대:" (+0.2)
        if '기대:' in prompt:
            score += 0.2

        # Has specific function/method name (+0.3)
        if re.search(r'(def|function|class|const)\s+\w+', prompt):
            score += 0.3

        return min(score, 1.0)
