from decimal import Decimal

from pos.application.views import CriterionView, criterion_view
from pos.domain.repositories import RubricRepository, StudentRepository
from pos.domain.services import ensure_criterion_unused
from pos.domain.values import CriterionId


class RubricService:
    def __init__(self, rubrics: RubricRepository, students: StudentRepository) -> None:
        self._rubrics = rubrics
        self._students = students

    def add(self, name: str, max_score: Decimal, weight: Decimal) -> CriterionView:
        rubric = self._rubrics.get()
        criterion = rubric.add(name, max_score, weight)
        self._rubrics.save(rubric)
        return criterion_view(rubric, criterion)

    def rename(self, criterion_id: int, name: str) -> CriterionView:
        rubric = self._rubrics.get()
        criterion = rubric.rename(CriterionId(criterion_id), name)
        self._rubrics.save(rubric)
        return criterion_view(rubric, criterion)

    def reweigh(self, criterion_id: int, weight: Decimal) -> CriterionView:
        rubric = self._rubrics.get()
        criterion = rubric.reweigh(CriterionId(criterion_id), weight)
        self._rubrics.save(rubric)
        return criterion_view(rubric, criterion)

    def remove(self, criterion_id: int) -> CriterionView:
        rubric = self._rubrics.get()
        criterion = rubric.criterion(CriterionId(criterion_id))
        ensure_criterion_unused(criterion, self._students.all())
        view = criterion_view(rubric, criterion)
        rubric.remove(criterion.id)
        self._rubrics.save(rubric)
        return view

    def all(self) -> tuple[CriterionView, ...]:
        rubric = self._rubrics.get()
        return tuple(criterion_view(rubric, criterion) for criterion in rubric.criteria)
