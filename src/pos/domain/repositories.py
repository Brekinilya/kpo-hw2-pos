from abc import ABC, abstractmethod

from pos.domain.errors import DomainError
from pos.domain.rubric import Rubric
from pos.domain.student import Student
from pos.domain.values import StudentId


class StorageError(Exception):
    pass


class StudentRepository(ABC):
    @abstractmethod
    def next_id(self) -> StudentId: ...

    @abstractmethod
    def find(self, student_id: StudentId) -> Student | None: ...

    @abstractmethod
    def all(self) -> tuple[Student, ...]: ...

    @abstractmethod
    def save(self, student: Student) -> None: ...

    @abstractmethod
    def remove(self, student_id: StudentId) -> None: ...

    def get(self, student_id: StudentId) -> Student:
        student = self.find(student_id)
        if student is None:
            raise DomainError(f"студента с ID {student_id.value} нет")
        return student


class RubricRepository(ABC):
    @abstractmethod
    def get(self) -> Rubric: ...

    @abstractmethod
    def save(self, rubric: Rubric) -> None: ...
