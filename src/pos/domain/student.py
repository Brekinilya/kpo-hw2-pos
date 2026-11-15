from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from pos.domain.errors import DomainError
from pos.domain.evaluation import Evaluation
from pos.domain.rubric import Rubric
from pos.domain.values import CriterionId, StudentId, require_text


class Student:
    def __init__(
        self,
        student_id: StudentId,
        name: str,
        evaluations: Iterable[Evaluation] = (),
        *,
        rubric: Rubric | None = None,
    ) -> None:
        self._id = student_id
        self._name = require_text(name, "имя студента")
        self._evaluations: dict[CriterionId, Evaluation] = {}
        for evaluation in evaluations:
            if rubric is None:
                raise DomainError("для восстановления оценок нужен рубрикатор")
            self.grade(evaluation, rubric)

    @property
    def id(self) -> StudentId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def evaluations(self) -> tuple[Evaluation, ...]:
        return tuple(
            sorted(self._evaluations.values(), key=lambda evaluation: evaluation.criterion_id.value)
        )

    def rename(self, name: str) -> None:
        self._name = require_text(name, "имя студента")

    def evaluation_for(self, criterion_id: CriterionId) -> Evaluation | None:
        return self._evaluations.get(criterion_id)

    def grade(self, evaluation: Evaluation, rubric: Rubric) -> None:
        evaluation.validate_against(rubric)
        if evaluation.criterion_id in self._evaluations:
            raise DomainError(
                f"у студента «{self._name}» уже есть оценка по критерию "
                f"с ID {evaluation.criterion_id.value}, её можно исправить"
            )
        self._evaluations[evaluation.criterion_id] = evaluation

    def validate_against(self, rubric: Rubric) -> None:
        for evaluation in self.evaluations:
            evaluation.validate_against(rubric)

    def correct(
        self, criterion_id: CriterionId, points: Decimal, graded_on: date | None, comment: str
    ) -> Evaluation:
        evaluation = self._require(criterion_id)
        evaluation.correct(points, graded_on, comment)
        return evaluation

    def cancel(self, criterion_id: CriterionId) -> Evaluation:
        evaluation = self._require(criterion_id)
        del self._evaluations[criterion_id]
        return evaluation

    def _require(self, criterion_id: CriterionId) -> Evaluation:
        evaluation = self.evaluation_for(criterion_id)
        if evaluation is None:
            raise DomainError(
                f"у студента «{self._name}» нет оценки по критерию с ID {criterion_id.value}"
            )
        return evaluation
