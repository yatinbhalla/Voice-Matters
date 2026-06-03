"""One-off: insert assistant messages flagged with HALLUCINATION_SUFFIX_HI
so the trust-metrics dashboard's hallucination_rate ticks up. Demo only.

Usage:
  cd backend
  .venv/Scripts/python.exe _inject_hallucination.py [count=5]
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")  # must run before models.db import

from models import Conversation, Message, Modality, Role  # noqa: E402
from models.db import SessionLocal  # noqa: E402
from services.answer_service import HALLUCINATION_SUFFIX_HI  # noqa: E402


async def main(count: int) -> None:
    if SessionLocal is None:
        print("DATABASE_URL not configured")
        return
    async with SessionLocal() as session:
        conv = Conversation()
        session.add(conv)
        await session.flush()
        for _ in range(count):
            m = Message(
                conversation_id=conv.id,
                role=Role.assistant,
                modality=Modality.text,
                content_text=(
                    "PMJDY ke saath aap turant 20,000 rupaye ka loan le sakte "
                    "hain bina kisi documentation ke. Bas mobile number dena hai."
                    + HALLUCINATION_SUFFIX_HI
                ),
                retrieved_schemes=[{
                    "scheme_id": "pmjdy",
                    "name_en": "Pradhan Mantri Jan Dhan Yojana",
                    "name_hi": "प्रधानमंत्री जन धन योजना",
                    "source_url": "https://www.pmjdy.gov.in/",
                }],
                sources=[{
                    "url": "https://www.pmjdy.gov.in/",
                    "title": "PMJDY",
                    "scheme_id": "pmjdy",
                }],
                eligibility_results=[],
            )
            session.add(m)
        await session.commit()
        print(f"inserted {count} hallucinated assistant messages under conv {conv.id}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    asyncio.run(main(n))
