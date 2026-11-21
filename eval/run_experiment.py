"""מריץ ניסוי ב-LangSmith: הסוכן רץ על כל קטע ב-Dataset, והשופט נותן ציון.

בניסוי אין מורה, ולכן הגרף רץ עד העצירה למורה (interrupt),
והציון ניתן לשאלות שהסוכן היה מציג לו.

הרצה:
    python eval/run_experiment.py v1-baseline
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from langsmith import evaluate  # noqa: E402

from create_dataset import DATASET_NAME  # noqa: E402
from evaluators import judge  # noqa: E402
from quiz_agent.config import JUDGE_MODEL, MODEL_NAME  # noqa: E402
from quiz_agent.graph import build_graph, initial_state  # noqa: E402

graph = build_graph()


def target(inputs: dict) -> dict:
    """מריץ את הגרף על קטע אחד עד שהוא עוצר למורה."""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke(initial_state(inputs["source_text"]), config)
    payload = result["__interrupt__"][0].value
    questions = payload["to_review"]
    return {
        "questions": questions,
        "rewrites": sum(q["attempts"] for q in questions),
        "flagged": sum(q["status"] == "flagged" for q in questions),
    }


def rewrites(outputs: dict) -> dict:
    """כמה פעמים הלולאה הפנימית כתבה שאלה מחדש (מידע, לא ציון איכות)."""
    return {"key": "rewrites", "score": outputs.get("rewrites", 0)}


def flagged(outputs: dict) -> dict:
    """כמה שאלות הגיעו למורה עם אזהרה."""
    return {"key": "flagged", "score": outputs.get("flagged", 0)}


if __name__ == "__main__":
    prefix = sys.argv[1] if len(sys.argv) > 1 else "experiment"
    evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[judge, rewrites, flagged],
        experiment_prefix=prefix,
        metadata={"model": MODEL_NAME, "judge_model": JUDGE_MODEL},
        max_concurrency=1,   # אחד-אחד, כדי לא לחרוג ממגבלת הקצב של Gemini
    )
