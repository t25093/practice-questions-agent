"""הגדרות מרכזיות של הסוכן - כל מספר או שם שאולי נרצה לשנות נמצא כאן."""
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# המודל שבו משתמשים כל הצמתים
MODEL_NAME = os.getenv("QUIZ_MODEL", "gemini-3.5-flash")

# כתובת הכניסה התואמת-OpenAI של Gemini
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# כמה שאלות לייצר בהתחלה
NUM_QUESTIONS = 5

# כמה פעמים מותר לכתוב מחדש שאלה פסולה לפני שמסמנים אותה באזהרה
MAX_REWRITE_ATTEMPTS = 3

# כמה סבבים של "המורה מחק -> מייצרים חלופות" מותרים
MAX_REPLACEMENT_ROUNDS = 3


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """מחזיר חיבור למודל Gemini."""
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=GEMINI_BASE_URL,
        api_key=os.getenv("GEMINI_API_KEY", "proxy-injected"),
        temperature=temperature,
        max_retries=6,
    )
