from datetime import date
from decimal import Decimal

import pytest

from pos.application.grading import GradingService
from pos.container import Container
from pos.domain.errors import DomainError
from tests.support import make_container


@pytest.fixture
def container():
    return make_container()


def prepare(container: Container) -> GradingService:
    rubric = container.rubric_service()
    rubric.add("ДЗ", Decimal("10"), Decimal("0.4"))
    rubric.add("Экзамен", Decimal("10"), Decimal("0.6"))
    students = container.student_service()
    students.enroll("Иванов Иван")
    students.enroll("Петрова Анна")
    return container.grading()


def test_students_can_be_enrolled_renamed_and_removed(container):
    students = container.student_service()
    first = students.enroll("  Иванов Иван ")
    second = students.enroll("Петрова Анна")
    assert (first.id, first.name, second.id) == (1, "Иванов Иван", 2)
    assert students.rename(2, "Петрова Анна Сергеевна").name == "Петрова Анна Сергеевна"
    assert students.remove(1).name == "Иванов Иван"
    assert [student.id for student in students.all()] == [2]
    assert students.enroll("Сидоров Пётр").id == 3


def test_unknown_student_is_reported(container):
    with pytest.raises(DomainError, match="студента с ID 5 нет"):
        container.student_service().rename(5, "Кто-то")


def test_rubric_shows_share_of_each_criterion(container):
    rubric = container.rubric_service()
    rubric.add("ДЗ", Decimal("10"), Decimal("1"))
    rubric.add("Экзамен", Decimal("100"), Decimal("2"))
    shares = [(item.name, item.share_percent) for item in rubric.all()]
    assert shares == [("ДЗ", Decimal("33.3")), ("Экзамен", Decimal("66.7"))]


def test_criterion_can_be_renamed_and_reweighed(container):
    rubric = container.rubric_service()
    rubric.add("ДЗ", Decimal("10"), Decimal("1"))
    assert rubric.rename(1, "Домашние задания").name == "Домашние задания"
    assert rubric.reweigh(1, Decimal("3")).weight == Decimal("3")


def test_graded_criterion_is_kept_until_evaluations_are_cancelled(container):
    grading = prepare(container)
    grading.grade(1, 1, Decimal("8"))
    rubric = container.rubric_service()
    with pytest.raises(DomainError, match="уже выставлены оценки"):
        rubric.remove(1)
    grading.cancel(1, 1)
    assert rubric.remove(1).name == "ДЗ"
    assert [item.name for item in rubric.all()] == ["Экзамен"]


def test_grading_scenario_produces_final_grades(container):
    grading = prepare(container)
    view = grading.grade(1, 1, Decimal("8"), date(2026, 11, 3), "молодец")
    assert (view.criterion, view.points, view.out_of, view.comment) == (
        "ДЗ",
        Decimal("8"),
        Decimal("10"),
        "молодец",
    )
    grading.grade(1, 2, Decimal("7"))
    grading.grade(2, 1, Decimal("10"))
    assert grading.final_grade(1, "exact").grade == Decimal("7.40")
    assert grading.final_grade(1, "final").grade == Decimal("7.00")
    sheet = grading.final_grades("interim")
    assert [(grade.student, grade.grade) for grade in sheet.grades] == [
        ("Иванов Иван", Decimal("7.40")),
        ("Петрова Анна", Decimal("10.00")),
    ]
    assert sheet.rule == container.rules()["interim"].title


def test_evaluation_rules_are_enforced_by_service(container):
    grading = prepare(container)
    with pytest.raises(DomainError, match="балл 12 вне диапазона"):
        grading.grade(1, 1, Decimal("12"))
    with pytest.raises(DomainError, match="нет в рубрикаторе"):
        grading.grade(1, 9, Decimal("1"))
    grading.grade(1, 1, Decimal("5"))
    with pytest.raises(DomainError, match="можно исправить"):
        grading.grade(1, 1, Decimal("6"))
    assert grading.evaluations(2) == ()


def test_correction_and_cancellation_change_the_final_grade(container):
    grading = prepare(container)
    grading.grade(1, 1, Decimal("5"))
    grading.grade(1, 2, Decimal("5"))
    assert grading.correct(1, 2, Decimal("10")).points == Decimal("10")
    assert grading.final_grade(1, "exact").grade == Decimal("8.00")
    assert grading.cancel(1, 2).criterion == "Экзамен"
    assert grading.final_grade(1, "exact").grade == Decimal("2.00")
    assert [item.criterion for item in grading.evaluations(1)] == ["ДЗ"]


def test_rules_are_listed_and_checked(container):
    grading = prepare(container)
    assert [rule.key for rule in grading.rules()] == ["final", "exact", "interim"]
    with pytest.raises(DomainError, match="неизвестное правило"):
        grading.final_grades("median")


def test_removing_student_removes_evaluations(container):
    grading = prepare(container)
    grading.grade(1, 1, Decimal("5"))
    container.student_service().remove(1)
    assert container.rubric_service().remove(1).name == "ДЗ"
