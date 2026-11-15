from pos.application.grading import GradingService
from pos.application.ports import GradeSheetExporter


class GradeSheetExport:
    def __init__(self, grading: GradingService, exporter: GradeSheetExporter) -> None:
        self._grading = grading
        self._exporter = exporter

    def run(self, location: str, rule: str) -> int:
        sheet = self._grading.final_grades(rule)
        self._exporter.export(location, sheet)
        return len(sheet.grades)
