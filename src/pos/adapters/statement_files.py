import csv
import io
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from pos.application.ports import StatementEntry, StatementSource, StatementSourceError

_DELIMITERS = (",", ";", "\t")


@dataclass(frozen=True)
class StatementRow:
    source: str
    student: str
    scores: tuple[tuple[str, str], ...]


class StatementFile(ABC):
    def read(self, path: Path) -> list[StatementEntry]:
        text = _read_text(path)
        return [
            StatementEntry(row.source, row.student, criterion, points.strip())
            for row in self._rows(text)
            for criterion, points in row.scores
            if points.strip()
        ]

    @abstractmethod
    def _rows(self, text: str) -> Iterable[StatementRow]: ...


class CsvStatementFile(StatementFile):
    def _rows(self, text: str) -> list[StatementRow]:
        lines = [
            (number, row)
            for number, row in enumerate(self._table(text), 1)
            if any(cell.strip() for cell in row)
        ]
        if not lines:
            raise StatementSourceError("ведомость пуста")
        _, header = lines[0]
        criteria = _criteria_from_header(header)
        rows = []
        for number, cells in lines[1:]:
            if len(cells) > len(header):
                raise StatementSourceError(f"строка {number}: значений больше, чем столбцов")
            values = [*cells[1:], *[""] * (len(header) - len(cells))]
            rows.append(
                StatementRow(
                    f"строка {number}", cells[0], tuple(zip(criteria, values, strict=True))
                )
            )
        return rows

    def _table(self, text: str) -> list[list[str]]:
        header = text.lstrip().partition("\n")[0]
        delimiter = max(_DELIMITERS, key=header.count)
        try:
            return list(csv.reader(io.StringIO(text), delimiter=delimiter))
        except csv.Error as error:
            raise StatementSourceError(f"некорректный CSV: {error}") from None


class JsonStatementFile(StatementFile):
    def _rows(self, text: str) -> list[StatementRow]:
        try:
            document = json.loads(text, parse_float=str, parse_int=str, parse_constant=str)
        except json.JSONDecodeError as error:
            raise StatementSourceError(
                f"некорректный JSON: строка {error.lineno}, позиция {error.colno}"
            ) from None
        records = document.get("students") if isinstance(document, dict) else None
        if not isinstance(records, list):
            raise StatementSourceError("ожидается JSON-объект с массивом students")
        return [_json_row(f"студент {number}", record) for number, record in enumerate(records, 1)]


class FileStatementSource(StatementSource):
    def __init__(self) -> None:
        self._formats: Mapping[str, StatementFile] = {
            ".csv": CsvStatementFile(),
            ".json": JsonStatementFile(),
        }

    def read(self, location: str) -> list[StatementEntry]:
        path = Path(location)
        statement = self._formats.get(path.suffix.lower())
        if statement is None:
            raise StatementSourceError("ведомость должна быть в формате .csv или .json")
        return statement.read(path)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise StatementSourceError(f"файл не найден: {path}") from None
    except OSError:
        raise StatementSourceError(f"не удалось прочитать файл: {path}") from None
    except UnicodeDecodeError:
        raise StatementSourceError("файл должен быть в кодировке UTF-8") from None


def _criteria_from_header(header: list[str]) -> list[str]:
    criteria = [cell.strip() for cell in header[1:]]
    if not criteria:
        raise StatementSourceError("в заголовке нужен столбец студента и хотя бы один критерий")
    if not all(criteria):
        raise StatementSourceError("в заголовке есть столбец без названия критерия")
    if len({name.casefold() for name in criteria}) != len(criteria):
        raise StatementSourceError("в заголовке критерии повторяются")
    return criteria


def _json_row(source: str, record: object) -> StatementRow:
    if not isinstance(record, dict):
        raise StatementSourceError(f"{source}: ожидается объект с полями name и scores")
    name = record.get("name")
    scores = record.get("scores")
    if not isinstance(name, str) or not isinstance(scores, dict):
        raise StatementSourceError(f"{source}: ожидается объект с полями name и scores")
    pairs = []
    for criterion, points in scores.items():
        if points is None:
            continue
        if not isinstance(points, str):
            raise StatementSourceError(f"{source}: балл по «{criterion}» должен быть числом")
        pairs.append((criterion, points))
    return StatementRow(source, name, tuple(pairs))
