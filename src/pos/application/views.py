from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pos.domain.evaluation import Evaluation
from pos.domain.rubric import Criterion, Rubric
from pos.domain.student import Student
from pos.domain.values import FinalGrade


@dataclass(frozen=True)
class StudentView:
    id: int
    name: str
    evaluated: int


@dataclass(frozen=True)
class CriterionView:
    id: int
    name: str
    max_score: Decimal
    weight: Decimal
    share_percent: Decimal


@dataclass(frozen=True)
class EvaluationView:
    criterion_id: int
    criterion: str
    points: Decimal
    out_of: Decimal
    graded_on: date | None
    comment: str


@dataclass(frozen=True)
class RuleView:
    key: str
    title: str


@dataclass(frozen=True)
class FinalGradeView:
    student_id: int
    student: str
    grade: Decimal
    evaluated: int
    criteria: int


@dataclass(frozen=True)
class GradeSheet:
    rule: str
    grades: tuple[FinalGradeView, ...]


def student_view(student: Student) -> StudentView:
    return StudentView(student.id.value, student.name, len(student.evaluations))


def criterion_view(rubric: Rubric, criterion: Criterion) -> CriterionView:
    total = sum((item.weight for item in rubric.criteria), Decimal(0))
    share = (criterion.weight * 100 / total).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return CriterionView(
        criterion.id.value, criterion.name, criterion.max_score, criterion.weight, share
    )


def evaluation_view(rubric: Rubric, evaluation: Evaluation) -> EvaluationView:
    return EvaluationView(
        evaluation.criterion_id.value,
        rubric.criterion(evaluation.criterion_id).name,
        evaluation.score.points,
        evaluation.score.out_of,
        evaluation.graded_on,
        evaluation.comment,
    )


def final_grade_view(student: Student, grade: FinalGrade) -> FinalGradeView:
    return FinalGradeView(
        student.id.value, student.name, grade.as_decimal(), grade.evaluated, grade.criteria
    )
