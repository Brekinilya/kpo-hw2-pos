import json
from datetime import date
from decimal import Decimal

import pytest

from pos.adapters.json_storage import JsonRubricRepository, JsonStudentRepository
from pos.domain.errors import DomainError
from pos.domain.evaluation import EvaluationFactory
from pos.domain.repositories import StorageError
from pos.domain.rubric import Rubric
from pos.domain.student import Student
from pos.domain.values import CriterionId, StudentId


def test_students_and_rubric_survive_restart(tmp_path):
    rubrics = JsonRubricRepository(tmp_path)
    rubric = rubrics.get()
    rubric.add("Экзамен", Decimal("100"), Decimal("0.35"))
    rubrics.save(rubric)
    students = JsonStudentRepository(tmp_path)
    student = Student(students.next_id(), "Иванов Иван")
    student.grade(
        EvaluationFactory().create(
            rubric, CriterionId(1), Decimal("72.5"), date(2026, 11, 3), "устно"
        ),
        rubric,
    )
    students.save(student)

    restored = JsonStudentRepository(tmp_path).get(StudentId(1))
    [evaluation] = restored.evaluations
    assert restored.name == "Иванов Иван"
    assert (evaluation.score.points, evaluation.score.out_of) == (Decimal("72.5"), Decimal("100"))
    assert (evaluation.graded_on, evaluation.comment) == (date(2026, 11, 3), "устно")
    [criterion] = JsonRubricRepository(tmp_path).get().criteria
    assert (criterion.name, criterion.weight) == ("Экзамен", Decimal("0.35"))


def test_missing_files_mean_empty_course(tmp_path):
    assert JsonStudentRepository(tmp_path / "new").all() == ()
    assert JsonRubricRepository(tmp_path / "new").get().criteria == ()


def test_ids_are_not_reused_after_removal(tmp_path):
    students = JsonStudentRepository(tmp_path)
    for name in ("Иванов", "Петров"):
        students.save(Student(students.next_id(), name))
    students.remove(StudentId(2))
    assert JsonStudentRepository(tmp_path).next_id() == StudentId(3)


def test_changes_without_save_are_not_stored(tmp_path):
    students = JsonStudentRepository(tmp_path)
    students.save(Student(students.next_id(), "Иванов"))
    students.get(StudentId(1)).rename("Петров")
    assert students.get(StudentId(1)).name == "Иванов"


@pytest.mark.parametrize(
    "document",
    [
        "{",
        "[1]",
        '{"last_id": 0}',
        '{"last_id": "1", "students": []}',
        '{"last_id": 0, "students": [{"id": 1, "name": "", "evaluations": []}]}',
        '{"last_id": 0, "students": [{"id": 1, "name": "А", "evaluations": ['
        '{"criterion_id": 1, "points": "12", "out_of": "10", "graded_on": null, "comment": ""}'
        "]}]}",
        '{"last_id": 0, "students": [{"id": 1, "name": "А", "evaluations": ['
        '{"criterion_id": 1, "points": 5, "out_of": "10", "graded_on": null, "comment": ""}'
        "]}]}",
        '{"last_id": 0, "students": [{"id": 1, "name": "А", "evaluations": []},'
        ' {"id": 1, "name": "Б", "evaluations": []}]}',
    ],
)
def test_corrupted_student_file_is_refused(tmp_path, document):
    (tmp_path / "students.json").write_text(document, encoding="utf-8")
    with pytest.raises(StorageError, match=r"students\.json"):
        JsonStudentRepository(tmp_path)


@pytest.mark.parametrize(
    "criteria",
    [
        [{"id": 1, "name": "ДЗ", "max_score": "abc", "weight": "1"}],
        [{"id": 1, "name": "ДЗ", "max_score": "10"}],
        [
            {"id": 1, "name": "ДЗ", "max_score": "10", "weight": "1"},
            {"id": 2, "name": "дз", "max_score": "10", "weight": "1"},
        ],
    ],
)
def test_corrupted_rubric_file_is_refused(tmp_path, criteria):
    (tmp_path / "rubric.json").write_text(json.dumps({"criteria": criteria}), encoding="utf-8")
    with pytest.raises(StorageError, match=r"rubric\.json"):
        JsonRubricRepository(tmp_path)


