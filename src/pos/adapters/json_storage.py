import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from pos.domain.evaluation import Evaluation
from pos.domain.repositories import RubricRepository, StorageError, StudentRepository
from pos.domain.rubric import Criterion, Rubric
from pos.domain.student import Student
from pos.domain.values import CriterionId, Score, StudentId

Record = dict[str, Any]


class JsonFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def read(self, default: Any = None) -> Any:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default
        except (OSError, UnicodeDecodeError) as error:
            raise StorageError(f"не удалось прочитать {self._path}") from error
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise StorageError(f"файл {self._path} повреждён: некорректный JSON") from error

    def write(self, data: Any) -> None:
        temporary = self._path.with_name(f"{self._path.name}.tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self._path)
        except OSError as error:
            raise StorageError(f"не удалось сохранить {self._path}") from error


class JsonStudentRepository(StudentRepository):
    def __init__(self, directory: str | Path, rubrics: RubricRepository | None = None) -> None:
        self._file = JsonFile(Path(directory) / "students.json")
        self._rubrics = rubrics if rubrics is not None else JsonRubricRepository(directory)
        document = self._file.read({"last_id": 0, "students": []})
        with _reading(self._file.path):
            rubric = self._rubrics.get()
            students = [_student_from(record, rubric) for record in _array(document["students"])]
            last_id = _integer(document["last_id"])
            if last_id < 0:
                raise ValueError("счётчик ID не может быть отрицательным")
        self._records = {student.id.value: _student_record(student) for student in students}
        if len(self._records) != len(students):
            raise StorageError(f"файл {self._file.path} повреждён: ID студентов повторяются")
        self._last_id = max([last_id, *self._records])

    def next_id(self) -> StudentId:
        self._last_id += 1
        return StudentId(self._last_id)

    def find(self, student_id: StudentId) -> Student | None:
        record = self._records.get(student_id.value)
        with _reading(self._file.path):
            return None if record is None else _student_from(record, self._rubrics.get())

    def all(self) -> tuple[Student, ...]:
        with _reading(self._file.path):
            rubric = self._rubrics.get()
            return tuple(
                _student_from(record, rubric) for _, record in sorted(self._records.items())
            )

    def save(self, student: Student) -> None:
        student.validate_against(self._rubrics.get())
        self._write({**self._records, student.id.value: _student_record(student)})

    def remove(self, student_id: StudentId) -> None:
        records = dict(self._records)
        records.pop(student_id.value, None)
        self._write(records)

    def _write(self, records: dict[int, Record]) -> None:
        self._file.write(
            {"last_id": self._last_id, "students": [records[key] for key in sorted(records)]}
        )
        self._records = records


class JsonRubricRepository(RubricRepository):
    def __init__(self, directory: str | Path) -> None:
        self._file = JsonFile(Path(directory) / "rubric.json")
        document = self._file.read({"criteria": []})
        with _reading(self._file.path):
            rubric = Rubric(_criterion_from(record) for record in _array(document["criteria"]))
        self._records = [_criterion_record(criterion) for criterion in rubric.criteria]

    def get(self) -> Rubric:
        return Rubric(_criterion_from(record) for record in self._records)

    def save(self, rubric: Rubric) -> None:
        records = [_criterion_record(criterion) for criterion in rubric.criteria]
        self._file.write({"criteria": records})
        self._records = records


@contextmanager
def _reading(path: Path) -> Iterator[None]:
    try:
        yield
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
        raise StorageError(f"файл {path} повреждён") from error


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(value)
    return value


def _array(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("ожидается массив")
    return value


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str):
        raise TypeError(value)
    return Decimal(value)


def _criterion_record(criterion: Criterion) -> Record:
    return {
        "id": criterion.id.value,
        "name": criterion.name,
        "max_score": str(criterion.max_score),
        "weight": str(criterion.weight),
    }


def _criterion_from(record: Record) -> Criterion:
    return Criterion(
        CriterionId(_integer(record["id"])),
        record["name"],
        _decimal(record["max_score"]),
        _decimal(record["weight"]),
    )


def _student_record(student: Student) -> Record:
    return {
        "id": student.id.value,
        "name": student.name,
        "evaluations": [
            {
                "criterion_id": evaluation.criterion_id.value,
                "points": str(evaluation.score.points),
                "out_of": str(evaluation.score.out_of),
                "graded_on": None
                if evaluation.graded_on is None
                else evaluation.graded_on.isoformat(),
                "comment": evaluation.comment,
            }
            for evaluation in student.evaluations
        ],
    }


def _student_from(record: Record, rubric: Rubric) -> Student:
    return Student(
        StudentId(_integer(record["id"])),
        record["name"],
        [_evaluation_from(item) for item in _array(record["evaluations"])],
        rubric=rubric,
    )


def _evaluation_from(record: Record) -> Evaluation:
    graded_on = record["graded_on"]
    return Evaluation(
        CriterionId(_integer(record["criterion_id"])),
        Score(_decimal(record["points"]), _decimal(record["out_of"])),
        None if graded_on is None else date.fromisoformat(graded_on),
        record["comment"],
    )
