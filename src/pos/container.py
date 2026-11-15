from types import MappingProxyType

from dependency_injector import containers, providers

from pos.adapters.console import ConsoleApp
from pos.adapters.grade_files import FileGradeSheetExporter
from pos.adapters.json_storage import JsonRubricRepository, JsonStudentRepository
from pos.adapters.statement_files import FileStatementSource
from pos.application.export import GradeSheetExport
from pos.application.grading import GradingService
from pos.application.rubric import RubricService
from pos.application.statements import StatementImport
from pos.application.students import StudentService
from pos.domain.evaluation import EvaluationFactory
from pos.domain.grading import EvaluatedAverage, HalfUpRounding, WeightedTotal
from pos.domain.services import FinalGradeCalculator

DEFAULT_DATA_DIR = "pos-data"


class Container(containers.DeclarativeContainer):
    config = providers.Configuration(default={"data_dir": DEFAULT_DATA_DIR})

    rubrics = providers.Singleton(JsonRubricRepository, config.data_dir)
    students = providers.Singleton(JsonStudentRepository, config.data_dir, rubrics)

    evaluation_factory = providers.Singleton(EvaluationFactory)
    calculator = providers.Singleton(FinalGradeCalculator)
    rules = providers.Object(
        MappingProxyType(
            {
                "final": HalfUpRounding(WeightedTotal()),
                "exact": WeightedTotal(),
                "interim": EvaluatedAverage(),
            }
        )
    )

    student_service = providers.Singleton(StudentService, students)
    rubric_service = providers.Singleton(RubricService, rubrics, students)
    grading = providers.Singleton(
        GradingService, students, rubrics, evaluation_factory, calculator, rules
    )

    statement_source = providers.Singleton(FileStatementSource)
    statement_import = providers.Singleton(
        StatementImport, statement_source, students, rubrics, evaluation_factory
    )
    exporter = providers.Singleton(FileGradeSheetExporter)
    grade_export = providers.Singleton(GradeSheetExport, grading, exporter)

    console = providers.Factory(
        ConsoleApp, student_service, rubric_service, grading, statement_import, grade_export
    )
