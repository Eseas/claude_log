"""Context inference for prompt optimization."""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import re


class ContextInferrer:
    """Infer context from current project state."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize context inferrer.

        Args:
            project_root: Project root directory (defaults to cwd)
        """
        self.project_root = project_root or Path.cwd()

    def get_context(self) -> Dict:
        """Get full context for prompt optimization.

        Returns:
            Dictionary with context information
        """
        return {
            "recent_files": self.get_recent_modified_files(),
            "current_branch": self.get_git_branch(),
            "last_error": self.get_last_error(),
            "modified_files": self.get_modified_files(),
        }

    def get_recent_modified_files(self, limit: int = 10) -> List[str]:
        """Get recently modified files from filesystem (mtime).

        Args:
            limit: Maximum number of files to return

        Returns:
            List of file paths (relative to project root)
        """
        # Code file extensions to track
        code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.vue', '.java', '.go', '.rs', '.rb', '.php'}

        # Directories to exclude
        exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next'}

        try:
            files_with_mtime = []

            for file_path in self.project_root.rglob('*'):
                # Skip directories
                if not file_path.is_file():
                    continue

                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in exclude_dirs):
                    continue

                # Only include code files
                if file_path.suffix not in code_extensions:
                    continue

                # Get relative path and mtime
                try:
                    rel_path = file_path.relative_to(self.project_root)
                    mtime = file_path.stat().st_mtime
                    files_with_mtime.append((str(rel_path), mtime))
                except (OSError, ValueError):
                    continue

            # Sort by modification time (newest first)
            files_with_mtime.sort(key=lambda x: x[1], reverse=True)

            # Return only file paths
            return [path for path, _ in files_with_mtime[:limit]]

        except Exception:
            return []

    def get_modified_files(self) -> List[str]:
        """Get currently modified files (git status).

        Returns:
            List of modified file paths
        """
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                files = []
                for line in result.stdout.split('\n'):
                    if line.strip():
                        # Parse git status format: " M file.py"
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) == 2:
                            files.append(parts[1])
                return files
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return []

    def get_git_branch(self) -> Optional[str]:
        """Get current git branch.

        Returns:
            Branch name or None
        """
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def get_last_error(self) -> Optional[str]:
        """Get last error from log files (if any).

        Returns:
            Last error message or None
        """
        # Look for common log files
        log_patterns = [
            "*.log",
            "organizer.log",
            "error.log",
        ]

        for pattern in log_patterns:
            for log_file in self.project_root.glob(pattern):
                try:
                    content = log_file.read_text(encoding='utf-8')
                    # Find last ERROR or Exception
                    errors = re.findall(r'(ERROR|Exception).*', content)
                    if errors:
                        return errors[-1][:200]  # Last 200 chars
                except Exception:
                    continue

        return None

    def infer_file_from_keywords(self, keywords: List[str]) -> Optional[str]:
        """Infer file path from keywords.

        Args:
            keywords: List of keywords from user input

        Returns:
            Inferred file path or None
        """
        context = self.get_context()
        all_files = context["recent_files"] + context["modified_files"]

        # Score files by keyword matches
        scores = {}
        for file_path in all_files:
            score = 0
            file_lower = file_path.lower()

            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in file_lower:
                    score += 10
                # Partial match
                elif any(k in file_lower for k in keyword_lower.split('_')):
                    score += 5

            if score > 0:
                scores[file_path] = score

        # Return highest scoring file
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]

        return None

    def find_function_in_file(self, file_path: str, keyword: str) -> Optional[int]:
        """Find line number of function matching keyword.

        Args:
            file_path: Path to file
            keyword: Keyword to search for

        Returns:
            Line number or None
        """
        try:
            full_path = self.project_root / file_path
            if not full_path.exists():
                return None

            content = full_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            keyword_lower = keyword.lower()

            for i, line in enumerate(lines, 1):
                line_lower = line.lower()
                # Match function/method definitions
                if re.search(r'(def|function|class)\s+\w*' + re.escape(keyword_lower), line_lower):
                    return i
                # Match if keyword is in line
                if keyword_lower in line_lower:
                    return i

        except Exception:
            pass

        return None
