import csv
import io
import json
from pathlib import Path

from pos.application.ports import ExportError, GradeSheetExporter
from pos.application.views import GradeSheet
from pos.domain.values import plain


class FileGradeSheetExporter(GradeSheetExporter):
    def export(self, location: str, sheet: GradeSheet) -> None:
        path = Path(location)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            content, encoding = _as_csv(sheet), "utf-8-sig"
        elif suffix == ".json":
            content, encoding = _as_json(sheet), "utf-8"
        else:
            raise ExportError("итоги можно сохранить в формате .csv или .json")
        try:
            path.write_text(content, encoding=encoding, newline="")
        except OSError:
            raise ExportError(f"не удалось записать файл: {path}") from None


def _as_csv(sheet: GradeSheet) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["ID", "Студент", "Итог", "Оценено критериев", "Всего критериев"])
    for grade in sheet.grades:
        writer.writerow(
            [grade.student_id, grade.student, plain(grade.grade), grade.evaluated, grade.criteria]
        )
    return buffer.getvalue()


def _as_json(sheet: GradeSheet) -> str:
    document = {
        "rule": sheet.rule,
        "grades": [
            {
                "id": grade.student_id,
                "student": grade.student,
                "grade": float(grade.grade),
                "evaluated": grade.evaluated,
                "criteria": grade.criteria,
            }
            for grade in sheet.grades
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
