from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pos.application.ports import StatementEntry, StatementSource
from pos.domain.errors import DomainError
from pos.domain.evaluation import EvaluationFactory
from pos.domain.repositories import RubricRepository, StudentRepository
from pos.domain.rubric import Rubric
from pos.domain.student import Student
from pos.domain.values import plain


@dataclass(frozen=True)
class ImportOutcome:
    entry: StatementEntry
    accepted: bool
    message: str


class StatementImport:
    def __init__(
        self,
        source: StatementSource,
        students: StudentRepository,
        rubrics: RubricRepository,
        factory: EvaluationFactory,
    ) -> None:
        self._source = source
        self._students = students
        self._rubrics = rubrics
        self._factory = factory

    def run(self, location: str) -> tuple[ImportOutcome, ...]:
        entries = self._source.read(location)
        rubric = self._rubrics.get()
        return tuple(self._apply(rubric, entry) for entry in entries)

    def _apply(self, rubric: Rubric, entry: StatementEntry) -> ImportOutcome:
        try:
            message = self._record(rubric, entry)
        except DomainError as error:
            return ImportOutcome(entry, False, str(error))
        return ImportOutcome(entry, True, message)

    def _record(self, rubric: Rubric, entry: StatementEntry) -> str:
        criterion = rubric.find(entry.criterion)
        if criterion is None:
            raise DomainError(f"критерия «{entry.criterion.strip()}» нет в рубрикаторе")
        points = _parse_points(entry.points)
        student, enrolled = self._student(entry.student)
        existing = student.evaluation_for(criterion.id)
        if existing is None:
            student.grade(self._factory.create(rubric, criterion.id, points), rubric)
            message = "оценка выставлена"
        else:
            before = existing.score.points
            student.correct(criterion.id, points, existing.graded_on, existing.comment)
            message = f"оценка исправлена: {plain(before)} → {plain(points)}"
        self._students.save(student)
        return f"студент добавлен, {message}" if enrolled else message

    def _student(self, name: str) -> tuple[Student, bool]:
        key = name.strip().casefold()
        matches = [student for student in self._students.all() if student.name.casefold() == key]
        if len(matches) > 1:
            raise DomainError(
                f"студентов с именем «{name.strip()}» несколько, выставьте оценку вручную по ID"
            )
        if matches:
            return matches[0], False
        return Student(self._students.next_id(), name), True


def _parse_points(text: str) -> Decimal:
    try:
        points = Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        raise DomainError(f"балл «{text.strip()}» должен быть числом") from None
    if not points.is_finite():
        raise DomainError(f"балл «{text.strip()}» должен быть числом")
    return points
