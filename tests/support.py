from datetime import date
from decimal import Decimal

from dependency_injector import providers

from pos.adapters.memory import InMemoryRubricRepository, InMemoryStudentRepository
from pos.container import Container
from pos.domain.rubric import Criterion
from pos.domain.values import CriterionId

TODAY = date(2026, 11, 3)


def make_container() -> Container:
    container = Container()
    container.students.override(providers.Singleton(InMemoryStudentRepository))
    container.rubrics.override(providers.Singleton(InMemoryRubricRepository))
    return container


def make_criterion(
    number: int = 1, name: str = "ДЗ-1", max_score: str = "10", weight: str = "1"
) -> Criterion:
    return Criterion(CriterionId(number), name, Decimal(max_score), Decimal(weight))


class ScriptedConsole:
    def __init__(self, *answers: str) -> None:
        self._answers = list(answers)
        self.lines: list[str] = []

    def read(self, prompt: str) -> str:
        if not self._answers:
            raise EOFError
        return self._answers.pop(0)

    def write(self, line: str) -> None:
        self.lines.append(line)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def run_app(container: Container, *answers: str) -> ScriptedConsole:
    console = ScriptedConsole(*answers)
    app = container.console(read=console.read, write=console.write, today=lambda: TODAY)
    app.run()
    return console
