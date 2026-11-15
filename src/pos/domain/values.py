from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from pos.domain.errors import DomainError

GRADE_SCALE = 10


def require_text(value: str, field: str) -> str:
    text = value.strip()
    if not text:
        raise DomainError(f"{field} не может быть пустым")
    return text


def require_positive(value: Decimal, field: str) -> Decimal:
    if not value.is_finite() or value <= 0:
        raise DomainError(f"{field} должен быть положительным числом")
    return value


def plain(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _require_identifier(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DomainError("ID должен быть целым положительным числом")


@dataclass(frozen=True)
class StudentId:
    value: int

    def __post_init__(self) -> None:
        _require_identifier(self.value)


@dataclass(frozen=True)
class CriterionId:
    value: int

    def __post_init__(self) -> None:
        _require_identifier(self.value)


@dataclass(frozen=True)
class Score:
    points: Decimal
    out_of: Decimal

    def __post_init__(self) -> None:
        require_positive(self.out_of, "максимальный балл")
        if not self.points.is_finite() or not 0 <= self.points <= self.out_of:
            raise DomainError(
                f"балл {plain(self.points)} вне диапазона критерия: от 0 до {plain(self.out_of)}"
            )

    @property
    def share(self) -> Fraction:
        return Fraction(self.points) / Fraction(self.out_of)

    def with_points(self, points: Decimal) -> "Score":
        return Score(points, self.out_of)


@dataclass(frozen=True)
class FinalGrade:
    value: Fraction
    evaluated: int
    criteria: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= GRADE_SCALE:
            raise DomainError(f"итог должен быть от 0 до {GRADE_SCALE}")
        if not 0 <= self.evaluated <= self.criteria:
            raise DomainError("оценённых критериев не может быть больше, чем критериев")

    def as_decimal(self) -> Decimal:
        exact = Decimal(self.value.numerator) / Decimal(self.value.denominator)
        return exact.quantize(Decimal("0.01"), ROUND_HALF_UP)
