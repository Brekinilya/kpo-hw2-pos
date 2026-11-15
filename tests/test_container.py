from pos.adapters.console import ConsoleApp
from pos.adapters.json_storage import JsonStudentRepository
from pos.adapters.memory import InMemoryStudentRepository
from pos.container import Container
from pos.domain.grading import EvaluatedAverage, HalfUpRounding, WeightedTotal
from tests.support import make_container


def test_default_wiring_stores_data_in_configured_folder(tmp_path):
    container = Container()
    container.config.data_dir.from_value(str(tmp_path))
    assert isinstance(container.students(), JsonStudentRepository)
    assert isinstance(container.console(), ConsoleApp)
    container.student_service().enroll("Иванов Иван")
    assert (tmp_path / "students.json").exists()


def test_repositories_are_replaced_through_container():
    container = make_container()
    assert isinstance(container.students(), InMemoryStudentRepository)
    container.student_service().enroll("Иванов Иван")
    assert container.students().all()[0].name == "Иванов Иван"


def test_services_share_one_repository_instance():
    container = make_container()
    container.student_service().enroll("Иванов Иван")
    assert container.grading().evaluations(1) == ()


def test_rules_combine_strategies_with_rounding_decorator():
    rules = Container.rules()
    assert isinstance(rules["final"], HalfUpRounding)
    assert isinstance(rules["exact"], WeightedTotal)
    assert isinstance(rules["interim"], EvaluatedAverage)
