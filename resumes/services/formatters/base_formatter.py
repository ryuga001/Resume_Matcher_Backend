from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ResumeFormatter(ABC):
    """Strategy interface — every concrete formatter converts structured resume data to bytes."""

    @abstractmethod
    def format(self, data: dict[str, Any]) -> bytes:
        ...

    @property
    @abstractmethod
    def content_type(self) -> str:
        ...

    @property
    @abstractmethod
    def extension(self) -> str:
        ...
