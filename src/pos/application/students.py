from pos.application.views import StudentView, student_view
from pos.domain.repositories import StudentRepository
from pos.domain.student import Student
from pos.domain.values import StudentId


class StudentService:
    def __init__(self, students: StudentRepository) -> None:
        self._students = students

    def enroll(self, name: str) -> StudentView:
        student = Student(self._students.next_id(), name)
        self._students.save(student)
        return student_view(student)

    def rename(self, student_id: int, name: str) -> StudentView:
        student = self._students.get(StudentId(student_id))
        student.rename(name)
        self._students.save(student)
        return student_view(student)

    def remove(self, student_id: int) -> StudentView:
        student = self._students.get(StudentId(student_id))
        self._students.remove(student.id)
        return student_view(student)

    def all(self) -> tuple[StudentView, ...]:
        return tuple(student_view(student) for student in self._students.all())
