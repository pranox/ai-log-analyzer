import os
from dotenv import load_dotenv
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()  # ✅ MUST be at top
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set")

client = Groq(api_key=GROQ_API_KEY)

def run_llm(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL"),
            messages=[
                {"role": "system", "content": "You are a CI/CD log analysis expert."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[LLM ERROR] {str(e)}"
