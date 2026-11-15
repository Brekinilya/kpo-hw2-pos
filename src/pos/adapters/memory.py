from pos.domain.repositories import RubricRepository, StudentRepository
from pos.domain.rubric import Rubric
from pos.domain.student import Student
from pos.domain.values import StudentId


class InMemoryStudentRepository(StudentRepository):
    def __init__(self) -> None:
        self._students: dict[StudentId, Student] = {}
        self._last_id = 0

    def next_id(self) -> StudentId:
        self._last_id += 1
        return StudentId(self._last_id)

    def find(self, student_id: StudentId) -> Student | None:
        return self._students.get(student_id)

    def all(self) -> tuple[Student, ...]:
        return tuple(sorted(self._students.values(), key=lambda student: student.id.value))

    def save(self, student: Student) -> None:
        self._students[student.id] = student

    def remove(self, student_id: StudentId) -> None:
        self._students.pop(student_id, None)


class InMemoryRubricRepository(RubricRepository):
    def __init__(self) -> None:
        self._rubric = Rubric()

    def get(self) -> Rubric:
        return self._rubric

    def save(self, rubric: Rubric) -> None:
        self._rubric = rubric
