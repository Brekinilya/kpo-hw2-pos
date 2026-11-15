from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import Decimal

from pos.domain.errors import DomainError
from pos.domain.values import CriterionId, require_positive, require_text


@dataclass(frozen=True, eq=False)
class Criterion:
    id: CriterionId
    name: str
    max_score: Decimal
    weight: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, "название критерия"))
        require_positive(self.max_score, "максимальный балл")
        require_positive(self.weight, "вес")


class Rubric:
    def __init__(self, criteria: Iterable[Criterion] = ()) -> None:
        self._criteria: dict[CriterionId, Criterion] = {}
        for criterion in criteria:
            self._include(criterion)

    @property
    def criteria(self) -> tuple[Criterion, ...]:
        return tuple(sorted(self._criteria.values(), key=lambda criterion: criterion.id.value))

    def add(self, name: str, max_score: Decimal, weight: Decimal) -> Criterion:
        criterion = Criterion(self._next_id(), name, max_score, weight)
        self._include(criterion)
        return criterion

    def criterion(self, criterion_id: CriterionId) -> Criterion:
        try:
            return self._criteria[criterion_id]
        except KeyError:
            raise DomainError(f"критерия с ID {criterion_id.value} нет в рубрикаторе") from None

    def find(self, name: str) -> Criterion | None:
        key = name.strip().casefold()
        return next(
            (
                criterion
                for criterion in self._criteria.values()
                if criterion.name.casefold() == key
            ),
            None,
        )

    def rename(self, criterion_id: CriterionId, name: str) -> Criterion:
        criterion = self.criterion(criterion_id)
        new_name = require_text(name, "название критерия")
        self._ensure_name_is_free(new_name, criterion_id)
        updated = replace(criterion, name=new_name)
        self._criteria[criterion_id] = updated
        return updated

    def reweigh(self, criterion_id: CriterionId, weight: Decimal) -> Criterion:
        criterion = self.criterion(criterion_id)
        updated = replace(criterion, weight=weight)
        self._criteria[criterion_id] = updated
        return updated

    def remove(self, criterion_id: CriterionId) -> Criterion:
        criterion = self.criterion(criterion_id)
        del self._criteria[criterion_id]
        return criterion

    def _include(self, criterion: Criterion) -> None:
        if criterion.id in self._criteria:
            raise DomainError(f"критерий с ID {criterion.id.value} уже есть в рубрикаторе")
        self._ensure_name_is_free(criterion.name, criterion.id)
        self._criteria[criterion.id] = criterion

    def _ensure_name_is_free(self, name: str, owner: CriterionId) -> None:
        other = self.find(name)
        if other is not None and other.id != owner:
            raise DomainError(f"критерий «{other.name}» уже есть в рубрикаторе")

    def _next_id(self) -> CriterionId:
        return CriterionId(max((key.value for key in self._criteria), default=0) + 1)
