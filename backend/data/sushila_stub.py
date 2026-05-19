"""Hardcoded top-3 schemes for the Sushila persona.

Used by the voice pipeline until real RAG lands in Prompt 6.
"""

TOP_3_SCHEMES = [
    {
        "scheme_id": "sukanya-samriddhi-yojana",
        "name_hi": "सुकन्या समृद्धि योजना",
        "name_en": "Sukanya Samriddhi Yojana",
        "one_line_pitch_hi": "बेटी के नाम पर हर साल थोड़ा-थोड़ा जमा करें, 21 साल में बड़ी रकम मिलेगी।",
        "benefit_amount_inr": 7000000,
        "effort": "low",
        "source_url": "https://www.india.gov.in/spotlight/sukanya-samriddhi-yojana",
        "match_confidence": 0.92,
    },
    {
        "scheme_id": "pmjdy",
        "name_hi": "प्रधानमंत्री जन धन योजना",
        "name_en": "Pradhan Mantri Jan Dhan Yojana",
        "one_line_pitch_hi": "ज़ीरो बैलेंस बैंक खाता, बीमा और RuPay कार्ड - सब मुफ़्त।",
        "benefit_amount_inr": 200000,
        "effort": "low",
        "source_url": "https://pmjdy.gov.in/scheme",
        "match_confidence": 0.81,
    },
    {
        "scheme_id": "e-shram",
        "name_hi": "ई-श्रम कार्ड",
        "name_en": "e-Shram",
        "one_line_pitch_hi": "असंगठित मज़दूरों के लिए पहचान पत्र और 2 लाख का दुर्घटना बीमा।",
        "benefit_amount_inr": 200000,
        "effort": "low",
        "source_url": "https://eshram.gov.in/",
        "match_confidence": 0.74,
    },
]

STUB_RESPONSE_HI = (
    "Sukanya Samriddhi Yojana ek bachat yojana hai jo aapki beti ke "
    "bhavishya ke liye hai."
)
