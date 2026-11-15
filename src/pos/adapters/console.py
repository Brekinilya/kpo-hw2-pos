from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pos.application.export import GradeSheetExport
from pos.application.grading import GradingService
from pos.application.ports import ExportError, StatementSourceError
from pos.application.rubric import RubricService
from pos.application.statements import StatementImport
from pos.application.students import StudentService
from pos.application.views import EvaluationView, RuleView
from pos.domain.errors import DomainError
from pos.domain.repositories import StorageError
from pos.domain.values import plain

Reader = Callable[[str], str]
Writer = Callable[[str], None]
Action = Callable[[], None]

_FAILURES = (DomainError, StorageError, StatementSourceError, ExportError)


class _CancelledError(Exception):
    pass


class ConsoleApp:
    def __init__(
        self,
        students: StudentService,
        rubric: RubricService,
        grading: GradingService,
        statements: StatementImport,
        export: GradeSheetExport,
        read: Reader = input,
        write: Writer = print,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._students = students
        self._rubric = rubric
        self._grading = grading
        self._statements = statements
        self._export = export
        self._read = read
        self._write = write
        self._today = today

    def run(self) -> None:
        self._write("ПОС — преподавательская оценка студентов. Обратная связь — спорт для двоих!")
        try:
            self._menu(
                "Главное меню",
                [
                    ("Студенты", self._students_menu),
                    ("Рубрикатор", self._rubric_menu),
                    ("Оценки", self._evaluations_menu),
                    ("Итоги", self._results_menu),
                    ("Импорт ведомости (CSV/JSON)", self._import_statement),
                    ("Экспорт итогов (CSV/JSON)", self._export_grades),
                ],
                exit_label="Выход",
            )
        except EOFError:
            self._write("")
        self._write("Работа завершена.")

    def _menu(
        self, title: str, items: Sequence[tuple[str, Action]], exit_label: str = "Назад"
    ) -> None:
        while True:
            self._write("")
            self._write(f"== {title} ==")
            for number, (label, _) in enumerate(items, 1):
                self._write(f"{number}. {label}")
            self._write(f"0. {exit_label}")
            choice = self._read("> ").strip()
            if choice == "0":
                return
            if not choice.isdecimal() or not 1 <= int(choice) <= len(items):
                self._write("Нет такого пункта.")
                continue
            try:
                items[int(choice) - 1][1]()
            except _CancelledError as reason:
                self._write(str(reason))
            except _FAILURES as error:
                self._write(f"Ошибка: {error}")

    def _students_menu(self) -> None:
        self._menu(
            "Студенты",
            [
                ("Список", self._show_students),
                ("Добавить", self._enroll_student),
                ("Переименовать", self._rename_student),
                ("Удалить", self._remove_student),
            ],
        )

    def _rubric_menu(self) -> None:
        self._menu(
            "Рубрикатор",
            [
                ("Список критериев", self._show_criteria),
                ("Добавить критерий", self._add_criterion),
                ("Изменить название или вес", self._edit_criterion),
                ("Удалить критерий", self._remove_criterion),
            ],
        )

    def _evaluations_menu(self) -> None:
        self._menu(
            "Оценки",
            [
                ("Выставить оценку", self._grade),
                ("Оценки студента", self._show_evaluations),
                ("Исправить оценку", self._correct),
                ("Отменить оценку", self._cancel),
            ],
        )

    def _results_menu(self) -> None:
        self._menu(
            "Итоги",
            [
                ("Итог студента", self._show_final_grade),
                ("Итоги всех студентов", self._show_final_grades),
            ],
        )

    def _show_students(self) -> None:
        students = self._students.all()
        if not students:
            raise _CancelledError("Студентов пока нет.")
        self._table(
            ("ID", "Студент", "Оценок"),
            [(str(student.id), student.name, str(student.evaluated)) for student in students],
        )

    def _enroll_student(self) -> None:
        student = self._students.enroll(self._read("Имя студента: "))
        self._write(f"Добавлен студент «{student.name}», ID {student.id}.")

    def _rename_student(self) -> None:
        student_id = self._pick_student()
        student = self._students.rename(student_id, self._read("Новое имя: "))
        self._write(f"Студент ID {student.id} теперь «{student.name}».")

    def _remove_student(self) -> None:
        student = self._students.remove(self._pick_student())
        self._write(f"Удалён студент «{student.name}» и его оценки ({student.evaluated}).")

    def _show_criteria(self) -> None:
        criteria = self._rubric.all()
        if not criteria:
            raise _CancelledError("Рубрикатор пуст.")
        self._table(
            ("ID", "Критерий", "Макс.", "Вес", "Доля в итоге"),
            [
                (
                    str(criterion.id),
                    criterion.name,
                    plain(criterion.max_score),
                    plain(criterion.weight),
                    f"{plain(criterion.share_percent)}%",
                )
                for criterion in criteria
            ],
        )

    def _add_criterion(self) -> None:
        name = self._read("Название критерия: ")
        max_score = self._ask_decimal("Максимальный балл: ")
        weight = self._ask_decimal("Вес в итоге: ")
        criterion = self._rubric.add(name, max_score, weight)
        self._write(f"Добавлен критерий «{criterion.name}», ID {criterion.id}.")

    def _edit_criterion(self) -> None:
        criterion_id = self._pick_criterion()
        name = self._read("Новое название (Enter — оставить): ").strip()
        weight = self._ask_optional_decimal("Новый вес (Enter — оставить): ")
        changed = None
        if name:
            changed = self._rubric.rename(criterion_id, name)
        if weight is not None:
            changed = self._rubric.reweigh(criterion_id, weight)
        if changed is None:
            self._write("Без изменений.")
            return
        self._write(
            f"Критерий ID {changed.id}: «{changed.name}», вес {plain(changed.weight)}, "
            f"доля в итоге {plain(changed.share_percent)}%."
        )

    def _remove_criterion(self) -> None:
        criterion = self._rubric.remove(self._pick_criterion())
        self._write(f"Удалён критерий «{criterion.name}».")

    def _grade(self) -> None:
        student_id = self._pick_student()
        criterion_id = self._pick_criterion()
        points = self._ask_decimal("Балл: ")
        graded_on = self._ask_date()
        comment = self._read("Комментарий (Enter — без комментария): ")
        evaluation = self._grading.grade(student_id, criterion_id, points, graded_on, comment)
        self._write(f"Выставлено: {_describe(evaluation)}.")

    def _show_evaluations(self) -> None:
        self._print_evaluations(self._pick_student())

    def _correct(self) -> None:
        student_id = self._pick_student()
        criterion_id = self._pick_evaluation(student_id)
        points = self._ask_decimal("Новый балл: ")
        graded_on = self._ask_date()
        comment = self._read("Комментарий (Enter — без комментария): ")
        evaluation = self._grading.correct(student_id, criterion_id, points, graded_on, comment)
        self._write(f"Исправлено: {_describe(evaluation)}.")

    def _cancel(self) -> None:
        student_id = self._pick_student()
        evaluation = self._grading.cancel(student_id, self._pick_evaluation(student_id))
        self._write(f"Отменено: {_describe(evaluation)}.")

    def _show_final_grade(self) -> None:
        student_id = self._pick_student()
        rule = self._pick_rule()
        self._print_evaluations(student_id)
        grade = self._grading.final_grade(student_id, rule.key)
        self._write(
            f"Итог «{grade.student}»: {plain(grade.grade)} из 10 "
            f"(оценено {grade.evaluated} из {grade.criteria} критериев; {rule.title})."
        )

    def _show_final_grades(self) -> None:
        rule = self._pick_rule()
        sheet = self._grading.final_grades(rule.key)
        if not sheet.grades:
            raise _CancelledError("Студентов пока нет.")
        self._write(f"Итоги: {sheet.rule}.")
        self._table(
            ("ID", "Студент", "Итог", "Оценено"),
            [
                (
                    str(grade.student_id),
                    grade.student,
                    plain(grade.grade),
                    f"{grade.evaluated} из {grade.criteria}",
                )
                for grade in sheet.grades
            ],
        )

    def _import_statement(self) -> None:
        location = self._ask_path("Путь к ведомости (.csv или .json): ")
        outcomes = self._statements.run(location)
        for outcome in outcomes:
            mark = "принято" if outcome.accepted else "отказ"
            entry = outcome.entry
            self._write(
                f"[{mark}] {entry.source}, {entry.student.strip()}, «{entry.criterion.strip()}» "
                f"= {entry.points}: {outcome.message}"
            )
        accepted = sum(1 for outcome in outcomes if outcome.accepted)
        self._write(f"Принято {accepted} из {len(outcomes)}.")

    def _export_grades(self) -> None:
        rule = self._pick_rule()
        location = self._ask_path("Файл для итогов (.csv или .json): ")
        count = self._export.run(location, rule.key)
        self._write(f"Сохранено итогов: {count}, файл {location}.")

    def _print_evaluations(self, student_id: int) -> bool:
        evaluations = self._grading.evaluations(student_id)
        if not evaluations:
            self._write("Оценок пока нет.")
            return False
        self._table(
            ("ID", "Критерий", "Балл", "Дата", "Комментарий"),
            [
                (
                    str(evaluation.criterion_id),
                    evaluation.criterion,
                    f"{plain(evaluation.points)} из {plain(evaluation.out_of)}",
                    _date(evaluation.graded_on),
                    evaluation.comment,
                )
                for evaluation in evaluations
            ],
        )
        return True

    def _pick_student(self) -> int:
        self._show_students()
        return self._ask_id("ID студента: ")

    def _pick_criterion(self) -> int:
        self._show_criteria()
        return self._ask_id("ID критерия: ")

    def _pick_evaluation(self, student_id: int) -> int:
        if not self._print_evaluations(student_id):
            raise _CancelledError("Исправлять и отменять нечего.")
        return self._ask_id("ID критерия: ")

    def _pick_rule(self) -> RuleView:
        rules = self._grading.rules()
        self._write("Правила итога:")
        for number, rule in enumerate(rules, 1):
            self._write(f"{number}. {rule.title}")
        while True:
            choice = self._read("Правило (Enter — 1): ").strip() or "1"
            if choice.isdecimal() and 1 <= int(choice) <= len(rules):
                return rules[int(choice) - 1]
            self._write("Нет такого правила.")

    def _ask_id(self, prompt: str) -> int:
        while True:
            text = self._read(prompt).strip()
            if text.isdecimal():
                return int(text)
            self._write("Введите целое число.")

    def _ask_decimal(self, prompt: str) -> Decimal:
        while True:
            value = self._ask_optional_decimal(prompt)
            if value is not None:
                return value
            self._write("Введите число, например 7.5.")

    def _ask_optional_decimal(self, prompt: str) -> Decimal | None:
        while True:
            text = self._read(prompt).strip().replace(",", ".")
            if not text:
                return None
            try:
                value = Decimal(text)
            except InvalidOperation:
                value = None
            if value is not None and value.is_finite():
                return value
            self._write("Введите число, например 7.5.")

    def _ask_date(self) -> date:
        while True:
            text = self._read("Дата (ДД.ММ.ГГГГ, Enter — сегодня): ").strip()
            if not text:
                return self._today()
            try:
                return datetime.strptime(text, "%d.%m.%Y").date()
            except ValueError:
                self._write("Введите дату в виде ДД.ММ.ГГГГ, например 03.11.2026.")

    def _ask_path(self, prompt: str) -> str:
        location = self._read(prompt).strip().strip('"')
        if not location:
            raise _CancelledError("Путь не указан.")
        return location

    def _table(self, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
        widths = [max(len(cell) for cell in column) for column in zip(header, *rows, strict=True)]
        for row in (header, *rows):
            self._write(
                "  ".join(
                    cell.ljust(width) for cell, width in zip(row, widths, strict=True)
                ).rstrip()
            )


def _date(value: date | None) -> str:
    return "—" if value is None else value.strftime("%d.%m.%Y")


def _describe(evaluation: EvaluationView) -> str:
    return f"«{evaluation.criterion}» — {plain(evaluation.points)} из {plain(evaluation.out_of)}"
