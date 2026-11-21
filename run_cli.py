"""הרצת הגרף בטרמינל - לבדיקה, לפני שיש מסך Streamlit.

שימוש:
    python run_cli.py samples/water_cycle.txt
"""
import sys
import uuid

from langgraph.types import Command

sys.path.insert(0, "src")
from quiz_agent.graph import build_graph, initial_state  # noqa: E402

STATUS_ICON = {"valid": "✓", "flagged": "⚠️", "approved": "★"}


def show(questions):
    for q in questions:
        print(f"\n[{q['id']}] {STATUS_ICON.get(q['status'], '?')}  {q['question']}")
        for i, opt in enumerate(q["options"]):
            mark = "←" if i == q["correct_index"] else " "
            print(f"     {i}. {opt} {mark}")
        if q["status"] == "flagged":
            print(f"     ⚠️ הבודק: {q['feedback']}")
        if q["attempts"]:
            print(f"     (נכתבה מחדש {q['attempts']} פעמים)")


def ask_decisions(to_review):
    decisions = {}
    print("\nלכל שאלה: Enter = אשר, d = מחק, e = ערוך")
    for q in to_review:
        a = input(f"שאלה {q['id']}: ").strip().lower()
        if a == "d":
            decisions[q["id"]] = {"action": "delete"}
        elif a == "e":
            new_q = input("  נוסח חדש (Enter = ללא שינוי): ").strip() or q["question"]
            idx = input(f"  מספר התשובה הנכונה (Enter = {q['correct_index']}): ").strip()
            decisions[q["id"]] = {
                "action": "edit",
                "question": new_q,
                "correct_index": int(idx) if idx else q["correct_index"],
            }
    return decisions


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke(initial_state(text), config)
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print("\n" + "=" * 60)
        print(f"⏸  הגרף עצר לאישור מורה (סבב חלופות {payload['replacement_round']})")
        if payload["already_approved"]:
            print("\n--- כבר אושרו ---")
            show(payload["already_approved"])
        print("\n--- לאישור ---")
        show(payload["to_review"])
        decisions = ask_decisions(payload["to_review"])
        result = graph.invoke(Command(resume={"decisions": decisions}), config)

    print("\n" + "=" * 60)
    print(f"✅ הסתיים. {len(result['questions'])} שאלות סופיות:")
    show(result["questions"])


if __name__ == "__main__":
    main()
