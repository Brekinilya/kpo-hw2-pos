from datetime import date
from decimal import Decimal

import pytest

from pos.domain.errors import DomainError
from pos.domain.evaluation import Evaluation, EvaluationFactory
from pos.domain.rubric import Rubric
from pos.domain.student import Student
from pos.domain.values import CriterionId, Score, StudentId
from tests.support import make_criterion


def evaluation(criterion: int = 1, points: str = "8", out_of: str = "10") -> Evaluation:
    return Evaluation(CriterionId(criterion), Score(Decimal(points), Decimal(out_of)))


def points_of(student: Student, criterion: int) -> Decimal:
    current = student.evaluation_for(CriterionId(criterion))
    assert current is not None
    return current.score.points


def rubric_for(*ids: int) -> Rubric:
    return Rubric(make_criterion(i, f"Критерий {i}") for i in ids)


def test_student_has_one_current_evaluation_per_criterion():
    student = Student(StudentId(1), "Иванов Иван")
    rubric = rubric_for(1)
    student.grade(evaluation(1), rubric)
    with pytest.raises(DomainError, match="её можно исправить"):
        student.grade(evaluation(1, "9"), rubric)
    assert points_of(student, 1) == Decimal("8")


def test_correction_keeps_criterion_range():
    student = Student(StudentId(1), "Иванов Иван", [evaluation(1, "8", "10")], rubric=rubric_for(1))
    corrected = student.correct(CriterionId(1), Decimal("9.5"), date(2026, 11, 3), " пересдача ")
    assert corrected.score == Score(Decimal("9.5"), Decimal("10"))
    assert corrected.graded_on == date(2026, 11, 3)
    assert corrected.comment == "пересдача"
    with pytest.raises(DomainError, match="от 0 до 10"):
        student.correct(CriterionId(1), Decimal("12"), None, "")
    assert points_of(student, 1) == Decimal("9.5")


def test_cancelled_evaluation_disappears():
    student = Student(
        StudentId(1), "Иванов Иван", [evaluation(1), evaluation(2)], rubric=rubric_for(1, 2)
    )
    student.cancel(CriterionId(1))
    assert [item.criterion_id for item in student.evaluations] == [CriterionId(2)]


def test_missing_evaluation_cannot_be_corrected_or_cancelled():
    student = Student(StudentId(1), "Иванов Иван")
    with pytest.raises(DomainError, match="нет оценки по критерию с ID 3"):
        student.correct(CriterionId(3), Decimal("1"), None, "")
    with pytest.raises(DomainError):
        student.cancel(CriterionId(3))


def test_evaluations_are_ordered_by_criterion():
    student = Student(
        StudentId(1), "Иванов Иван", [evaluation(3), evaluation(1)], rubric=rubric_for(1, 3)
    )
    assert [item.criterion_id.value for item in student.evaluations] == [1, 3]


def test_student_name_cannot_be_blank():
    with pytest.raises(DomainError, match="имя студента"):
        Student(StudentId(1), " ")
    student = Student(StudentId(1), "Иванов")
    with pytest.raises(DomainError):
        student.rename("")
    student.rename(" Иванов Иван ")
    assert student.name == "Иванов Иван"


def test_factory_takes_maximum_from_rubric():
    rubric = Rubric([make_criterion(1, "Экзамен", max_score="100")])
    created = EvaluationFactory().create(
        rubric, CriterionId(1), Decimal("75"), date(2026, 11, 3), "  устно "
    )
    assert created.score == Score(Decimal("75"), Decimal("100"))
    assert created.graded_on == date(2026, 11, 3)
    assert created.comment == "устно"


def test_factory_refuses_criterion_outside_rubric():
    with pytest.raises(DomainError, match="нет в рубрикаторе"):
        EvaluationFactory().create(Rubric(), CriterionId(1), Decimal("5"))


def test_factory_refuses_points_above_criterion_maximum():
    rubric = Rubric([make_criterion(max_score="10")])
    with pytest.raises(DomainError, match="балл 12 вне диапазона"):
        EvaluationFactory().create(rubric, CriterionId(1), Decimal("12"))


@pytest.mark.parametrize(
    ("created", "rubric", "message"),
    [
        (evaluation(9), rubric_for(1), "нет в рубрикаторе"),
        (evaluation(1, "12", "100"), rubric_for(1), "от 0 до 10"),
        (evaluation(1, "8", "100"), rubric_for(1), "максимум оценки"),
    ],
)
def test_student_rejects_invalid_evaluation_without_factory(created, rubric, message):
    student = Student(StudentId(1), "Иванов")
    with pytest.raises(DomainError, match=message):
        student.grade(created, rubric)
    assert student.evaluations == ()
    with pytest.raises(DomainError, match=message):
        Student(StudentId(1), "Иванов", [created], rubric=rubric)


def test_restoring_evaluations_requires_rubric():
    with pytest.raises(DomainError, match="нужен рубрикатор"):
        Student(StudentId(1), "Иванов", [evaluation()])
