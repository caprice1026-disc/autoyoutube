from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    message: str
    location: str | None = None
    details: str | None = None
    next_step: str | None = None

    def __str__(self) -> str:
        return self.message

    def to_cli_text(self) -> str:
        lines = [f"Error: {self.message}"]
        if self.location:
            lines.append(f"Location: {self.location}")
        if self.details:
            lines.append(f"Details: {self.details}")
        if self.next_step:
            lines.append(f"Next step: {self.next_step}")
        return "\n".join(lines)
