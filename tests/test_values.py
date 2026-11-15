from decimal import Decimal
from fractions import Fraction

import pytest

from pos.domain.errors import DomainError
from pos.domain.values import CriterionId, FinalGrade, Score, StudentId, plain, require_text


@pytest.mark.parametrize("points", ["0", "7.5", "10"])
def test_score_accepts_points_within_criterion_range(points):
    assert Score(Decimal(points), Decimal("10")).points == Decimal(points)


def test_twelve_out_of_ten_is_impossible():
    with pytest.raises(DomainError, match="балл 12 вне диапазона критерия: от 0 до 10"):
        Score(Decimal("12"), Decimal("10"))


@pytest.mark.parametrize("points", ["-0.5", "10.01", "NaN", "Infinity"])
def test_score_rejects_points_outside_range(points):
    with pytest.raises(DomainError):
        Score(Decimal(points), Decimal("10"))


@pytest.mark.parametrize("out_of", ["0", "-10", "NaN"])
def test_score_needs_positive_maximum(out_of):
    with pytest.raises(DomainError, match="максимальный балл"):
        Score(Decimal("0"), Decimal(out_of))


def test_score_share_is_exact():
    assert Score(Decimal("7.5"), Decimal("10")).share == Fraction(3, 4)


def test_corrected_score_keeps_maximum_and_range():
    score = Score(Decimal("5"), Decimal("10"))
    assert score.with_points(Decimal("9")) == Score(Decimal("9"), Decimal("10"))
    with pytest.raises(DomainError):
        score.with_points(Decimal("11"))


@pytest.mark.parametrize("value", [0, -1, True])
def test_identifiers_must_be_positive_integers(value):
    with pytest.raises(DomainError):
        StudentId(value)
    with pytest.raises(DomainError):
        CriterionId(value)


def test_identifiers_of_different_kinds_are_not_equal():
    identifiers: list[object] = [StudentId(1), StudentId(1), CriterionId(1)]
    assert identifiers[0] == identifiers[1]
    assert identifiers[0] != identifiers[2]


def test_final_grade_stays_on_ten_point_scale():
    with pytest.raises(DomainError):
        FinalGrade(Fraction(11), 1, 1)
    with pytest.raises(DomainError):
        FinalGrade(Fraction(-1), 1, 1)
    with pytest.raises(DomainError):
        FinalGrade(Fraction(5), 2, 1)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Fraction(20, 3), "6.67"), (Fraction(7495, 1000), "7.50"), (Fraction(8), "8.00")],
)
def test_final_grade_is_shown_with_two_decimals_rounded_half_up(value, expected):
    assert FinalGrade(value, 1, 1).as_decimal() == Decimal(expected)


def test_text_is_trimmed_and_cannot_be_blank():
    assert require_text("  Иванов  ", "имя") == "Иванов"
    with pytest.raises(DomainError, match="имя не может быть пустым"):
        require_text("   ", "имя")


@pytest.mark.parametrize(("value", "expected"), [("7.50", "7.5"), ("100", "100"), ("0.00", "0")])
def test_plain_drops_trailing_zeros(value, expected):
    assert plain(Decimal(value)) == expected
