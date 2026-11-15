from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from pos.domain.errors import DomainError
from pos.domain.rubric import Criterion, Rubric
from pos.domain.values import CriterionId
from tests.support import make_criterion


def test_criteria_get_sequential_ids():
    rubric = Rubric()
    first = rubric.add("ДЗ-1", Decimal("10"), Decimal("0.3"))
    second = rubric.add("Экзамен", Decimal("100"), Decimal("0.7"))
    assert (first.id, second.id) == (CriterionId(1), CriterionId(2))
    assert rubric.criteria == (first, second)


def test_criterion_is_found_by_name_ignoring_case_and_spaces():
    rubric = Rubric([make_criterion(name="Экзамен")])
    assert rubric.find("  экзамен ") is rubric.criterion(CriterionId(1))
    assert rubric.find("Доклад") is None


def test_criterion_names_are_unique_ignoring_case():
    rubric = Rubric([make_criterion(name="ДЗ-1")])
    with pytest.raises(DomainError, match="«ДЗ-1» уже есть"):
        rubric.add("дз-1", Decimal("10"), Decimal("1"))


def test_rename_keeps_names_unique():
    rubric = Rubric([make_criterion(1, "ДЗ-1"), make_criterion(2, "ДЗ-2")])
    with pytest.raises(DomainError):
        rubric.rename(CriterionId(2), "ДЗ-1")
    assert rubric.rename(CriterionId(1), "дз-1").name == "дз-1"


@pytest.mark.parametrize(
    ("name", "max_score", "weight", "message"),
    [
        ("  ", "10", "1", "название критерия"),
        ("ДЗ", "0", "1", "максимальный балл"),
        ("ДЗ", "-5", "1", "максимальный балл"),
        ("ДЗ", "10", "0", "вес"),
        ("ДЗ", "10", "NaN", "вес"),
    ],
)
def test_criterion_rejects_invalid_values(name, max_score, weight, message):
    with pytest.raises(DomainError, match=message):
        Rubric().add(name, Decimal(max_score), Decimal(weight))


def test_failed_reweigh_keeps_previous_weight():
    rubric = Rubric([make_criterion(weight="0.5")])
    with pytest.raises(DomainError):
        rubric.reweigh(CriterionId(1), Decimal("-1"))
    assert rubric.criterion(CriterionId(1)).weight == Decimal("0.5")
    assert rubric.reweigh(CriterionId(1), Decimal("2")).weight == Decimal("2")


def test_unknown_criterion_is_reported():
    with pytest.raises(DomainError, match="критерия с ID 7 нет в рубрикаторе"):
        Rubric().criterion(CriterionId(7))


def test_removed_criterion_leaves_rubric():
    rubric = Rubric([make_criterion(1, "ДЗ-1"), make_criterion(2, "ДЗ-2")])
    assert rubric.remove(CriterionId(1)).name == "ДЗ-1"
    assert [criterion.name for criterion in rubric.criteria] == ["ДЗ-2"]
    with pytest.raises(DomainError):
        rubric.remove(CriterionId(1))


def test_rubric_rejects_repeated_ids_when_restored():
    with pytest.raises(DomainError, match="ID 1"):
        Rubric([make_criterion(1, "ДЗ-1"), make_criterion(1, "ДЗ-2")])


@pytest.mark.parametrize("access", ["criteria", "criterion", "find", "add"])
def test_exposed_criterion_cannot_change_aggregate(access):
    rubric = Rubric([make_criterion(1, "ДЗ-1"), make_criterion(2, "ДЗ-2")])
    criterion: Criterion | None
    if access == "criteria":
        criterion = rubric.criteria[0]
    elif access == "criterion":
        criterion = rubric.criterion(CriterionId(1))
    elif access == "find":
        criterion = rubric.find("ДЗ-1")
    else:
        criterion = rubric.add("ДЗ-3", Decimal("10"), Decimal("1"))
    assert criterion is not None
    for field, value in (("name", "ДЗ-2"), ("max_score", Decimal("100")), ("weight", Decimal(0))):
        with pytest.raises(FrozenInstanceError):
            setattr(criterion, field, value)
    copy = replace(criterion, name="ДЗ-2")
    assert copy.name == "ДЗ-2"
    assert rubric.criterion(criterion.id).name == criterion.name


def test_rubric_updates_criterion_snapshot_with_same_id():
    rubric = Rubric([make_criterion(1, "ДЗ")])
    before = rubric.criterion(CriterionId(1))
    renamed = rubric.rename(before.id, "Домашнее задание")
    reweighed = rubric.reweigh(before.id, Decimal("2"))
    assert before.id == renamed.id == reweighed.id
    assert before.name == "ДЗ"
    assert reweighed.name == "Домашнее задание"
    assert reweighed.weight == Decimal("2")
    assert rubric.criterion(before.id) is reweighed
