"""מבנה הנתונים: איך נראית שאלה, ואיך נראה ה"תיק" המשותף של הגרף (State)."""
from typing import Literal, Optional, TypedDict

from pydantic import BaseModel, Field


# ---------- מה המודל מחזיר (פלט מובנה) ----------

class MCQ(BaseModel):
    """שאלה אמריקאית אחת כפי שהמודל מייצר אותה."""

    question: str = Field(description="נוסח השאלה")
    options: list[str] = Field(description="בדיוק 4 תשובות אפשריות", min_length=4, max_length=4)
    correct_index: int = Field(description="מספר התשובה הנכונה, 0 עד 3", ge=0, le=3)
    source_quote: str = Field(description="המשפט מתוך הטקסט שממנו אפשר להסיק את התשובה הנכונה")


class MCQSet(BaseModel):
    """קבוצת שאלות שהמחולל מחזיר."""

    questions: list[MCQ]


class Verdict(BaseModel):
    """פסק הדין של הבודק על שאלה אחת."""

    answerable_from_text: bool = Field(description="האם אפשר לענות על השאלה רק מתוך הטקסט")
    single_correct_answer: bool = Field(description="האם יש בדיוק תשובה נכונה אחת, והיא זו המסומנת")
    reason: str = Field(description="אם השאלה פסולה - מה בדיוק הבעיה. אם תקינה - מחרוזת ריקה")


# ---------- מה נשמר בתיק המשותף ----------

Status = Literal["pending", "valid", "invalid", "flagged", "approved"]
# pending  - עוד לא נבדקה
# valid    - הבודק אישר
# invalid  - הבודק פסל, תיכתב מחדש
# flagged  - נפסלה גם אחרי כל הניסיונות, תגיע למורה עם אזהרה
# approved - המורה אישר או ערך


class QuestionItem(TypedDict):
    id: int
    question: str
    options: list[str]
    correct_index: int
    source_quote: str
    status: Status
    attempts: int          # כמה פעמים נכתבה מחדש
    feedback: str          # סיבת הפסילה האחרונה
    edited_by_teacher: bool


class QuizState(TypedDict, total=False):
    source_text: str
    questions: list[QuestionItem]
    to_generate: int            # כמה שאלות חדשות המחולל צריך לייצר
    next_id: int                # מונה למספור שאלות
    replacement_round: int      # כמה סבבי חלופות כבר היו
    deleted_count: int          # כמה שאלות המורה מחק בסבב האחרון
    deleted_questions: list[str]  # נוסחי כל השאלות שהמורה מחק - כדי שהמחולל לא ייצר אותן שוב
    title: str                  # כותרת המסמך, נקבעת על ידי המורה
    export_paths: Optional[dict]  # {"student": ..., "teacher": ...}
