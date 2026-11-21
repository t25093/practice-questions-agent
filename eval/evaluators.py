"""המעריך: "שופט" (מודל אחר מהנבחן) שנותן ציון לשאלות שהסוכן הציג למורה.

שני ציונים נפרדים, כל אחד = אחוז השאלות שעברו:
  grounded        - השאלה מבוססת על הטקסט (אפשר לענות עליה רק ממנו)
  answer_correct  - התשובה המסומנת נכונה באמת (גם בעולם האמיתי), ואין תשובה נכונה נוספת

ההפרדה חשובה: אם הטקסט עצמו שגוי, שאלה יכולה להיות "מבוססת" אבל לא "נכונה".
"""
import sys
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from quiz_agent.config import JUDGE_MODEL, get_llm  # noqa: E402

JUDGE_PROMPT = """אתה שופט קפדן של שאלות אמריקאיות שנוצרו מתוך חומר לימוד.

הטקסט:
<<<
{source_text}
>>>

השאלות:
{questions}

לכל שאלה קבע שני דברים בנפרד:
1. grounded – האם אפשר לענות על השאלה רק מתוך הטקסט, בלי ידע חיצוני?
2. answer_correct – האם התשובה המסומנת נכונה באמת, לפי הידע שלך על העולם (לא רק לפי הטקסט),
   והאם כל שאר התשובות שגויות? אם יש עוד תשובה נכונה, או שהתשובה המסומנת שגויה – false.
הסבר בקצרה כל false."""


class QuestionJudgement(BaseModel):
    index: int = Field(description="מספר השאלה")
    grounded: bool
    answer_correct: bool
    reason: str = Field(description="הסבר קצר אם אחד מהם false, אחרת מחרוזת ריקה")


class Judgement(BaseModel):
    judgements: list[QuestionJudgement]


def _format(questions) -> str:
    parts = []
    for i, q in enumerate(questions, start=1):
        opts = "\n".join(f"   {j}. {o}" for j, o in enumerate(q["options"], start=1))
        parts.append(f"--- שאלה {i} ---\n{q['question']}\n{opts}\n"
                     f"   התשובה המסומנת: {q['correct_index'] + 1}")
    return "\n\n".join(parts)


def judge(inputs: dict, outputs: dict) -> list[dict]:
    """מעריך LangSmith: מחזיר שני ציונים לכל דוגמה."""
    questions = outputs.get("questions", [])
    if not questions:
        return [{"key": "grounded", "score": 0}, {"key": "answer_correct", "score": 0}]

    llm = get_llm(temperature=0, model=JUDGE_MODEL).with_structured_output(Judgement, method="json_schema")
    result: Judgement = llm.invoke(
        JUDGE_PROMPT.format(source_text=inputs["source_text"], questions=_format(questions))
    )
    js = result.judgements[: len(questions)]
    n = len(questions)
    grounded = sum(j.grounded for j in js) / n
    correct = sum(j.answer_correct for j in js) / n
    problems = "\n".join(f"שאלה {j.index}: {j.reason}" for j in js if j.reason)
    return [
        {"key": "grounded", "score": grounded, "comment": problems},
        {"key": "answer_correct", "score": correct, "comment": problems},
    ]
