"""מעריך קוד (בלי מודל): האם התשובה הנכונה "מסגירה את עצמה"?

תלמיד שלא למד יכול לנחש תשובה נכונה אם:
  1. היא בולטת באורכה - ארוכה בהרבה מהמסיחים (התשובות השגויות)
  2. היא ציטוט מילה במילה מהטקסט, כשהמסיחים לא

הציון no_giveaway = אחוז השאלות שאין בהן אף אחת מהבעיות (גבוה = טוב).
"""
import re

LONGEST_RATIO = 1.3   # התשובה הנכונה ארוכה פי 1.3 לפחות מממוצע המסיחים
MIN_QUOTE_WORDS = 4   # ציטוט נחשב רק מ-4 מילים ומעלה


def _norm(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s)          # בלי פיסוק
    return re.sub(r"\s+", " ", s).strip().lower()


def _is_quote(option: str, text: str) -> bool:
    o = _norm(option)
    return len(o.split()) >= MIN_QUOTE_WORDS and o in _norm(text)


def check_question(q: dict, source_text: str) -> list[str]:
    correct = q["options"][q["correct_index"]]
    others = [o for i, o in enumerate(q["options"]) if i != q["correct_index"]]
    problems = []

    avg_other = sum(len(o) for o in others) / len(others)
    if len(correct) >= max(len(o) for o in others) and len(correct) > LONGEST_RATIO * avg_other:
        problems.append("הנכונה ארוכה בבירור מהמסיחים")

    if _is_quote(correct, source_text) and not any(_is_quote(o, source_text) for o in others):
        problems.append("הנכונה מועתקת מילה במילה מהטקסט")
    return problems


def no_giveaway(inputs: dict, outputs: dict) -> dict:
    questions = outputs.get("questions", [])
    if not questions:
        return {"key": "no_giveaway", "score": 0}
    comments, clean = [], 0
    for i, q in enumerate(questions, start=1):
        problems = check_question(q, inputs["source_text"])
        if problems:
            comments.append(f"שאלה {i}: " + ", ".join(problems))
        else:
            clean += 1
    return {"key": "no_giveaway", "score": clean / len(questions), "comment": "\n".join(comments)}
