"""Convert the 7 new scheme .py files into the canonical JSON shape my
ingest + RAG + eligibility services expect, then drop the old 5 JSONs.

Input  : C:/Users/DeLL/Downloads/{Scheme}.py — each defines a dict with
         keys {id, name_hi, name_en, source_url, helpline_phone,
         eligibility_rules (flat), benefits (struct), application_steps,
         documents_needed, content_hi, content_en, ...}

Output : scheme-corpus/schemes/processed/{kebab_id}.json — canonical
         shape with scheme_id, ministry, summary_hi, eligibility_rules
         {rules: [{field, op, value, reason_hi, ask_hi}], ...}, chunks[].

Per-scheme metadata I author inline below — the rest is derived from the
content of each .py.
"""
from __future__ import annotations

import json
from pathlib import Path

DOWNLOADS = Path("C:/Users/DeLL/Downloads")
OUT_DIR = Path(__file__).resolve().parent.parent / "scheme-corpus" / "schemes" / "processed"

# scheme_id (kebab) -> {file, ministry, summary_hi, eligibility_rules, tags}
# eligibility rules follow the shape that EligibilityService.evaluate()
# expects: each rule has field/op/value/reason_hi/ask_hi.
SCHEMES = {
    "pmjdy": {
        "file": "Pradhan Mantri Jan Dhan Yojana.py",
        "ministry": "Ministry of Finance",
        "summary_hi": (
            "Har vyakti ke liye zero-balance bank khaata - free RuPay card, "
            "Rs 2 lakh ka durghatna beema aur Rs 10,000 ka overdraft."
        ),
        "tags": ["banking", "financial-inclusion", "savings", "rupay", "jan-dhan"],
        "eligibility_rules": {
            "requires_external_verification": False,
            "rules": [
                {
                    "field": "has_aadhaar",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "PMJDY khaata kholne ke liye Aadhaar ya koi sarkari pehchaan zaroori hai",
                    "ask_hi": "Kya aapke paas Aadhaar card ya koi sarkari ID hai?",
                },
            ],
        },
    },
    "pmuy": {
        "file": "Pradhan Mantri Ujjwala Yojana 2.0.py",
        "ministry": "Ministry of Petroleum and Natural Gas",
        "summary_hi": (
            "Garib pariwaron ki mahilaaon ke liye free LPG connection - "
            "pehla refill aur chulha bhi muft, koi deposit nahi lagta."
        ),
        "tags": ["lpg", "women", "household", "clean-fuel", "ujjwala"],
        "eligibility_rules": {
            "requires_external_verification": True,
            "external_verification_hi": (
                "Aapka pariwaar SECC list, AAY, PMAY-G ya kisi pat-r shreni "
                "mein hona chahiye - LPG vitarak ya sarkari portal par jaanch hoti hai."
            ),
            "rules": [
                {
                    "field": "gender",
                    "op": "eq",
                    "value": "female",
                    "reason_hi": "PMUY 2.0 sirf mahilaaon ke naam par connection deti hai",
                    "ask_hi": "Kya aap mahilaa hain? Connection mahilaa ke naam par hi banta hai.",
                },
                {
                    "field": "age",
                    "op": "gte",
                    "value": 18,
                    "reason_hi": "Aavedika ki umar kam se kam 18 saal honi chahiye",
                    "ask_hi": "Kya aap 18 saal ya usse upar ki hain?",
                },
                {
                    "field": "has_aadhaar",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "PMUY 2.0 ke liye Aadhaar zaroori hai",
                    "ask_hi": "Kya aapke paas Aadhaar card hai?",
                },
            ],
        },
    },
    "kcc": {
        "file": "Kisan Credit Card.py",
        "ministry": "Ministry of Agriculture and Farmers' Welfare",
        "summary_hi": (
            "Kisaano ke liye saste credit card - kheti, paludhan aur "
            "machinery ke liye 4% byaaj par loan, batayi-daar bhi paat-r."
        ),
        "tags": ["farmer", "credit", "kisan", "loan", "kcc", "agriculture"],
        "eligibility_rules": {
            "requires_external_verification": True,
            "external_verification_hi": (
                "Bank zameen ke kaagaz (khasra/khatauni) aur fasal pattern verify karega."
            ),
            "rules": [
                {
                    "field": "occupation",
                    "op": "contains_any",
                    "value": ["farmer", "kisan", "kheti", "agriculture", "किसान", "खेती", "batay", "share crop"],
                    "reason_hi": "KCC sirf kisaano, batayi-daaron aur kheti karne waalon ke liye hai",
                    "ask_hi": "Kya aap kheti karte hain - apni zameen par ya batayi par?",
                },
                {
                    "field": "age",
                    "op": "gte",
                    "value": 18,
                    "reason_hi": "Aavedak ki umar kam se kam 18 saal honi chahiye",
                    "ask_hi": "Kya aap 18 saal ya usse upar ke hain?",
                },
                {
                    "field": "has_bank_account",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "KCC ek bank credit card hai, isliye bank khaata zaroori hai",
                    "ask_hi": "Kya aapka kisi bank mein khaata hai?",
                },
            ],
        },
    },
    "day-nrlm": {
        "file": "Deendayal Antyodaya Yojana.py",
        "ministry": "Ministry of Rural Development",
        "summary_hi": (
            "Grameen mahilaaon ke liye SHG-based bachat aur loan - "
            "kam byaaj par credit, kaushal training aur livelihood support."
        ),
        "tags": ["women", "shg", "rural", "livelihood", "loan", "nrlm"],
        "eligibility_rules": {
            "requires_external_verification": True,
            "external_verification_hi": (
                "Aapko kisi gram-stareey SHG ka sadasya hona zaroori hai - "
                "kam se kam 6 mahine purana aur panchasutra ka palan karta ho."
            ),
            "rules": [
                {
                    "field": "occupation",
                    "op": "not_contains_any",
                    "value": ["government employee", "sarkari naukri", "income tax payer"],
                    "reason_hi": "DAY-NRLM grameen garib pariwaaron ke liye hai - sarkari karmchari paat-r nahi",
                    "ask_hi": "Aap kya kaam karte hain?",
                },
            ],
        },
    },
    "pmjjby": {
        "file": "Pradhan Mantri Jeevan Jyoti Bima Yojana.py",
        "ministry": "Ministry of Finance",
        "summary_hi": (
            "Sirf Rs 436 saal mein Rs 2 lakh ka jeevan beema - "
            "bank khaata aur Aadhaar zaroori, har saal renew hota hai."
        ),
        "tags": ["insurance", "life-cover", "low-premium", "jansuraksha"],
        "eligibility_rules": {
            "requires_external_verification": False,
            "rules": [
                {
                    "field": "age",
                    "op": "gte",
                    "value": 18,
                    "reason_hi": "PMJJBY ke liye kam se kam umar 18 saal hai",
                    "ask_hi": "Kya aap 18 saal ya usse upar ke hain?",
                },
                {
                    "field": "age",
                    "op": "lte",
                    "value": 50,
                    "reason_hi": "PMJJBY ki maximum entry umar 50 saal hai",
                    "ask_hi": "Aapki umar kya hai? 50 saal tak hi naya enrolment hota hai.",
                },
                {
                    "field": "has_bank_account",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "Premium auto-debit hota hai isliye bank ya post office khaata zaroori hai",
                    "ask_hi": "Kya aapka bank ya post office mein khaata hai?",
                },
                {
                    "field": "has_aadhaar",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "PMJJBY enrolment ke liye Aadhaar KYC zaroori hai",
                    "ask_hi": "Kya aapke paas Aadhaar card hai?",
                },
            ],
        },
    },
    "pmmy": {
        "file": "Pradhan Mantri Mudra Yojana.py",
        "ministry": "Ministry of Finance (Department of Financial Services)",
        "summary_hi": (
            "Chhote vyaapariyon ke liye Rs 50,000 se Rs 20 lakh tak ka "
            "collateral-free business loan - Shishu, Kishore, Tarun, Tarun Plus shreniyaan."
        ),
        "tags": ["business", "loan", "msme", "mudra", "self-employment", "shishu", "kishore", "tarun"],
        "eligibility_rules": {
            "requires_external_verification": True,
            "external_verification_hi": (
                "Bank aapka credit record aur business plan dekh ke loan deta hai - "
                "default record nahi hona chahiye."
            ),
            "rules": [
                {
                    "field": "age",
                    "op": "gte",
                    "value": 18,
                    "reason_hi": "Loan lene ke liye kam se kam umar 18 saal hai",
                    "ask_hi": "Kya aap 18 saal ya usse upar ke hain?",
                },
                {
                    "field": "has_bank_account",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "Mudra loan bank khaate mein aata hai isliye bank account zaroori hai",
                    "ask_hi": "Kya aapka kisi bank mein khaata hai?",
                },
                {
                    "field": "occupation",
                    "op": "not_contains_any",
                    "value": ["agriculture only", "kheti only"],
                    "reason_hi": "Mudra non-farm sector ke liye hai - sirf kheti ke liye nahi",
                    "ask_hi": "Aap kis tarah ka kaam karte hain? Dukan, sevayein, ya manufacture?",
                },
            ],
        },
    },
    "mmsby": {
        "file": "Mukhmantri Sehat Bima Yojana.py",
        "ministry": "Government of Punjab (State Health Agency)",
        "summary_hi": (
            "Punjab ke pariwaaron ke liye Rs 5 lakh ka cashless ilaaj - "
            "sarkari aur empanelled niji aspataalon mein, koi paisa nahi dena."
        ),
        "tags": ["health", "insurance", "punjab", "cashless", "ayushman", "state-scheme"],
        "eligibility_rules": {
            "requires_external_verification": True,
            "external_verification_hi": (
                "Aapka pariwaar SECC 2011 ya Smart Ration Card list ya J-form farmer ya "
                "kisi paat-r shreni mein hona chahiye - State Health Agency portal par jaanch hoti hai."
            ),
            "rules": [
                {
                    "field": "state",
                    "op": "eq",
                    "value": "punjab",
                    "reason_hi": "MMSBY sirf Punjab raajya ke nivaasiyon ke liye hai",
                    "ask_hi": "Kya aap Punjab mein rehte hain?",
                },
                {
                    "field": "has_aadhaar",
                    "op": "eq",
                    "value": True,
                    "reason_hi": "E-card ke liye Aadhaar zaroori hai",
                    "ask_hi": "Kya aapke paas Aadhaar card hai?",
                },
            ],
        },
    },
}


