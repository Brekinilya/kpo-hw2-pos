import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from pos.domain.values import GRADE_SCALE


@dataclass(frozen=True)
class Contribution:
    weight: Fraction
    share: Fraction | None


class GradingPolicy(ABC):
    @property
    @abstractmethod
    def title(self) -> str: ...

    @abstractmethod
    def grade(self, contributions: Sequence[Contribution]) -> Fraction: ...


class WeightedTotal(GradingPolicy):
    title = "взвешенный балл, невыставленная оценка считается нулём"

    def grade(self, contributions: Sequence[Contribution]) -> Fraction:
        return _weighted_average(
            [(item.weight, item.share or Fraction(0)) for item in contributions]
        )


class EvaluatedAverage(GradingPolicy):
    title = "промежуточный балл только по выставленным оценкам"

    def grade(self, contributions: Sequence[Contribution]) -> Fraction:
        return _weighted_average(
            [(item.weight, item.share) for item in contributions if item.share is not None]
        )


class HalfUpRounding(GradingPolicy):
    def __init__(self, inner: GradingPolicy) -> None:
        self._inner = inner

    @property
    def title(self) -> str:
        return f"{self._inner.title}, с арифметическим округлением до целого"

    def grade(self, contributions: Sequence[Contribution]) -> Fraction:
        return Fraction(math.floor(self._inner.grade(contributions) + Fraction(1, 2)))


def _weighted_average(pairs: Sequence[tuple[Fraction, Fraction]]) -> Fraction:
    total_weight = sum((weight for weight, _ in pairs), Fraction(0))
    if total_weight == 0:
        return Fraction(0)
    earned = sum((weight * share for weight, share in pairs), Fraction(0))
    return GRADE_SCALE * earned / total_weight
