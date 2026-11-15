from datetime import date
from decimal import Decimal

from pos.domain.errors import DomainError
from pos.domain.rubric import Rubric
from pos.domain.values import CriterionId, Score


class Evaluation:
    def __init__(
        self,
        criterion_id: CriterionId,
        score: Score,
        graded_on: date | None = None,
        comment: str = "",
    ) -> None:
        self._criterion_id = criterion_id
        self._score = score
        self._graded_on = graded_on
        self._comment = comment.strip()

    @property
    def criterion_id(self) -> CriterionId:
        return self._criterion_id

    @property
    def score(self) -> Score:
        return self._score

    @property
    def graded_on(self) -> date | None:
        return self._graded_on

    @property
    def comment(self) -> str:
        return self._comment

    def correct(self, points: Decimal, graded_on: date | None, comment: str) -> None:
        self._score = self._score.with_points(points)
        self._graded_on = graded_on
        self._comment = comment.strip()

    def validate_against(self, rubric: Rubric) -> None:
        criterion = rubric.criterion(self.criterion_id)
        Score(self.score.points, criterion.max_score)
        if self.score.out_of != criterion.max_score:
            raise DomainError(
                f"максимум оценки не совпадает с максимумом критерия «{criterion.name}»"
            )


class EvaluationFactory:
    def create(
        self,
        rubric: Rubric,
        criterion_id: CriterionId,
        points: Decimal,
        graded_on: date | None = None,
        comment: str = "",
    ) -> Evaluation:
        criterion = rubric.criterion(criterion_id)
        return Evaluation(criterion.id, Score(points, criterion.max_score), graded_on, comment)
