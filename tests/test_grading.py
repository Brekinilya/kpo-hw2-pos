from decimal import Decimal
from fractions import Fraction

import pytest

from pos.domain.errors import DomainError
from pos.domain.evaluation import EvaluationFactory
from pos.domain.grading import Contribution, EvaluatedAverage, HalfUpRounding, WeightedTotal
from pos.domain.rubric import Rubric
from pos.domain.services import FinalGradeCalculator, ensure_criterion_unused
from pos.domain.student import Student
from pos.domain.values import CriterionId, StudentId
from tests.support import make_criterion


def contributions(*items: tuple[str, Fraction | None]) -> list[Contribution]:
    return [Contribution(Fraction(weight), share) for weight, share in items]


def graded(rubric: Rubric, **points: str) -> Student:
    student = Student(StudentId(1), "Иванов Иван")
    factory = EvaluationFactory()
    for name, value in points.items():
        criterion = rubric.find(name)
        assert criterion is not None
        student.grade(factory.create(rubric, criterion.id, Decimal(value)), rubric)
    return student


def test_weighted_total_counts_missing_evaluation_as_zero():
    assert WeightedTotal().grade(contributions(("1", Fraction(1)), ("1", None))) == 5


def test_evaluated_average_uses_only_given_evaluations():
    assert EvaluatedAverage().grade(contributions(("1", Fraction(1)), ("1", None))) == 10


def test_policies_give_zero_without_data():
    assert WeightedTotal().grade([]) == 0
    assert EvaluatedAverage().grade(contributions(("1", None))) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Fraction(15, 2), 8), (Fraction(749, 100), 7), (Fraction(13, 2), 7), (Fraction(0), 0)],
)
def test_rounding_decorator_rounds_half_up(value, expected):
    class Fixed(WeightedTotal):
        def grade(self, contributions):
            return value

    assert HalfUpRounding(Fixed()).grade([]) == expected


def test_rounding_decorator_describes_wrapped_rule():
    title = HalfUpRounding(WeightedTotal()).title
    assert title.startswith(WeightedTotal.title)
    assert "округлением" in title


def test_different_maximums_are_normalised_by_weight():
    rubric = Rubric(
        [
            make_criterion(1, "ДЗ", max_score="10", weight="0.3"),
            make_criterion(2, "Экзамен", max_score="100", weight="0.7"),
        ]
    )
    student = graded(rubric, ДЗ="8", Экзамен="60")
    grade = FinalGradeCalculator().calculate(student, rubric, WeightedTotal())
    assert grade.value == Fraction(33, 5)
    assert (grade.evaluated, grade.criteria) == (2, 2)


def test_weights_do_not_have_to_sum_to_one():
    rubric = Rubric(
        [
            make_criterion(1, "ДЗ", max_score="10", weight="3"),
            make_criterion(2, "Экзамен", max_score="100", weight="7"),
        ]
    )
    student = graded(rubric, ДЗ="8", Экзамен="60")
    assert FinalGradeCalculator().calculate(student, rubric, WeightedTotal()).value == Fraction(
        33, 5
    )


def test_exact_arithmetic_keeps_half_point_for_rounding():
    rubric = Rubric(
        [
            make_criterion(1, "ДЗ-1", weight="0.1"),
            make_criterion(2, "ДЗ-2", weight="0.1"),
            make_criterion(3, "Экзамен", weight="0.2"),
        ]
    )
    student = graded(rubric, **{"ДЗ-1": "0", "ДЗ-2": "0", "Экзамен": "9"})
    calculator = FinalGradeCalculator()
    assert 10 * (0.2 * 9 / 10) / (0.1 + 0.1 + 0.2) < 4.5
    assert calculator.calculate(student, rubric, WeightedTotal()).value == Fraction(9, 2)
    assert calculator.calculate(student, rubric, HalfUpRounding(WeightedTotal())).value == 5


def test_final_grade_follows_current_evaluations():
    rubric = Rubric([make_criterion(1, "ДЗ", weight="1"), make_criterion(2, "Экзамен", weight="1")])
    student = graded(rubric, ДЗ="10", Экзамен="10")
    calculator = FinalGradeCalculator()
    assert calculator.calculate(student, rubric, WeightedTotal()).value == 10
    student.correct(CriterionId(2), Decimal("4"), None, "")
    assert calculator.calculate(student, rubric, WeightedTotal()).value == 7
    student.cancel(CriterionId(2))
    grade = calculator.calculate(student, rubric, WeightedTotal())
    assert grade.value == 5
    assert grade.evaluated == 1
    rubric.add("Доклад", Decimal("5"), Decimal("2"))
    assert calculator.calculate(student, rubric, WeightedTotal()).value == Fraction(10, 4)


def test_graded_criterion_cannot_be_removed():
    rubric = Rubric([make_criterion(1, "ДЗ")])
    student = graded(rubric, ДЗ="5")
    with pytest.raises(DomainError, match=r"«ДЗ» уже выставлены оценки \(1\)"):
        ensure_criterion_unused(rubric.criterion(CriterionId(1)), [student])
    student.cancel(CriterionId(1))
    ensure_criterion_unused(rubric.criterion(CriterionId(1)), [student])


def test_calculator_refuses_evaluations_from_another_rubric():
    original = Rubric([make_criterion(1, "ДЗ", max_score="100")])
    student = graded(original, ДЗ="80")
    calculator = FinalGradeCalculator()
    with pytest.raises(DomainError, match="нет в рубрикаторе"):
        calculator.calculate(student, Rubric(), WeightedTotal())
    other = Rubric([make_criterion(1, "ДЗ", max_score="10")])
    with pytest.raises(DomainError, match="от 0 до 10"):
        calculator.calculate(student, other, WeightedTotal())