def _load_py(path: Path) -> dict:
    ns: dict = {}
    exec(path.read_text(encoding="utf-8"), ns)
    # 6 of 7 files use `scheme_data`; KCC uses `kisan_credit_card`.
    for key in ("scheme_data", "kisan_credit_card"):
        if key in ns and isinstance(ns[key], dict):
            return ns[key]
    raise RuntimeError(f"no scheme dict found in {path.name}")


def _first_paragraphs(text: str, n: int = 2) -> str:
    """Take the first N non-empty paragraphs of the long-form content."""
    paras = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    return "\n\n".join(paras[:n])


def _benefits_text(benefits: dict, name_en: str) -> str:
    """Render the benefits struct into a human Hindi-Roman + English line."""
    lines = []
    for k, v in benefits.items():
        if isinstance(v, bool):
            if v:
                lines.append(k.replace("_", " "))
        else:
            lines.append(f"{k.replace('_',' ')}: {v}")
    return f"{name_en} ke benefits / faayde: " + "; ".join(lines)


def _docs_text(docs: list, name_en: str) -> str:
    names = []
    for d in docs:
        if isinstance(d, dict):
            names.append(d.get("name_en") or d.get("name_hi") or "")
        else:
            names.append(str(d))
    names = [n for n in names if n]
    return f"Documents needed for {name_en} application / Zaroori kaagaz: " + ", ".join(names)


