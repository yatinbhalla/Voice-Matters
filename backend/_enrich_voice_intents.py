"""Add a 'user_voice_intents' chunk to each scheme JSON. These chunks
contain colloquial first-person query patterns users actually say —
"main kisan hu", "mujhe loan chahiye", etc. — so OpenAI embeddings
land much closer to the right scheme on natural voice queries.

Run after _convert_new_schemes.py. Re-ingest after this."""
import json
from pathlib import Path

OUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "scheme-corpus" / "schemes" / "processed"
)

# Devanagari intent variants. Sarvam Saaras (voice STT) transcribes
# Hindi as Devanagari, not Roman — without these, every voice query
# scores <0.30 against the Roman-only intents and gets refused.
DEVANAGARI_INTENTS = {
    "pmjdy": [
        "मुझे बैंक खाता खुलवाना है",
        "मेरा बैंक खाता नहीं है",
        "मुफ्त में बैंक खाता कैसे खुलता है",
        "जन धन योजना में नाम लिखवाना है",
        "जीरो बैलेंस खाता चाहिए",
        "रुपे कार्ड चाहिए",
        "मैं गरीब हूँ बैंक खाता खोलो",
        "मुझे मुफ्त सेविंग्स अकाउंट चाहिए",
        "मेरे पास बैंक खाता नहीं है क्या करूँ",
        "ओवरड्राफ्ट चाहिए बिना पैसे के",
    ],
    "pmuy": [
        "मुझे गैस कनेक्शन चाहिए",
        "मुफ्त एलपीजी चाहिए",
        "उज्ज्वला योजना में नाम लिखवाना है",
        "मैं महिला हूँ गैस कैसे मिलेगी",
        "घर में चूल्हा और गैस नहीं है",
        "लकड़ी का चूल्हा है गैस चाहिए",
        "गरीब महिला के लिए गैस",
        "मुफ्त सिलेंडर कैसे मिलता है",
        "रसोई के लिए साफ ईंधन चाहिए",
        "बीपीएल परिवार के लिए गैस योजना",
    ],
    "kcc": [
        "मैं किसान हूँ",
        "मैं किसान हूं",
        "मैं किसान हूँ लोन चाहिए",
        "मैं खेती करता हूँ",
        "किसान को लोन कैसे मिलता है",
        "किसान क्रेडिट कार्ड कैसे बनता है",
        "फसल के लिए पैसा चाहिए",
        "खेत के लिए लोन चाहिए",
        "खेती के लिए सस्ता लोन",
        "मुझे ट्रैक्टर के लिए लोन चाहिए",
        "मैं बटाई पर खेती करता हूँ लोन मिलेगा क्या",
        "किसान को सरकारी मदद",
        "किसानों के लिए सरकारी योजना",
    ],
    "day-nrlm": [
        "मैं महिला हूँ SHG कैसे बनाएं",
        "स्वयं सहायता समूह से जुड़ना है",
        "ग्रामीण महिलाओं के लिए योजना",
        "SHG से लोन कैसे मिलता है",
        "आजीविका मिशन क्या है",
        "बचत समूह के लिए सरकारी मदद",
        "कौशल प्रशिक्षण महिलाओं के लिए",
        "ग्रामीण गरीब के लिए योजना",
    ],
    "pmjjby": [
        "सस्ता जीवन बीमा चाहिए",
        "कम प्रीमियम पर इंश्योरेंस",
        "जीवन ज्योति योजना",
        "436 रुपये वाला बीमा",
        "2 लाख का जीवन बीमा",
        "मुझे लाइफ इंश्योरेंस चाहिए सस्ता",
        "एक साल का बीमा",
        "अगर मैं मर गया तो परिवार को पैसा मिलेगा",
    ],
    "pmmy": [
        "मुझे व्यापार शुरू करने के लिए लोन चाहिए",
        "मुद्रा लोन कैसे मिलता है",
        "छोटी दुकान के लिए लोन",
        "बिना गहना रखे लोन",
        "मैं स्वरोजगार करता हूँ लोन चाहिए",
        "एमएसएमई लोन कैसे लेते हैं",
        "शिशु लोन क्या है",
        "किशोर तरुण लोन",
        "मैं रेहड़ी लगाता हूँ लोन चाहिए",
        "नए बिज़नेस के लिए पैसा चाहिए",
    ],
    "mmsby": [
        "पंजाब में मुफ्त इलाज",
        "सेहत बीमा योजना पंजाब",
        "मुख्यमंत्री सेहत बीमा",
        "पंजाब की हेल्थ योजना",
        "मैं पंजाब से हूँ इलाज की योजना",
        "पंजाब में कैशलेस इलाज",
        "5 लाख का मुफ्त इलाज पंजाब",
        "स्मार्ट राशन कार्ड पर इलाज",
    ],
}

