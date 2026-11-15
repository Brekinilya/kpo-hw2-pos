import json

from pos.container import Container
from tests.support import make_container, run_app

RUBRIC = ("2", "2", "ДЗ", "10", "0.4", "2", "Экзамен", "10", "0.6", "0")
STUDENTS = ("1", "2", "Иванов Иван", "2", "Петрова Анна", "0")


def test_end_to_end_scenario_from_rubric_to_export(tmp_path):
    export_path = tmp_path / "итоги.json"
    console = run_app(
        make_container(),
        *RUBRIC,
        *STUDENTS,
        "3",
        *("1", "1", "1", "12", "", ""),
        *("1", "1", "1", "8", "", "молодец"),
        *("1", "1", "2", "7", "01.11.2026", ""),
        *("1", "2", "1", "10", "", ""),
        "0",
        "4",
        *("1", "1", ""),
        *("2", "3"),
        "0",
        *("6", "", str(export_path)),
        "0",
    )
    text = console.text
    assert "Ошибка: балл 12 вне диапазона критерия: от 0 до 10" in text
    assert "Выставлено: «ДЗ» — 8 из 10." in text
    assert "1   ДЗ        8 из 10  03.11.2026  молодец" in console.lines
    assert "2   Экзамен   7 из 10  01.11.2026" in console.lines
    assert any(
        line.startswith("Итог «Иванов Иван»: 7 из 10 (оценено 2 из 2") for line in console.lines
    )
    assert "1   Иванов Иван   7.4   2 из 2" in console.lines
    assert "2   Петрова Анна  10    1 из 2" in console.lines
    assert f"Сохранено итогов: 2, файл {export_path}." in console.lines
    grades = json.loads(export_path.read_text(encoding="utf-8"))["grades"]
    assert [(grade["student"], grade["grade"]) for grade in grades] == [
        ("Иванов Иван", 7.0),
        ("Петрова Анна", 4.0),
    ]
    assert console.lines[-1] == "Работа завершена."


def test_rubric_lists_shares_and_edits_criteria():
    console = run_app(
        make_container(),
        *RUBRIC[:-1],
        "1",
        *("3", "1", "Домашние задания", "1,4"),
        *("3", "2", "", ""),
        *("4", "1"),
        "1",
        "0",
    )
    assert "ID  Критерий  Макс.  Вес  Доля в итоге" in console.lines
    assert "1   ДЗ        10     0.4  40%" in console.lines
    assert "Критерий ID 1: «Домашние задания», вес 1.4, доля в итоге 70%." in console.lines
    assert "Без изменений." in console.lines
    assert "Удалён критерий «Домашние задания»." in console.lines
    assert "2   Экзамен   10     0.6  100%" in console.lines


def test_students_can_be_renamed_and_removed():
    console = run_app(
        make_container(),
        *STUDENTS[:-1],
        *("3", "2", "Петрова Анна Сергеевна"),
        *("4", "1"),
        "1",
        "0",
    )
    assert "Студент ID 2 теперь «Петрова Анна Сергеевна»." in console.lines
    assert "Удалён студент «Иванов Иван» и его оценки (0)." in console.lines
    assert "2   Петрова Анна Сергеевна  0" in console.lines


def test_corrections_and_cancellations_go_through_menu():
    console = run_app(
        make_container(),
        *RUBRIC,
        *STUDENTS,
        "3",
        *("1", "1", "1", "6", "", ""),
        *("3", "1", "1", "9", "02.11.2026", "апелляция"),
        *("4", "1", "2"),
        *("4", "1", "1"),
        *("4", "2"),
        *("2", "1"),
        "0",
    )
    assert "Исправлено: «ДЗ» — 9 из 10." in console.lines
    assert "Ошибка: у студента «Иванов Иван» нет оценки по критерию с ID 2" in console.lines
    assert "Отменено: «ДЗ» — 9 из 10." in console.lines
    assert "Исправлять и отменять нечего." in console.lines
    assert "Оценок пока нет." in console.lines


def test_input_is_asked_again_until_it_makes_sense():
    console = run_app(
        make_container(),
        *("2", "2", "ДЗ", "десять", "10", "", "1", "0"),
        *STUDENTS,
        "3",
        *("1", "первый", "1", "1", "5", "вчера", "", ""),
        "0",
        *("4", "1", "1", "9", "1"),
        "7",
    )
    text = console.text
    assert text.count("Введите число, например 7.5.") == 2
    assert "Введите целое число." in text
    assert "Введите дату в виде ДД.ММ.ГГГГ, например 03.11.2026." in text
    assert "Нет такого правила." in text
    assert "Нет такого пункта." in text
    assert "Итог «Иванов Иван»: 5 из 10" in text


def test_empty_course_explains_what_is_missing():
    console = run_app(make_container(), "1", "1", "3", "0", "2", "1", "0", "4", "2", "", "0")
    assert console.lines.count("Студентов пока нет.") == 3
    assert "Рубрикатор пуст." in console.lines


def test_import_reports_each_entry(tmp_path):
    statement = tmp_path / "ведомость.csv"
    statement.write_text("Студент,ДЗ,Доклад\nИванов Иван,8,5\nПетрова Анна,12,\n", encoding="utf-8")
    console = run_app(make_container(), *RUBRIC, "5", f'"{statement}"', "5", "", "0")
    summary = console.lines.index("Принято 1 из 3.")
    assert console.lines[summary - 3 : summary + 1] == [
        "[принято] строка 2, Иванов Иван, «ДЗ» = 8: студент добавлен, оценка выставлена",
        "[отказ] строка 2, Иванов Иван, «Доклад» = 5: критерия «Доклад» нет в рубрикаторе",
        "[отказ] строка 3, Петрова Анна, «ДЗ» = 12: балл 12 вне диапазона критерия: от 0 до 10",
        "Принято 1 из 3.",
    ]
    assert "Путь не указан." in console.lines


def test_file_errors_are_shown_without_stopping(tmp_path):
    console = run_app(
        make_container(),
        *("5", str(tmp_path / "нет.csv")),
        *("6", "", str(tmp_path / "итоги.txt")),
        "0",
    )
    assert any(line.startswith("Ошибка: файл не найден") for line in console.lines)
    assert "Ошибка: итоги можно сохранить в формате .csv или .json" in console.lines
    assert console.lines[-1] == "Работа завершена."


def test_data_survive_between_runs(tmp_path):
    def container() -> Container:
        configured = Container()
        configured.config.data_dir.from_value(str(tmp_path))
        return configured

    run_app(container(), *RUBRIC, *STUDENTS, "3", "1", "1", "1", "8", "", "", "0", "0")
    console = run_app(container(), "3", "2", "1", "0", "0")
    assert "1   ДЗ        8 из 10  03.11.2026" in console.lines
