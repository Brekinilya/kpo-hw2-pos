from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from pos.application.views import GradeSheet


@dataclass(frozen=True)
class StatementEntry:
    source: str
    student: str
    criterion: str
    points: str


class StatementSourceError(Exception):
    pass


class StatementSource(ABC):
    @abstractmethod
    def read(self, location: str) -> Sequence[StatementEntry]: ...


class ExportError(Exception):
    pass


class GradeSheetExporter(ABC):
    @abstractmethod
    def export(self, location: str, sheet: GradeSheet) -> None: ...
