import io
import sys

import pytest

from pos.__main__ import main


class InterruptedInput(io.StringIO):
    def readline(self, size=-1):
        raise KeyboardInterrupt


def test_main_runs_console_on_given_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pos", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    main()
    assert "Работа завершена." in capsys.readouterr().out


def test_main_stops_quietly_on_ctrl_c(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["pos", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", InterruptedInput())
    main()
    assert "Работа завершена." not in capsys.readouterr().out


def test_main_refuses_corrupted_data(tmp_path, monkeypatch, capsys):
    (tmp_path / "students.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pos", str(tmp_path)])
    with pytest.raises(SystemExit) as stopped:
        main()
    assert stopped.value.code == 1
    assert "Не удалось открыть данные" in capsys.readouterr().out