def _steps_text(steps: list, name_en: str) -> str:
    pieces = []
    for s in steps:
        n = s.get("step_number", "?")
        en = s.get("title_en", "")
        hi = s.get("title_hi", "")
        det = s.get("detail_en") or s.get("detail_hi") or ""
        pieces.append(f"Step {n}: {en} / {hi}. {det}".strip())
    return f"How to apply for {name_en} / Kaise apply karein: " + " | ".join(pieces)


def _chunks_for(scheme_id: str, src: dict, summary_hi: str) -> list[dict]:
    name_en = src.get("name_en", "")
    name_hi = src.get("name_hi", "")
    content_hi = (src.get("content_hi") or "").strip()
    content_en = (src.get("content_en") or "").strip()
    helpline = src.get("helpline_phone", "")
    portal = src.get("official_portal_url") or src.get("source_url") or ""

    return [
        {
            "id": f"{scheme_id}-summary",
            "chunk_type": "summary",
            "language": "hi-en",
            "text": (
                f"{name_en} ({name_hi}) - {summary_hi} "
                f"{_first_paragraphs(content_en, 1)} {_first_paragraphs(content_hi, 1)}"
            ).strip(),
        },
        {
            "id": f"{scheme_id}-overview",
            "chunk_type": "overview",
            "language": "hi-en",
            "text": (
                f"{name_en} detailed overview / vistar se jaankari: "
                f"{_first_paragraphs(content_en, 2)} "
                f"{_first_paragraphs(content_hi, 2)}"
            ).strip(),
        },
        {
            "id": f"{scheme_id}-benefits",
            "chunk_type": "benefits",
            "language": "hi-en",
            "text": _benefits_text(src.get("benefits") or {}, name_en),
        },
        {
            "id": f"{scheme_id}-documents",
            "chunk_type": "documents_required",
            "language": "hi-en",
            "text": _docs_text(src.get("documents_needed") or [], name_en),
        },
        {
            "id": f"{scheme_id}-apply",
            "chunk_type": "application_process",
            "language": "hi-en",
            "text": _steps_text(src.get("application_steps") or [], name_en),
        },
        {
            "id": f"{scheme_id}-helpline",
            "chunk_type": "helpline",
            "language": "hi-en",
            "text": (
                f"{name_en} helpline / madad ke liye number: {helpline}. "
                f"Official portal: {portal}. Madad ke liye is number par call karein "
                f"ya portal par jaayein."
            ),
        },
    ]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Convert + write new JSONs.
    written: list[str] = []
    for scheme_id, meta in SCHEMES.items():
        src_path = DOWNLOADS / meta["file"]
        if not src_path.exists():
            print(f"SKIP {scheme_id}: {src_path} not found")
            continue
        src = _load_py(src_path)
        doc = {
            "scheme_id": scheme_id,
            "name_hi": src.get("name_hi", ""),
            "name_en": src.get("name_en", ""),
            "ministry": meta["ministry"],
            "summary_hi": meta["summary_hi"],
            "source_url": src.get("source_url", ""),
            "helpline_phone": src.get("helpline_phone", ""),
            "tags": meta["tags"],
            "eligibility_rules": meta["eligibility_rules"],
            "chunks": _chunks_for(scheme_id, src, meta["summary_hi"]),
        }
        out_path = OUT_DIR / f"{scheme_id}.json"
        out_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"OK   {scheme_id}.json  ({len(doc['chunks'])} chunks)")
        written.append(scheme_id)

    # 2. Drop the old 5 JSON files (anything not in the new set).
    keep = set(SCHEMES.keys()) | {".gitkeep"}
    removed = []
    for f in OUT_DIR.iterdir():
        if f.is_file() and f.stem not in keep and f.name not in keep:
            f.unlink()
            removed.append(f.name)
    if removed:
        print()
        print(f"removed old: {', '.join(sorted(removed))}")

    print()
    print(f"wrote {len(written)} new schemes in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
