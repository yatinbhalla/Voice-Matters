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
                    "Sukanya Samriddhi Yojana aapki beti ke liye sabse achi hai - "
                    "8.2% byaaj milta hai. Aap PM-KISAN bhi check kar sakte hain."
                    + HALLUCINATION_SUFFIX_HI
                ),
                retrieved_schemes=[{
                    "scheme_id": "sukanya-samriddhi-yojana",
                    "name_en": "Sukanya Samriddhi Yojana",
                    "name_hi": "सुकन्या समृद्धि योजना",
                    "source_url": "https://www.india.gov.in/spotlight/sukanya-samriddhi-yojana",
                }],
                sources=[{
                    "url": "https://www.india.gov.in/spotlight/sukanya-samriddhi-yojana",
                    "title": "SSY",
                    "scheme_id": "sukanya-samriddhi-yojana",
                }],
                eligibility_results=[],
            )
            session.add(m)
        await session.commit()
        print(f"inserted {count} hallucinated assistant messages under conv {conv.id}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    asyncio.run(main(n))
