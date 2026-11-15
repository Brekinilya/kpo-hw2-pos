from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pos.application.views import (
    EvaluationView,
    FinalGradeView,
    GradeSheet,
    RuleView,
    evaluation_view,
    final_grade_view,
)
from pos.domain.errors import DomainError
from pos.domain.evaluation import EvaluationFactory
from pos.domain.grading import GradingPolicy
from pos.domain.repositories import RubricRepository, StudentRepository
from pos.domain.services import FinalGradeCalculator
from pos.domain.values import CriterionId, StudentId


class GradingService:
    def __init__(
        self,
        students: StudentRepository,
        rubrics: RubricRepository,
        factory: EvaluationFactory,
        calculator: FinalGradeCalculator,
        rules: Mapping[str, GradingPolicy],
    ) -> None:
        self._students = students
        self._rubrics = rubrics
        self._factory = factory
        self._calculator = calculator
        self._rules = rules

    def grade(
        self,
        student_id: int,
        criterion_id: int,
        points: Decimal,
        graded_on: date | None = None,
        comment: str = "",
    ) -> EvaluationView:
        student = self._students.get(StudentId(student_id))
        rubric = self._rubrics.get()
        evaluation = self._factory.create(
            rubric, CriterionId(criterion_id), points, graded_on, comment
        )
        student.grade(evaluation, rubric)
        self._students.save(student)
        return evaluation_view(rubric, evaluation)

    def correct(
        self,
        student_id: int,
        criterion_id: int,
        points: Decimal,
        graded_on: date | None = None,
        comment: str = "",
    ) -> EvaluationView:
        student = self._students.get(StudentId(student_id))
        evaluation = student.correct(CriterionId(criterion_id), points, graded_on, comment)
        self._students.save(student)
        return evaluation_view(self._rubrics.get(), evaluation)

    def cancel(self, student_id: int, criterion_id: int) -> EvaluationView:
        student = self._students.get(StudentId(student_id))
        evaluation = student.cancel(CriterionId(criterion_id))
        self._students.save(student)
        return evaluation_view(self._rubrics.get(), evaluation)

    def evaluations(self, student_id: int) -> tuple[EvaluationView, ...]:
        student = self._students.get(StudentId(student_id))
        rubric = self._rubrics.get()
        return tuple(evaluation_view(rubric, evaluation) for evaluation in student.evaluations)

    def rules(self) -> tuple[RuleView, ...]:
        return tuple(RuleView(key, policy.title) for key, policy in self._rules.items())

    def final_grade(self, student_id: int, rule: str) -> FinalGradeView:
        policy = self._policy(rule)
        student = self._students.get(StudentId(student_id))
        grade = self._calculator.calculate(student, self._rubrics.get(), policy)
        return final_grade_view(student, grade)

    def final_grades(self, rule: str) -> GradeSheet:
        policy = self._policy(rule)
        rubric = self._rubrics.get()
        grades = tuple(
            final_grade_view(student, self._calculator.calculate(student, rubric, policy))
            for student in self._students.all()
        )
        return GradeSheet(policy.title, grades)

    def _policy(self, rule: str) -> GradingPolicy:
        try:
            return self._rules[rule]
        except KeyError:
            raise DomainError(f"неизвестное правило итога «{rule}»") from None
