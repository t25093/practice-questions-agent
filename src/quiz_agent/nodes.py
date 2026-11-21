"""הצמתים של הגרף. כל צומת מקבל את התיק (state) ומחזיר את מה שהשתנה בו."""
from langgraph.types import interrupt

from .config import MAX_REWRITE_ATTEMPTS, get_llm
from .models import MCQ, MCQSet, QuestionItem, QuizState, Verdict
from .prompts import AVOID_DELETED, AVOID_DUPLICATES, GENERATOR_PROMPT, REWRITE_PROMPT, VALIDATOR_PROMPT


def _format_options(options: list[str]) -> str:
    return "\n".join(f"{i}. {opt}" for i, opt in enumerate(options))


def _to_item(mcq: MCQ, qid: int) -> QuestionItem:
    return QuestionItem(
        id=qid,
        question=mcq.question,
        options=list(mcq.options),
        correct_index=mcq.correct_index,
        source_quote=mcq.source_quote,
        status="pending",
        attempts=0,
        feedback="",
        edited_by_teacher=False,
    )


# ---------- ① מחולל ----------

def generate(state: QuizState) -> dict:
    """מייצר שאלות חדשות. בפעם הראשונה 5; בסבב חלופות - כמספר השאלות שנמחקו."""
    existing = state.get("questions", [])
    count = state["to_generate"]

    avoid_parts = []
    if existing:
        avoid_parts.append(AVOID_DUPLICATES.format(existing="\n".join(f"- {q['question']}" for q in existing)))
    if state.get("deleted_questions"):
        avoid_parts.append(AVOID_DELETED.format(deleted="\n".join(f"- {t}" for t in state["deleted_questions"])))
    avoid = "\n\n".join(avoid_parts)

    llm = get_llm(temperature=0.8).with_structured_output(MCQSet, method="json_schema")
    result: MCQSet = llm.invoke(
        GENERATOR_PROMPT.format(source_text=state["source_text"], count=count, avoid=avoid)
    )

    next_id = state.get("next_id", 1)
    new_items = []
    for mcq in result.questions[:count]:
        new_items.append(_to_item(mcq, next_id))
        next_id += 1

    return {"questions": existing + new_items, "next_id": next_id, "to_generate": 0}


# ---------- ② בודק ----------

def validate(state: QuizState) -> dict:
    """בודק כל שאלה שעוד לא נבדקה: האם ניתנת למענה מהטקסט, והאם יש לה רק תשובה נכונה אחת."""
    llm = get_llm(temperature=0).with_structured_output(Verdict, method="json_schema")
    updated = []
    for q in state["questions"]:
        if q["status"] != "pending":
            updated.append(q)
            continue

        verdict: Verdict = llm.invoke(
            VALIDATOR_PROMPT.format(
                source_text=state["source_text"],
                question=q["question"],
                options=_format_options(q["options"]),
                correct=f"{q['correct_index']}. {q['options'][q['correct_index']]}",
            )
        )
        ok = verdict.answerable_from_text and verdict.single_correct_answer
        if ok:
            updated.append({**q, "status": "valid", "feedback": ""})
        elif q["attempts"] >= MAX_REWRITE_ATTEMPTS:
            # נגמרו הניסיונות - מעבירים למורה עם אזהרה
            updated.append({**q, "status": "flagged", "feedback": verdict.reason})
        else:
            updated.append({**q, "status": "invalid", "feedback": verdict.reason})

    return {"questions": updated}


# ---------- ③ כותב מחדש ----------

def rewrite(state: QuizState) -> dict:
    """כותב מחדש רק את השאלות הפסולות, לפי סיבת הפסילה."""
    llm = get_llm(temperature=0.7).with_structured_output(MCQ, method="json_schema")
    updated = []
    for q in state["questions"]:
        if q["status"] != "invalid":
            updated.append(q)
            continue

        new: MCQ = llm.invoke(
            REWRITE_PROMPT.format(
                source_text=state["source_text"],
                question=q["question"],
                options=_format_options(q["options"]),
                correct=f"{q['correct_index']}. {q['options'][q['correct_index']]}",
                feedback=q["feedback"],
            )
        )
        updated.append({
            **q,
            "question": new.question,
            "options": list(new.options),
            "correct_index": new.correct_index,
            "source_quote": new.source_quote,
            "status": "pending",        # חוזרת לבודק
            "attempts": q["attempts"] + 1,
        })

    return {"questions": updated}


# ---------- ④ אישור מורה (interrupt) ----------

def teacher_review(state: QuizState) -> dict:
    """הגרף נעצר כאן ומחכה להחלטות המורה.

    המורה מחזיר: {"decisions": {"מספר שאלה": {"action": "approve" | "delete" | "edit", ...שדות עריכה}}}
    שאלה שלא קיבלה החלטה נחשבת מאושרת.
    """
    to_review = [q for q in state["questions"] if q["status"] in ("valid", "flagged")]

    answer: dict = interrupt({
        "message": "אשר, מחק או ערוך כל שאלה",
        "to_review": to_review,
        "already_approved": [q for q in state["questions"] if q["status"] == "approved"],
        "replacement_round": state.get("replacement_round", 0),
    })
    decisions = {int(k): v for k, v in (answer or {}).get("decisions", {}).items()}

    kept, deleted_texts = [], []
    for q in state["questions"]:
        if q["status"] == "approved":
            kept.append(q)
            continue
        d = decisions.get(q["id"], {"action": "approve"})
        action = d.get("action", "approve")
        if action == "delete":
            deleted_texts.append(q["question"])
        elif action == "edit":
            kept.append({
                **q,
                "question": d.get("question", q["question"]),
                "options": d.get("options", q["options"]),
                "correct_index": d.get("correct_index", q["correct_index"]),
                "status": "approved",       # סומכים על המורה - לא חוזר לבודק
                "edited_by_teacher": True,
            })
        else:
            kept.append({**q, "status": "approved"})

    return {
        "questions": kept,
        "deleted_count": len(deleted_texts),
        "deleted_questions": state.get("deleted_questions", []) + deleted_texts,
    }


def prepare_replacements(state: QuizState) -> dict:
    """מכין סבב חלופות: כמה לייצר, ומעלה את מונה הסבבים."""
    return {
        "to_generate": state["deleted_count"],
        "replacement_round": state.get("replacement_round", 0) + 1,
    }


# ---------- ⑤ ייצוא ----------

def export(state: QuizState) -> dict:
    """ייצוא - בשלב הזה רק מסמן סיום. ייצוא Word ייבנה בשלב הבא."""
    return {"export_path": None}