# scheme_id -> list of first-person query templates a real user would say
INTENTS = {
    "pmjdy": [
        "main bank khaata kholna chahta hu",
        "muft bank khaata",
        "muft bank khaata kaise khulwayein",
        "mera bank khaata nahi hai",
        "muft bank account kaise khulta hai",
        "Jan Dhan yojana mein naam likhwana hai",
        "zero balance khaata chahiye",
        "RuPay card chahiye",
        "main garib hu, bank khaata kholo",
        "mujhe muft mein savings account chahiye",
        "Jan Dhan account kya hai",
        "mere paas paisa kam hai, bank khaata kaise kholun",
        "bank mein mera account nahi hai, kya karu",
        "overdraft chahiye bina paisa diye",
    ],
    "pmuy": [
        "mujhe gas connection chahiye",
        "main mahila hu gas chahiye",
        "mai mahila hu",
        "main aurat hu",
        "free LPG chahiye",
        "Ujjwala yojana mein naam likhwana hai",
        "mai mahila hu, gas kaise milegi",
        "ghar mein chulha aur gas nahi hai",
        "lakdi ka chulha hai, gas chahiye",
        "gareeb mahila ke liye gas",
        "free cylinder kaise milta hai",
        "Ujjwala 2.0 kya hai",
        "BPL parivaar ke liye gas yojana",
        "humare ghar mein dhuaan bahut hota hai, gas chahiye",
        "rasoi ke liye saaf eindhan chahiye",
    ],
    "kcc": [
        "main kisan hu",
        "mai kisan hu",
        "main kissan hu",
        "mai kissan hu",
        "main kishan hu",
        "main kisaan hu",
        "main kisan hu loan chahiye",
        "mai kheti karta hu",
        "kisaan ko loan kaise milta hai",
        "Kisan Credit Card kaise banta hai",
        "fasal ke liye paisa chahiye",
        "khet ke liye loan chahiye",
        "kheti ke liye sasta loan",
        "main batayi par kheti karta hu, loan milega kya",
        "share cropper ko KCC milta hai",
        "kheti karta hu, mujhe credit card chahiye",
        "kisan ke liye sarkari madad",
        "mujhe trsctor ke liye loan chahiye kheti ke liye",
        "paludhan ya dairy ke liye loan",
    ],
    "day-nrlm": [
        "main mahila hu, SHG kaise banaye",
        "self help group join karna hai",
        "grameen mahilaaon ke liye yojana",
        "SHG se loan kaise milta hai",
        "Aajeevika mission kya hai",
        "mai gaon se hu, SHG mein judna chahti hu",
        "bachat group ke liye sarkari madad",
        "kaushal training mahilaaon ke liye",
        "grameen garib ke liye yojana",
        "SHG bank linkage loan",
    ],
    "pmjjby": [
        "sasta jeevan beema chahiye",
        "kam premium par insurance",
        "PMJJBY kya hai",
        "Jeevan Jyoti yojana",
        "₹436 wala beema",
        "2 lakh ka jeevan beema",
        "mujhe life insurance chahiye sasta",
        "ek saal ka beema",
        "auto debit wala beema",
        "agar mai mar gaya to parivar ko paisa milega",
        "term insurance gareebon ke liye",
    ],
    "pmmy": [
        "main vyaapar shuru karna chahta hu, loan chahiye",
        "Mudra loan kaise milta hai",
        "chhoti dukaan ke liye loan",
        "collateral free business loan",
        "main self employed hu, loan chahiye",
        "MSME loan kaise lete hain",
        "Shishu loan kya hai",
        "Kishore loan",
        "Tarun loan ke liye apply kaise karein",
        "₹50000 ka business loan",
        "₹10 lakh ka loan vyaapar ke liye",
        "main rehri lagata hu, loan chahiye",
        "naye business ke liye paisa chahiye",
        "Mudra Yojana kya hai",
    ],
    "mmsby": [
        "Punjab mein muft ilaaj",
        "Sehat Bima Yojana Punjab",
        "Mukhmantri sehat bima",
        "Punjab ki health scheme",
        "AB PM-JAY Punjab",
        "main Punjab se hu, ilaaj ke liye yojana",
        "Punjab mein cashless ilaaj",
        "Punjab ke kisaano ke liye health card",
        "5 lakh ka muft ilaaj Punjab",
        "Smart Ration Card par ilaaj",
        "J-form farmer Punjab health scheme",
    ],
}


def main() -> int:
    if not OUT_DIR.exists():
        print(f"FAIL: {OUT_DIR} not found")
        return 1
    enriched = 0
    for sid, intents in INTENTS.items():
        path = OUT_DIR / f"{sid}.json"
        if not path.exists():
            print(f"SKIP {sid}: file missing")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        # Drop any prior intents chunks so re-running is idempotent.
        doc["chunks"] = [
            c for c in doc.get("chunks", [])
            if not c.get("id", "").endswith("-intents")
            and not c.get("id", "").endswith("-intents-hi")
        ]
        # Roman intents chunk (for typed Hinglish queries).
        doc["chunks"].append({
            "id": f"{sid}-intents",
            "chunk_type": "user_voice_intents",
            "language": "hi-roman",
            "text": (
                f"Common user voice intents for {doc.get('name_en','')}: "
                + " | ".join(intents)
            ),
        })
        # Devanagari intents chunk (Sarvam Saaras returns Devanagari from
        # voice queries, which scores 0.20-0.30 against Roman chunks —
        # this puts the same intents in the matching script.)
        dev = DEVANAGARI_INTENTS.get(sid, [])
        dev_count = 0
        if dev:
            doc["chunks"].append({
                "id": f"{sid}-intents-hi",
                "chunk_type": "user_voice_intents_devanagari",
                "language": "hi-devanagari",
                "text": (
                    f"{doc.get('name_hi','')} ke liye common voice queries: "
                    + " | ".join(dev)
                ),
            })
            dev_count = len(dev)
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        enriched += 1
        print(f"OK   {sid}.json  ({len(intents)} roman + {dev_count} dev)")
    print()
    print(f"enriched {enriched} schemes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