def test_unreadable_file_is_reported(tmp_path):
    (tmp_path / "rubric.json").write_bytes("{'ДЗ'}".encode("cp1251"))
    with pytest.raises(StorageError, match="не удалось прочитать"):
        JsonRubricRepository(tmp_path)


def test_failed_write_is_reported_and_keeps_previous_state(tmp_path):
    students = JsonStudentRepository(tmp_path)
    students.save(Student(students.next_id(), "Иванов"))
    (tmp_path / "students.json.tmp").mkdir()
    with pytest.raises(StorageError, match="не удалось сохранить"):
        students.save(Student(students.next_id(), "Петров"))
    assert [student.name for student in students.all()] == ["Иванов"]


@pytest.mark.parametrize(
    "repository,filename",
    [
        (JsonStudentRepository, "students.json"),
        (JsonRubricRepository, "rubric.json"),
    ],
)
@pytest.mark.parametrize("document", ["{}", "[]", "false", "0", "null", '""'])
def test_invalid_root_is_not_treated_as_missing_file(tmp_path, repository, filename, document):
    path = tmp_path / filename
    path.write_text(document, encoding="utf-8")
    with pytest.raises(StorageError, match=filename):
        repository(tmp_path)
    assert path.read_text(encoding="utf-8") == document


@pytest.mark.parametrize(
    "filename,document",
    [
        ("students.json", {"last_id": 0, "students": {}}),
        ("students.json", {"last_id": -1, "students": []}),
        ("students.json", {"last_id": 1, "students": [{"id": 1, "name": "А", "evaluations": {}}]}),
        ("rubric.json", {"criteria": {}}),
    ],
)
def test_invalid_storage_structure_is_refused(tmp_path, filename, document):
    path = tmp_path / filename
    path.write_text(json.dumps(document), encoding="utf-8")
    before = path.read_bytes()
    repository = JsonStudentRepository if filename == "students.json" else JsonRubricRepository
    with pytest.raises(StorageError, match=filename):
        repository(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "criterion_id,points,out_of", [(9, "8", "10"), (1, "12", "100"), (1, "8", "100")]
)
def test_stored_evaluations_must_match_rubric(tmp_path, criterion_id, points, out_of):
    rubrics = JsonRubricRepository(tmp_path)
    rubric = rubrics.get()
    rubric.add("ДЗ", Decimal("10"), Decimal("1"))
    rubrics.save(rubric)
    document = {
        "last_id": 1,
        "students": [
            {
                "id": 1,
                "name": "А",
                "evaluations": [
                    {
                        "criterion_id": criterion_id,
                        "points": points,
                        "out_of": out_of,
                        "graded_on": None,
                        "comment": "",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "students.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(StorageError, match=r"students\.json"):
        JsonStudentRepository(tmp_path)
    assert path.read_bytes() == before


def test_repository_refuses_saving_student_from_another_rubric(tmp_path):
    rubrics = JsonRubricRepository(tmp_path)
    rubric = rubrics.get()
    rubric.add("ДЗ", Decimal("10"), Decimal("1"))
    rubrics.save(rubric)
    students = JsonStudentRepository(tmp_path, rubrics)
    student = Student(students.next_id(), "А")
    students.save(student)
    before = (tmp_path / "students.json").read_bytes()
    other = Rubric()
    criterion = other.add("ДЗ", Decimal("100"), Decimal("1"))
    student.grade(EvaluationFactory().create(other, criterion.id, Decimal("12")), other)
    with pytest.raises(DomainError, match="от 0 до 10"):
        students.save(student)
    assert (tmp_path / "students.json").read_bytes() == before
    assert students.get(student.id).evaluations == ()
