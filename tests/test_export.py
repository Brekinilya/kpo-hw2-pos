import json
from decimal import Decimal

import pytest
from dependency_injector import providers

from pos.adapters.grade_files import FileGradeSheetExporter
from pos.application.ports import ExportError, GradeSheetExporter
from pos.application.views import FinalGradeView, GradeSheet
from tests.support import make_container

SHEET = GradeSheet(
    "взвешенный балл",
    (
        FinalGradeView(1, "Иванов Иван", Decimal("7.50"), 2, 3),
        FinalGradeView(2, "Петрова, Анна", Decimal("10.00"), 3, 3),
    ),
)


def test_csv_export_opens_in_spreadsheets(tmp_path):
    path = tmp_path / "grades.csv"
    FileGradeSheetExporter().export(str(path), SHEET)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert path.read_text(encoding="utf-8-sig").splitlines() == [
        "ID,Студент,Итог,Оценено критериев,Всего критериев",
        "1,Иванов Иван,7.5,2,3",
        '2,"Петрова, Анна",10,3,3',
    ]


def test_json_export_keeps_rule_and_numbers(tmp_path):
    path = tmp_path / "grades.json"
    FileGradeSheetExporter().export(str(path), SHEET)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["rule"] == "взвешенный балл"
    assert document["grades"][0] == {
        "id": 1,
        "student": "Иванов Иван",
        "grade": 7.5,
        "evaluated": 2,
        "criteria": 3,
    }


def test_export_needs_known_format(tmp_path):
    with pytest.raises(ExportError, match=r"\.csv или \.json"):
        FileGradeSheetExporter().export(str(tmp_path / "grades.xlsx"), SHEET)


def test_export_reports_write_failure(tmp_path):
    with pytest.raises(ExportError, match="не удалось записать"):
        FileGradeSheetExporter().export(str(tmp_path / "missing" / "grades.csv"), SHEET)


class RecordingExporter(GradeSheetExporter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, GradeSheet]] = []

    def export(self, location, sheet):
        self.calls.append((location, sheet))


def test_export_scenario_passes_sheet_of_chosen_rule():
    container = make_container()
    container.rubric_service().add("ДЗ", Decimal("10"), Decimal("1"))
    container.student_service().enroll("Иванов Иван")
    container.grading().grade(1, 1, Decimal("7.5"))
    exporter = RecordingExporter()
    container.exporter.override(providers.Object(exporter))
    assert container.grade_export().run("итоги.csv", "final") == 1
    [(location, sheet)] = exporter.calls
    assert location == "итоги.csv"
    assert sheet.grades[0].grade == Decimal("8.00")
