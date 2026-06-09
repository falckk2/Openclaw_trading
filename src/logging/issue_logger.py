"""Issue logger — writes issues to issues.md in standardized format."""

import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Literal

IssueStatus = Literal["Open", "In Progress", "Resolved", "Deferred"]
IssueSeverity = Literal["Critical", "High", "Medium", "Low", "Info"]


@dataclass
class Issue:
    """A tracked issue or task."""
    title: str
    status: IssueStatus
    severity: IssueSeverity
    agent: str
    location: str
    description: str
    root_cause: str | None = None
    resolution: str | None = None
    notes: str | None = None


from dataclasses import dataclass as dataclass_func


class IssueLogger:
    """
    Logs and tracks issues in issues.md.
    Each agent writes to issues.md with standardized format.
    """

    ISSUE_FILE = "issues.md"
    AGENTS = ["Architect", "Engineer", "BugFinder", "Debugger", "Tester"]

    def __init__(self, issues_file: Path | str | None = None):
        self._path = Path(issues_file) if issues_file else Path(self.ISSUE_FILE)

    def log_issue(self, issue: Issue) -> None:
        """Append an issue to the issues.md file."""
        issue_id = self._get_next_issue_id()
        entry = self._format_issue(issue_id, issue)
        self._append_to_file(entry)

    def resolve_issue(self, issue_id: str, resolution: str) -> None:
        """Mark an issue as resolved with the resolution text."""
        self._update_issue_status(issue_id, "Resolved", resolution=resolution)

    def get_open_issues(self) -> list[dict]:
        """Parse issues.md and return list of open issues."""
        if not self._path.exists():
            return []

        content = self._path.read_text()
        issues = []

        # Simple parsing — find all issue blocks
        pattern = r"## \[ISSUE-(\d+)\] (.+?)\n- \*\*Status:\*\* ([^\n]+)\n- \*\*Severity:\*\* ([^\n]+)\n- \*\*Agent:\*\* ([^\n]+)\n- \*\*Created:\*\* ([^\n]+)\n- \*\*Location:\*\* ([^\n]+)\n- \*\*Description:\*\* ([^\n]+)"
        for match in re.finditer(pattern, content, re.DOTALL):
            issue_id, title, status, severity, agent, created, location, description = match.groups()
            if status.strip() in ("Open", "In Progress"):
                issues.append({
                    "id": f"ISSUE-{issue_id}",
                    "title": title.strip(),
                    "status": status.strip(),
                    "severity": severity.strip(),
                    "agent": agent.strip(),
                    "created": created.strip(),
                    "location": location.strip(),
                    "description": description.strip(),
                })
        return issues

    def _get_next_issue_id(self) -> int:
        """Find the next available issue number."""
        if not self._path.exists():
            return 1
        content = self._path.read_text()
        ids = [int(m) for m in re.findall(r"ISSUE-(\d+)", content)]
        return max(ids) + 1 if ids else 1

    def _format_issue(self, issue_id: int, issue: Issue) -> str:
        """Format an issue as a markdown block."""
        root_cause = f"\n- **Root Cause:** {issue.root_cause}" if issue.root_cause else ""
        resolution = f"\n- **Resolution:** {issue.resolution}" if issue.resolution else ""
        notes = f"\n- **Notes:** {issue.notes}" if issue.notes else ""

        return f"""
## [ISSUE-{issue_id:03d}] {issue.title}
- **Status:** {issue.status}
- **Severity:** {issue.severity}
- **Agent:** {issue.agent}
- **Created:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}
- **Location:** {issue.location}
- **Description:** {issue.description}{root_cause}{resolution}{notes}
"""

    def _append_to_file(self, entry: str) -> None:
        """Append entry to the open issues section."""
        if not self._path.exists():
            return

        content = self._path.read_text()
        # Insert before "## Resolved Issues" or at end
        if "## Resolved Issues" in content:
            content = content.replace("## Resolved Issues", entry + "\n## Resolved Issues")
        else:
            content = content.replace("\n---\n\n## Open Issues\n\n\n", f"\n---\n\n## Open Issues\n\n{entry}\n")
        self._path.write_text(content)

    def _update_issue_status(self, issue_id: str, status: str, resolution: str | None = None) -> None:
        """Update status and optionally resolution of an issue."""
        if not self._path.exists():
            return

        content = self._path.read_text()
        # Find and replace status line
        pattern = rf"## \[{issue_id}\] (.+?)\n(- \*\*Status:\*\* ).+?\n"
        replacement = rf"## [{issue_id}] \1\n\2{status}\n"
        content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)

        if resolution:
            res_line = f"\n- **Resolution:** {resolution}"
            # Find the issue block and add resolution
            issue_pattern = rf"## \[{issue_id}\].*?(?=\n## \[|$)"
            match = re.search(issue_pattern, content, re.DOTALL)
            if match:
                block = match.group(0)
                if "- **Resolution:**" not in block:
                    block = block.rstrip() + res_line + "\n"
                    content = content[:match.start()] + block + content[match.end():]

        self._path.write_text(content)