from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class DifficultyLevel(str, enum.Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExerciseType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    NUMERIC = "numeric"
    ALGEBRA = "algebra"


class Grade(Base):
    __tablename__ = "grades"
    
    id = Column(Integer, primary_key=True, index=True)
    grade_number = Column(Integer, unique=True, nullable=False)  # 5, 6, 7
    
    # Relationships
    topics = relationship("Topic", back_populates="grade", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Grade {self.grade_number}>"


class Topic(Base):
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True, index=True)
    grade_id = Column(Integer, ForeignKey("grades.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Relationships
    grade = relationship("Grade", back_populates="topics")
    lessons = relationship("Lesson", back_populates="topic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Topic {self.title}>"


class Lesson(Base):
    __tablename__ = "lessons"
    
    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text)  # Markdown or text explanation
    
    # Relationships
    topic = relationship("Topic", back_populates="lessons")
    exercises = relationship("Exercise", back_populates="lesson", cascade="all, delete-orphan")
    generated_contents = relationship("GeneratedLessonContent", back_populates="lesson", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Lesson {self.title}>"


class Exercise(Base):
    __tablename__ = "exercises"
    
    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    question = Column(Text, nullable=False)  # Supports LaTeX
    answer = Column(String(255), nullable=False)  # Correct answer
    solution = Column(Text)  # Step-by-step explanation
    # values_callable: SQLAlchemy's Enum column persists the member NAME
    # ("EASY") by default, not its value ("easy"). Every CHECK constraint,
    # seed JSON file, and raw-SQL read path in this codebase expects the
    # lowercase value, so without this every ORM insert violates the DB
    # constraint (see supabase_schema.sql's difficulty/exercise_type CHECKs).
    difficulty = Column(
        Enum(DifficultyLevel, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=DifficultyLevel.MEDIUM,
    )
    exercise_type = Column(
        Enum(ExerciseType, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=ExerciseType.NUMERIC,
    )
    
    # Relationships
    lesson = relationship("Lesson", back_populates="exercises")
    attempts = relationship("ExerciseAttempt", back_populates="exercise", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Exercise {self.id}: {self.question[:50]}>"


class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # Will link to User model later
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    submitted_answer = Column(String(255), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    exercise = relationship("Exercise", back_populates="attempts")
    
    def __repr__(self):
        status = "✓" if self.is_correct is True else "✗"
        return f"<ExerciseAttempt {self.id}: {status}>"


class GeneratedLessonContent(Base):
    """Cache for AI-generated lesson theory and examples by detail level."""
    __tablename__ = "generated_lesson_content"
    __table_args__ = (
        UniqueConstraint("lesson_id", "detail_level", name="uq_generated_lesson_content_lesson_level"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    # detail_level: 'concise' | 'standard' | 'detailed' | 'examples'
    detail_level = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lesson = relationship("Lesson", back_populates="generated_contents")

    def __repr__(self):
        return f"<GeneratedLessonContent lesson={self.lesson_id} level={self.detail_level}>"
