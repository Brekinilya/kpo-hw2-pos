import json
import re
from pathlib import Path

import pytest

from pos.adapters.statement_files import FileStatementSource
from pos.application.ports import StatementEntry, StatementSourceError


def write(path: Path, text: str, encoding: str = "utf-8") -> str:
    path.write_text(text, encoding=encoding)
    return str(path)


def read(location: str) -> list[StatementEntry]:
    return FileStatementSource().read(location)


def test_csv_statement_turns_cells_into_entries(tmp_path):
    location = write(
        tmp_path / "statement.csv",
        "Студент,ДЗ,Экзамен\nИванов Иван,8,7.5\nПетрова Анна,10,\n",
    )
    assert read(location) == [
        StatementEntry("строка 2", "Иванов Иван", "ДЗ", "8"),
        StatementEntry("строка 2", "Иванов Иван", "Экзамен", "7.5"),
        StatementEntry("строка 3", "Петрова Анна", "ДЗ", "10"),
    ]


def test_csv_with_semicolons_and_decimal_commas(tmp_path):
    location = write(
        tmp_path / "statement.csv",
        "Студент;ДЗ;Экзамен\nИванов Иван;7,5;9\n\nПетрова Анна;10\n",
        encoding="utf-8-sig",
    )
    assert [(entry.source, entry.criterion, entry.points) for entry in read(location)] == [
        ("строка 2", "ДЗ", "7,5"),
        ("строка 2", "Экзамен", "9"),
        ("строка 4", "ДЗ", "10"),
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "ведомость пуста"),
        ("Студент\nИванов\n", "хотя бы один критерий"),
        ("Студент,ДЗ,\nИванов,1,2\n", "без названия"),
        ("Студент,ДЗ,дз\nИванов,1,2\n", "повторяются"),
        ("Студент,ДЗ\nИванов,1,2\n", "строка 2: значений больше"),
    ],
)
def test_malformed_csv_is_rejected_as_a_whole(tmp_path, text, message):
    with pytest.raises(StatementSourceError, match=message):
        read(write(tmp_path / "statement.csv", text))


def test_json_statement_accepts_numbers_strings_and_nulls(tmp_path):
    document = {
        "students": [
            {"name": "Иванов Иван", "scores": {"ДЗ": 8, "Экзамен": "7,5", "Доклад": None}},
            {"name": "Петрова Анна", "scores": {"ДЗ": 9.25}},
        ]
    }
    location = write(tmp_path / "statement.json", json.dumps(document, ensure_ascii=False))
    assert read(location) == [
        StatementEntry("студент 1", "Иванов Иван", "ДЗ", "8"),
        StatementEntry("студент 1", "Иванов Иван", "Экзамен", "7,5"),
        StatementEntry("студент 2", "Петрова Анна", "ДЗ", "9.25"),
    ]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{", "некорректный JSON: строка 1"),
        ("[]", "массивом students"),
        ('{"students": {}}', "массивом students"),
        ('{"students": [1]}', "студент 1: ожидается объект"),
        ('{"students": [{"name": "Иванов"}]}', "студент 1: ожидается объект"),
        ('{"students": [{"name": "Иванов", "scores": {"ДЗ": true}}]}', "должен быть числом"),
    ],
)
def test_malformed_json_is_rejected_as_a_whole(tmp_path, text, message):
    with pytest.raises(StatementSourceError, match=re.escape(message)):
        read(write(tmp_path / "statement.json", text))


def test_csv_reader_failure_is_reported(tmp_path):
    location = write(tmp_path / "statement.csv", "Студент,ДЗ\nИванов," + "9" * 200_000 + "\n")
    with pytest.raises(StatementSourceError, match="некорректный CSV"):
        read(location)


def test_unsupported_extension_is_rejected(tmp_path):
    with pytest.raises(StatementSourceError, match=r"\.csv или \.json"):
        read(write(tmp_path / "statement.txt", "Студент,ДЗ"))


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(StatementSourceError, match="файл не найден"):
        read(str(tmp_path / "missing.csv"))


def test_directory_is_not_a_statement(tmp_path):
    folder = tmp_path / "folder.csv"
    folder.mkdir()
    with pytest.raises(StatementSourceError, match="не удалось прочитать"):
        read(str(folder))


def test_statement_must_be_utf8(tmp_path):
    location = write(tmp_path / "statement.csv", "Студент,ДЗ\nИванов,5\n", encoding="cp1251")
    with pytest.raises(StatementSourceError, match="UTF-8"):
        read(location)
