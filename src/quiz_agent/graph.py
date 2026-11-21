"""בניית הגרף: הצמתים, הלולאות, הענפים המותנים ונקודת העצירה."""
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .config import MAX_REPLACEMENT_ROUNDS
from .models import QuizState
from .nodes import export, generate, prepare_replacements, rewrite, teacher_review, validate


def route_after_validate(state: QuizState) -> str:
    """ענף מותנה ①: יש שאלה פסולה שאפשר עוד לתקן? -> לכותב. אחרת -> למורה."""
    if any(q["status"] == "invalid" for q in state["questions"]):
        return "rewrite"
    return "teacher_review"


def route_after_review(state: QuizState) -> str:
    """ענף מותנה ②: המורה מחק שאלות ועוד לא נגמרו סבבי החלופות? -> מייצרים חלופות. אחרת -> ייצוא."""
    if state.get("deleted_count", 0) > 0 and state.get("replacement_round", 0) < MAX_REPLACEMENT_ROUNDS:
        return "prepare_replacements"
    return "export"


def build_graph(checkpointer=None):
    g = StateGraph(QuizState)

    g.add_node("generate", generate)
    g.add_node("validate", validate)
    g.add_node("rewrite", rewrite)
    g.add_node("teacher_review", teacher_review)
    g.add_node("prepare_replacements", prepare_replacements)
    g.add_node("export", export)

    g.add_edge(START, "generate")
    g.add_edge("generate", "validate")
    g.add_conditional_edges("validate", route_after_validate, ["rewrite", "teacher_review"])
    g.add_edge("rewrite", "validate")                      # לולאה פנימית
    g.add_conditional_edges("teacher_review", route_after_review, ["prepare_replacements", "export"])
    g.add_edge("prepare_replacements", "generate")         # לולאה חיצונית
    g.add_edge("export", END)

    # checkpointer = הזיכרון שמאפשר לגרף "להירדם" ב-interrupt ולהמשיך מאותה נקודה
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def initial_state(source_text: str) -> QuizState:
    from .config import NUM_QUESTIONS
    return QuizState(
        source_text=source_text,
        questions=[],
        to_generate=NUM_QUESTIONS,
        next_id=1,
        replacement_round=0,
        deleted_count=0,
        deleted_questions=[],
        export_path=None,
    )
