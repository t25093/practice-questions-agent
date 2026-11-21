"""יוצר ב-LangSmith את ה-Dataset: קטע טקסט אחד לכל דוגמה.

הרצה:
    python eval/create_dataset.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import quiz_agent.config  # noqa: E402,F401  (טוען את הגדרות LangSmith)
from langsmith import Client  # noqa: E402

DATASET_NAME = "practice-questions-texts"
TEXTS_DIR = Path(__file__).parent / "texts"

# ה"מלכודת" בכל קטע - נשמרת כ-metadata כדי שיהיה קל לנתח תוצאות
TRAPS = {
    "01_python_lesson1": "הטקסט עצמו מכיל אי-דיוקים (/n, global x=5)",
    "02_solar_system": "חמה הכי קרוב לשמש אבל נוגה הכי חם; טבעות לא רק לשבתאי",
    "03_states_of_matter": "התאדות מול רתיחה",
    "04_jordan_dead_sea": "שני מספרים דומים: 210 ו-430 מטר מתחת לפני הים",
    "05_stack_queue": "LIFO מול FIFO, push/pop מול enqueue/dequeue",
    "06_photosynthesis": "פוטוסינתזה מול נשימה - תהליכים הפוכים",
}


def main():
    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        print(f"ה-Dataset '{DATASET_NAME}' כבר קיים - לא נוצר מחדש.")
        return

    ds = client.create_dataset(DATASET_NAME, description="קטעי חומר לימוד לבדיקת מחולל שאלות התרגול")
    examples = []
    for path in sorted(TEXTS_DIR.glob("*.txt")):
        examples.append({
            "inputs": {"source_text": path.read_text(encoding="utf-8")},
            "metadata": {"name": path.stem, "trap": TRAPS.get(path.stem, "")},
        })
    client.create_examples(dataset_id=ds.id, examples=examples)
    print(f"נוצר Dataset '{DATASET_NAME}' עם {len(examples)} דוגמאות.")


if __name__ == "__main__":
    main()
