"""Replace each scheme's summary_hi with a Devanagari version so the
/schemes/{id}/explain endpoint (the source for the scheme card's "सुन लो"
button) feeds Sarvam Bulbul natural Hindi — not Hindi-Roman that Bulbul
reads with an English accent.

Also clears the explain_cache table so old Hindi-Roman cached audio
URLs don't keep getting served.
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

OUT_DIR = BACKEND.parent / "scheme-corpus" / "schemes" / "processed"

# scheme_id -> Devanagari summary (1-3 sentences, warm tone, no Roman words
# except scheme acronyms in parens and unavoidable English nouns)
SUMMARIES_DEVANAGARI = {
    "pmjdy": (
        "प्रधानमंत्री जन धन योजना उन सब लोगों के लिए है जिनका अभी तक बैंक "
        "खाता नहीं खुला। ज़ीरो बैलेंस पर खाता खुलता है - कोई न्यूनतम राशि "
        "नहीं रखनी। साथ में मुफ्त रुपे डेबिट कार्ड और दो लाख का दुर्घटना "
        "बीमा भी मिलता है, और ज़रूरत पड़ने पर दस हज़ार का ओवरड्राफ्ट।"
    ),
    "pmuy": (
        "प्रधानमंत्री उज्ज्वला योजना 2.0 ग़रीब परिवारों की महिलाओं को "
        "बिल्कुल मुफ्त एलपीजी कनेक्शन देती है। साथ में चूल्हा और पहला "
        "सिलेंडर रिफिल भी मुफ्त मिलता है - कोई security deposit नहीं देना। "
        "सब इंतज़ाम सरकार और गैस कंपनी मिल कर करती है।"
    ),
    "kcc": (
        "किसान क्रेडिट कार्ड किसानों को सस्ती दर पर लोन देता है - खेती, "
        "फसल कटाई के बाद का ख़र्च, पशुपालन और मशीनरी सब के लिए। समय पर "
        "चुकाने पर ब्याज सिर्फ़ चार प्रतिशत के क़रीब आता है, और एक बार बना "
        "कार्ड पाँच साल तक चलता है। बटाई-दार और शेयर क्रॉपर भी ले सकते हैं।"
    ),
    "day-nrlm": (
        "दीनदयाल अंत्योदय योजना ग्रामीण ग़रीब परिवारों, ख़ास कर महिलाओं को "
        "स्वयं सहायता समूह से जोड़ती है। समूह के ज़रिए बचत, आपसी लोन, "
        "बैंक से कम ब्याज पर तीन लाख तक का क्रेडिट, और कौशल प्रशिक्षण - "
        "सब एक जगह मिल जाता है।"
    ),
    "pmjjby": (
        "प्रधानमंत्री जीवन ज्योति बीमा योजना सिर्फ़ चार सौ छत्तीस रुपये "
        "साल में दो लाख का जीवन बीमा देती है। कोई भी कारण हो - प्राकृतिक "
        "मौत हो या दुर्घटना - नॉमिनी को पूरा पैसा मिलता है। प्रीमियम "
        "बैंक या डाकघर के खाते से अपने आप कट जाता है।"
    ),
    "pmmy": (
        "प्रधानमंत्री मुद्रा योजना छोटे व्यापारियों को बिना कोई गहना रखे "
        "लोन देती है। चार श्रेणियाँ हैं - शिशु पचास हज़ार तक, किशोर पाँच "
        "लाख तक, तरुण दस लाख तक, और तरुण प्लस बीस लाख तक। दुकान खोलनी हो "
        "या चलाते हुए व्यापार बढ़ाना हो, दोनों के लिए मिलता है।"
    ),
    "mmsby": (
        "मुख्यमंत्री सेहत बीमा योजना पंजाब राज्य की स्वास्थ्य योजना है। "
        "पात्र परिवारों को हर साल पाँच लाख तक का cashless इलाज मिलता है - "
        "सरकारी और कई empanelled निजी अस्पतालों में, अस्पताल में कोई "
        "पैसा नहीं देना पड़ता।"
    ),
}


async def _truncate_cache_table() -> None:
    """Drop any old explain-cache rows so a fresh Devanagari summary is
    served, not stale Hindi-Roman text + audio URL."""
    try:
        from sqlalchemy import text as sql_text

        from models.db import SessionLocal
    except Exception as e:
        print(f"  (skipping cache truncate: {e})")
        return
    if SessionLocal is None:
        print("  (skipping cache truncate: SessionLocal is None)")
        return
    async with SessionLocal() as session:
        await session.execute(sql_text("DELETE FROM explain_cache"))
        await session.commit()
    print("  explain_cache table truncated")


async def main() -> int:
    if not OUT_DIR.exists():
        print(f"FAIL: {OUT_DIR} not found")
        return 1
    updated = 0
    for sid, dev_summary in SUMMARIES_DEVANAGARI.items():
        path = OUT_DIR / f"{sid}.json"
        if not path.exists():
            print(f"SKIP {sid}")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["summary_hi"] = dev_summary
        # Also overwrite the summary chunk with Devanagari content so a
        # voice query that semantically hits "summary" lands in Devanagari
        # context (RAG retrieval already covers user-intents).
        for c in doc.get("chunks", []):
            if c.get("id", "").endswith("-summary"):
                # Keep the bilingual context for embedding diversity, but
                # lead with the Devanagari summary so it's the natural
                # paraphrase target.
                c["text"] = f"{dev_summary} {c.get('text','')}"
                break
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        updated += 1
        print(f"OK   {sid}.json")
    print()
    print(f"updated {updated} schemes with Devanagari summary_hi")
    await _truncate_cache_table()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
