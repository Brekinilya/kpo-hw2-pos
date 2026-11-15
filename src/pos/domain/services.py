from collections.abc import Iterable
from fractions import Fraction

from pos.domain.errors import DomainError
from pos.domain.grading import Contribution, GradingPolicy
from pos.domain.rubric import Criterion, Rubric
from pos.domain.student import Student
from pos.domain.values import FinalGrade


class FinalGradeCalculator:
    def calculate(self, student: Student, rubric: Rubric, policy: GradingPolicy) -> FinalGrade:
        student.validate_against(rubric)
        contributions = [self._contribution(student, criterion) for criterion in rubric.criteria]
        evaluated = sum(1 for item in contributions if item.share is not None)
        return FinalGrade(policy.grade(contributions), evaluated, len(contributions))

    def _contribution(self, student: Student, criterion: Criterion) -> Contribution:
        evaluation = student.evaluation_for(criterion.id)
        share = None if evaluation is None else evaluation.score.share
        return Contribution(Fraction(criterion.weight), share)


def ensure_criterion_unused(criterion: Criterion, students: Iterable[Student]) -> None:
    graded = sum(1 for student in students if student.evaluation_for(criterion.id) is not None)
    if graded:
        raise DomainError(
            f"по критерию «{criterion.name}» уже выставлены оценки ({graded}), сначала отмените их"
        )
