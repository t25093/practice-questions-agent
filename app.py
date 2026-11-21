"""מסך המורה (Streamlit).

הרצה:
    streamlit run app.py

המסך הוא רק "חלון" אל הגרף: הוא מתחיל ריצה, מציג את ההתקדמות,
מציג את השאלות כשהגרף עוצר (interrupt), ושולח בחזרה את החלטות המורה.
"""
import sqlite3
import sys
import uuid
from pathlib import Path

import streamlit as st
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).parent / "src"))
from quiz_agent.graph import build_graph, initial_state  # noqa: E402

st.set_page_config(page_title="מחולל שאלות תרגול", page_icon="📝", layout="centered")

# ---------- עיצוב מימין לשמאל ----------
st.markdown(
    """
    <style>
    .stApp, .stMarkdown, .stTextInput, .stTextArea, .stRadio, .stExpander, .stAlert,
    [data-testid="stStatusWidget"], [data-testid="stExpanderDetails"] {
        direction: rtl; text-align: right;
    }
    .stRadio [role="radiogroup"] { justify-content: flex-start; }
    textarea, input { direction: rtl; text-align: right; }
    code { direction: ltr; unicode-bidi: isolate; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- הגרף והזיכרון שלו ----------
@st.cache_resource
def get_graph():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
    return build_graph(SqliteSaver(conn))


graph = get_graph()


def cfg():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


# ---------- הודעות התקדמות לפי צומת ----------
def describe(node: str, update: dict) -> str | None:
    qs = (update or {}).get("questions", [])
    if node == "generate":
        n = sum(1 for q in qs if q["status"] == "pending")
        return f"✅ מחולל: נוצרו {n} שאלות"
    if node == "validate":
        ok = sum(1 for q in qs if q["status"] == "valid")
        bad = sum(1 for q in qs if q["status"] == "invalid")
        flag = sum(1 for q in qs if q["status"] == "flagged")
        msg = f"🔍 בודק: {ok} תקינות"
        if bad:
            msg += f", {bad} פסולות (יישלחו לתיקון)"
        if flag:
            msg += f", {flag} סומנו ⚠️ אחרי 3 ניסיונות"
        return msg
    if node == "rewrite":
        n = sum(1 for q in qs if q["status"] == "pending")
        return f"✏️ כותב מחדש: תוקנו {n} שאלות, חוזרות לבודק"
    if node == "prepare_replacements":
        return f"🔁 מייצר {update['to_generate']} שאלות חלופיות (סבב {update['replacement_round']})"
    if node == "export":
        return "📄 קבצי Word נוצרו"
    if node == "__interrupt__":
        return "⏸ השאלות מוכנות לאישור המורה"
    return None


def run_graph(graph_input):
    """מריץ את הגרף עד העצירה הבאה, ומציג כל שלב בזמן אמת."""
    with st.status("הסוכן עובד...", expanded=True) as status:
        for chunk in graph.stream(graph_input, cfg(), stream_mode="updates"):
            for node, update in chunk.items():
                msg = describe(node, update)
                if msg:
                    st.write(msg)
                    st.session_state.log.append(msg)
        status.update(label="הסתיים", state="complete", expanded=False)
    st.rerun()


def snapshot():
    return graph.get_state(cfg())


# ---------- מצב התחלתי ----------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
    st.session_state.log = []

st.title("📝 מחולל שאלות תרגול")


def start_screen():
    st.write("מדביקים חומר לימוד או מעלים PDF, והסוכן מייצר 5 שאלות אמריקאיות לאישורך.")
    title = st.text_input("כותרת המסמך", value="שאלות תרגול")

    pdf = st.file_uploader("העלאת PDF (לא חובה)", type=["pdf"])
    if pdf is not None and st.session_state.get("pdf_name") != pdf.name:
        from pypdf import PdfReader

        text = "\n".join((p.extract_text() or "") for p in PdfReader(pdf).pages)
        st.session_state.source_text = text.strip()
        st.session_state.pdf_name = pdf.name
        st.info("הטקסט חולץ מה-PDF. בעברית מעורבת בקוד הסדר עלול להשתבש – כדאי לעבור ולתקן לפני שמתחילים.")

    text = st.text_area("חומר הלימוד", key="source_text", height=300)

    if st.button("צור שאלות", type="primary", disabled=not text.strip()):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.log = []
        run_graph(initial_state(text, title=title or "שאלות תרגול"))


def show_question(q, show_correct=True):
    st.markdown(f"**{q['question']}**")
    for i, opt in enumerate(q["options"], start=1):
        mark = " ✅" if show_correct and i - 1 == q["correct_index"] else ""
        st.markdown(f"{i}. {opt}{mark}")
    if q.get("source_quote"):
        st.caption(f"מקור בטקסט: \"{q['source_quote']}\"")


def review_screen(payload):
    rnd = payload["replacement_round"]
    st.subheader("אישור שאלות" + (f" – סבב חלופות {rnd}" if rnd else ""))

    if payload["already_approved"]:
        with st.expander(f"✔️ {len(payload['already_approved'])} שאלות שכבר אושרו"):
            for q in payload["already_approved"]:
                show_question(q)
                st.divider()

    decisions = {}
    for q in payload["to_review"]:
        qid = q["id"]
        with st.container(border=True):
            if q["status"] == "flagged":
                st.warning(f"⚠️ הבודק לא הצליח לאשר את השאלה גם אחרי {q['attempts']} תיקונים: {q['feedback']}")
            elif q["attempts"]:
                st.caption(f"נכתבה מחדש {q['attempts']} פעמים עד שעברה את הבודק")
            show_question(q)

            action = st.radio(
                "החלטה", ["אשר", "מחק", "ערוך"], key=f"act_{rnd}_{qid}", horizontal=True,
            )
            if action == "מחק":
                decisions[str(qid)] = {"action": "delete"}
            elif action == "ערוך":
                new_q = st.text_area("נוסח השאלה", q["question"], key=f"q_{rnd}_{qid}")
                opts = [
                    st.text_input(f"תשובה {i + 1}", o, key=f"o_{rnd}_{qid}_{i}")
                    for i, o in enumerate(q["options"])
                ]
                correct = st.radio(
                    "התשובה הנכונה", [1, 2, 3, 4], index=q["correct_index"],
                    key=f"c_{rnd}_{qid}", horizontal=True,
                )
                decisions[str(qid)] = {
                    "action": "edit", "question": new_q, "options": opts, "correct_index": correct - 1,
                }
            else:
                decisions[str(qid)] = {"action": "approve"}

    n_del = sum(1 for d in decisions.values() if d["action"] == "delete")
    if n_del:
        if rnd < 3:
            st.info(f"על כל שאלה שנמחקת ייווצר תחליף ({n_del}).")
        else:
            st.info("זה סבב החלופות האחרון – שאלות שיימחקו לא יוחלפו.")

    if st.button("שלח החלטות", type="primary"):
        run_graph(Command(resume={"decisions": decisions}))


def done_screen(values):
    st.success(f"הסתיים! {len(values['questions'])} שאלות מאושרות.")
    paths = values.get("export_paths") or {}
    c1, c2 = st.columns(2)
    if paths.get("student"):
        c1.download_button("⬇️ גרסת תלמיד (Word)", Path(paths["student"]).read_bytes(),
                           file_name="questions_student.docx")
    if paths.get("teacher"):
        c2.download_button("⬇️ גרסת מורה (Word)", Path(paths["teacher"]).read_bytes(),
                           file_name="questions_teacher.docx")
    for n, q in enumerate(values["questions"], start=1):
        with st.container(border=True):
            st.caption(f"שאלה {n}" + (" · נערכה על ידי המורה" if q.get("edited_by_teacher") else ""))
            show_question(q)
    if st.button("התחל מחדש"):
        st.session_state.thread_id = None
        st.rerun()


# ---------- ניתוב בין המסכים ----------
if st.session_state.thread_id is None:
    start_screen()
else:
    snap = snapshot()
    if st.session_state.log:
        with st.expander("מה הסוכן עשה עד עכשיו"):
            for line in st.session_state.log:
                st.write(line)
    if snap.interrupts:
        review_screen(snap.interrupts[0].value)
    elif not snap.next:
        done_screen(snap.values)
    else:
        st.warning("הריצה נעצרה באמצע. אפשר להתחיל מחדש.")
        if st.button("התחל מחדש"):
            st.session_state.thread_id = None
            st.rerun()
