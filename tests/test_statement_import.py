from decimal import Decimal

from dependency_injector import providers

from pos.application.ports import StatementEntry, StatementSource
from pos.container import Container
from tests.support import make_container


class FakeStatementSource(StatementSource):
    def __init__(self, *entries: tuple[str, str, str]) -> None:
        self.locations: list[str] = []
        self._entries = [
            StatementEntry(f"строка {number}", student, criterion, points)
            for number, (student, criterion, points) in enumerate(entries, 2)
        ]

    def read(self, location):
        self.locations.append(location)
        return self._entries


def import_with(*entries: tuple[str, str, str]) -> tuple[Container, list[tuple[bool, str]]]:
    container = make_container()
    container.rubric_service().add("ДЗ", Decimal("10"), Decimal("1"))
    container.rubric_service().add("Экзамен", Decimal("100"), Decimal("1"))
    source = FakeStatementSource(*entries)
    container.statement_source.override(providers.Object(source))
    outcomes = container.statement_import().run("ведомость.csv")
    assert source.locations == ["ведомость.csv"]
    return container, [(outcome.accepted, outcome.message) for outcome in outcomes]


def test_new_student_is_enrolled_once_and_graded():
    container, outcomes = import_with(
        ("Иванов Иван", "ДЗ", "8"), ("иванов иван ", "Экзамен", "75,5")
    )
    assert outcomes == [
        (True, "студент добавлен, оценка выставлена"),
        (True, "оценка выставлена"),
    ]
    [student] = container.student_service().all()
    assert (student.name, student.evaluated) == ("Иванов Иван", 2)
    points = [item.points for item in container.grading().evaluations(student.id)]
    assert points == [Decimal("8"), Decimal("75.5")]


def test_existing_evaluation_is_corrected():
    _, outcomes = import_with(("Иванов Иван", "ДЗ", "8"), ("Иванов Иван", "ДЗ", "9"))
    assert outcomes[1] == (True, "оценка исправлена: 8 → 9")


def test_rules_of_domain_reject_single_entries():
    container, outcomes = import_with(
        ("Иванов Иван", "Доклад", "5"),
        ("Петрова Анна", "ДЗ", "12"),
        ("Петрова Анна", "ДЗ", "много"),
        ("Петрова Анна", "ДЗ", "NaN"),
        (" ", "ДЗ", "5"),
        ("Сидоров Пётр", "ДЗ", "6"),
    )
    assert outcomes == [
        (False, "критерия «Доклад» нет в рубрикаторе"),
        (False, "балл 12 вне диапазона критерия: от 0 до 10"),
        (False, "балл «много» должен быть числом"),
        (False, "балл «NaN» должен быть числом"),
        (False, "имя студента не может быть пустым"),
        (True, "студент добавлен, оценка выставлена"),
    ]
    assert [student.name for student in container.student_service().all()] == ["Сидоров Пётр"]


def test_ambiguous_student_name_is_not_guessed():
    container = make_container()
    container.rubric_service().add("ДЗ", Decimal("10"), Decimal("1"))
    container.student_service().enroll("Иванов Иван")
    container.student_service().enroll("Иванов Иван")
    container.statement_source.override(
        providers.Object(FakeStatementSource(("Иванов Иван", "ДЗ", "5")))
    )
    [outcome] = container.statement_import().run("ведомость.json")
    assert not outcome.accepted
    assert "несколько" in outcome.message
