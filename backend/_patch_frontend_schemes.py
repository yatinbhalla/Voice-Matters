"""Replace the frontend's local SCHEMES dict + downstream references
with the 7 new schemes. Runs in-place on web/index.html."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web" / "index.html"

NEW_SCHEMES_BLOCK = r"""const SCHEMES = {
  'pmjdy':{
    scheme_id:'pmjdy', name_en:'Pradhan Mantri Jan Dhan Yojana', name_hi:'प्रधानमंत्री जन धन योजना',
    ministry:'Ministry of Finance', ministry_hi:'वित्त मंत्रालय',
    category_label:'Banking · Zero-balance khata', match_confidence:0.92,
    one_line_pitch_hi:'Zero-balance khata + ₹2 lakh durghatna beema + ₹10,000 overdraft - sab muft',
    helpline_phone:'011-23361571', helpline_hours:'Sub din · 9am–6pm',
    source_url:'https://www.pmjdy.gov.in/', pdf_url:'https://www.pmjdy.gov.in/files/E-Documents/PMJDY_BROCHURE_ENG.pdf',
    tags:['Banking','Muft khata','Beema','RuPay'],
    summary_hi:'PMJDY hai un sab logon ke liye jinka abhi tak bank khaata nahi khula. Khaata zero-balance par khulta hai, koi minimum amount nahi rakhna. Saath mein muft RuPay card aur ₹2 lakh ka durghatna beema bhi milta hai.',
    summary_en:'PMJDY is a national financial inclusion mission. It opens a basic savings account with zero minimum balance, a free RuPay debit card with ₹2 lakh accident insurance, and an overdraft facility up to ₹10,000.',
    stats:[['₹2 lakh','Durghatna beema'],['₹10,000','Overdraft'],['₹0','Minimum balance']],
    benefits:[
      {head:'Zero-balance khaata', sub:'Khaate mein paisa rakhna zaroori nahi - kabhi bhi kholo aur chalu rakho.'},
      {head:'Muft RuPay debit card', sub:'Card par ₹2 lakh ka durghatna beema bhi milta hai.'},
      {head:'₹10,000 ka overdraft', sub:'Khaate mein paisa kam padne par bhi nikaal sakte ho.'},
      {head:'Mobile aur ATM se sahi', sub:'Bank shaakha, ATM ya Bank Mitr - jahan se chahe paisa nikalo.'},
      {head:'Chhota khaata bhi', sub:'Kaagaz na hone par bhi 12 mahine ke liye chhota khaata khul sakta hai.'},
    ],
    eligibility:[
      {field:'citizen', text_hi:'Bharat ka naagrik ho', status:'yes'},
      {field:'aadhaar', text_hi:'Aadhaar ya koi sarkari ID', status:'yes'},
      {field:'age', text_hi:'10 saal se upar ke bachche bhi (guardian ke saath)', status:'yes'},
    ],
    documents_needed:['Aadhaar card','Sarkari pehchan patra','Pata ka praman','Passport photo'],
  },
  'pmuy':{
    scheme_id:'pmuy', name_en:'Pradhan Mantri Ujjwala Yojana 2.0', name_hi:'प्रधानमंत्री उज्ज्वला योजना 2.0',
    ministry:'Ministry of Petroleum and Natural Gas', ministry_hi:'पेट्रोलियम एवं प्राकृतिक गैस मंत्रालय',
    category_label:'Mahila · Free LPG', match_confidence:0.88,
    one_line_pitch_hi:'Mahilaaon ke liye free LPG connection - chulha aur pehla refill bhi muft',
    helpline_phone:'1800-266-6696', helpline_hours:'Sub din · 24 ghante',
    source_url:'https://www.pmuy.gov.in/', pdf_url:'',
    tags:['Mahila','LPG','Saaf-suthra eindhan','Ghar'],
    summary_hi:'PMUY 2.0 paat-r pariwaaron ki mahilaaon ko bilkul muft LPG gas connection deti hai. Sath mein chulha aur pehla cylinder refill bhi muft milta hai - koi security deposit nahi lagta.',
    summary_en:'PMUY 2.0 provides eligible women from poor and deprived households a deposit-free LPG connection, free first refill, and free cooking stove.',
    stats:[['Free','Connection'],['Free','Pehla refill'],['Free','Chulha']],
    benefits:[
      {head:'Deposit-free LPG connection', sub:'14.2 kg cylinder par ₹1,600 ki sahaayata, koi paisa upfront nahi.'},
      {head:'Muft chulha aur pehla refill', sub:'Oil companies aapko gas chulha aur ek refill cylinder muft deti hain.'},
      {head:'Pravaasi pariwaaron ke liye bhi', sub:'Ration card nahi to self-declaration chalega - migrant workers ko aasaani.'},
      {head:'Mahila ke naam par hi', sub:'Connection saaf-suthre eindhan se mahilaa aur bachchon ke swaasthya ke liye.'},
      {head:'Indane, Bharatgas, HP - sab', sub:'Kisi bhi gas vitarak se le sakte ho, online ya offline apply.'},
    ],
    eligibility:[
      {field:'gender', text_hi:'Aavedika mahilaa ho', status:'yes'},
      {field:'age', text_hi:'Umar 18 saal ya zyaada', status:'yes'},
      {field:'lpg', text_hi:'Pehle se LPG connection na ho', status:'unk'},
      {field:'category', text_hi:'SC/ST/PMAY-G/AAY/SECC ya gareeb pariwaar', status:'unk', rank_hi:'List mein naam check karna hoga'},
    ],
    documents_needed:['Aadhaar card','Ration card','KYC dastaavej','Bank passbook','Photo'],
  },
  'kcc':{
    scheme_id:'kcc', name_en:'Kisan Credit Card', name_hi:'किसान क्रेडिट कार्ड',
    ministry:'Ministry of Agriculture & Farmers’ Welfare', ministry_hi:'कृषि एवं किसान कल्याण मंत्रालय',
    category_label:'Kisaan · Credit card', match_confidence:0.90,
    one_line_pitch_hi:'Kheti aur paludhan ke liye 4% byaaj par loan - 5 saal ka credit card',
    helpline_phone:'1800-180-1551', helpline_hours:'Sub din · 9am–6pm',
    source_url:'https://pib.gov.in/FactsheetDetails.aspx?Id=148600',
    pdf_url:'https://rbidocs.rbi.org.in/rdocs/notification/PDFs/04MCKCC030720171E79A08735884C429CF26F5414AB36D9.PDF',
    tags:['Kisaan','Loan','Kheti','Credit'],
    summary_hi:'Kisan Credit Card kisaano ko sasti dar par loan deta hai - kheti, fasal kataai ke baad, paludhan aur farm machinery ke liye. Time par chukane par byaaj sirf 4% ke karib aata hai aur card 5 saal ke liye valid hota hai.',
    summary_en:'Kisan Credit Card provides farmers timely and affordable credit for crop cultivation, post-harvest, farm maintenance, and allied activities. Interest subvention and prompt-repayment incentive bring the effective rate to about 4%.',
    stats:[['~4%','Effective byaaj'],['5 saal','Card validity'],['Aasaan','Apply']],
    benefits:[
      {head:'Sasta byaaj - ~4% effective', sub:'2% subvention + 3% prompt-repayment incentive milake byaaj ghat jaata hai.'},
      {head:'Kheti se jude sab kharch', sub:'Beej, khaad, machinery, paludhan, mandi - sab cover.'},
      {head:'Batayi-daar aur kiraayedaar bhi', sub:'Zameen apne naam na ho to bhi SHG/JLG ke through mil sakta hai.'},
      {head:'5 saal valid', sub:'Card 5 saal ke liye chalta hai - har baar apply nahi karna.'},
      {head:'ATM, mobile aur BC', sub:'ATM, micro-ATM, mobile banking, Aadhaar-enabled - sab se nikaalo.'},
    ],
    eligibility:[
      {field:'farmer', text_hi:'Kheti karte ho (apni ya batayi)', status:'yes'},
      {field:'age', text_hi:'Umar 18 saal ya zyaada', status:'yes'},
      {field:'bank', text_hi:'Bank khaata zaroori', status:'yes'},
      {field:'default', text_hi:'Bank default record nahi', status:'unk'},
    ],
    documents_needed:['Aavedan patra','Pehchaan praman','Pata praman','Zameen ke kaagaz','Fasal pattern','Photo'],
  },
  'day-nrlm':{
    scheme_id:'day-nrlm', name_en:'Deendayal Antyodaya Yojana - NRLM', name_hi:'दीनदयाल अंत्योदय योजना',
    ministry:'Ministry of Rural Development', ministry_hi:'ग्रामीण विकास मंत्रालय',
    category_label:'Grameen · SHG livelihood', match_confidence:0.82,
    one_line_pitch_hi:'SHG ke through grameen mahilaaon ko bachat aur loan - kam byaaj par credit',
    helpline_phone:'1800-102-0988', helpline_hours:'Som–Shani · 10am–6pm',
    source_url:'https://aajeevika.gov.in/', pdf_url:'',
    tags:['Grameen','Mahila','SHG','Loan','Livelihood'],
    summary_hi:'DAY-NRLM grameen garib pariwaaron, khaaskar mahilaaon ko SHG (Self-Help Group) se jodta hai. Group ke through bachat, internal loan aur fir bank-linkage milti hai - kam byaaj par 3 lakh tak ka credit aur kaushal training.',
    summary_en:'DAY-NRLM is a flagship rural poverty reduction programme. It organizes rural poor households into Self Help Groups for collective savings, financial inclusion, skill development, and access to bank credit at concessional rates.',
    stats:[['7%','Effective byaaj'],['SHG','Group savings'],['Grameen','Mahila focus']],
    benefits:[
      {head:'SHG bachat aur internal loan', sub:'Group regular bachat karta hai aur sadasyon ko aapas mein loan deta hai.'},
      {head:'Bank-linkage credit', sub:'Sahi SHG ko bank se ₹3 lakh tak ka loan kam byaaj par milta hai.'},
      {head:'Revolving Fund aur CIF', sub:'Group ko sarkar revolving aur community-investment fund deti hai.'},
      {head:'Kaushal training', sub:'Yuvaaon ke liye skill training aur livelihood opportunities.'},
      {head:'Vishesh dhyaan', sub:'Vidhwa, single mahila, divyaangjan, bhoomi-heen mazdoor - prathmikta.'},
    ],
    eligibility:[
      {field:'rural', text_hi:'Grameen pariwaar ho', status:'yes'},
      {field:'shg', text_hi:'Sahi SHG ka sadasya 6+ mahine purana', status:'unk', rank_hi:'SHG record check karna hoga'},
      {field:'panchasutra', text_hi:'Panchasutra ka palan kare', status:'unk'},
    ],
    documents_needed:['Aadhaar number','Pehchaan praman','Niwaas praman','Voter ID','Passport photo'],
  },
  'pmjjby':{
    scheme_id:'pmjjby', name_en:'Pradhan Mantri Jeevan Jyoti Bima Yojana', name_hi:'प्रधानमंत्री जीवन ज्योति बीमा योजना',
    ministry:'Ministry of Finance', ministry_hi:'वित्त मंत्रालय',
    category_label:'Beema · Jeevan suraksha', match_confidence:0.85,
    one_line_pitch_hi:'Sirf ₹436 saal mein ₹2 lakh ka jeevan beema - sab tarah ki maut cover',
    helpline_phone:'1800-180-1111', helpline_hours:'Sub din · 24 ghante',
    source_url:'https://www.jansuraksha.gov.in',
    pdf_url:'https://www.jansuraksha.gov.in/Files/PMJJBY/English/Rules.pdf',
    tags:['Beema','Jeevan suraksha','Saste premium'],
    summary_hi:'PMJJBY ek 1-saal ka renewable jeevan beema hai jisme sirf ₹436 saalana premium par ₹2 lakh ka cover milta hai. Kisi bhi karan se maut hone par poora paisa nominee ko milta hai. Bank/post office se auto-debit ho jaata hai.',
    summary_en:'PMJJBY is a one-year renewable term life insurance scheme. For a premium of just ₹436 per year, it provides a ₹2 lakh cover on death from any cause. Premium is auto-debited from the bank/post office account.',
    stats:[['₹2 lakh','Cover'],['₹436','Saal mein'],['18-50','Umar']],
    benefits:[
      {head:'₹2 lakh cover', sub:'Sab tarah ki maut par nominee ko ₹2 lakh milte hain - natural ya accidental.'},
      {head:'Sirf ₹436 saalana', sub:'Bank/post office khaate se auto-debit ho jaata hai - bharna nahi padta.'},
      {head:'Har saal renew', sub:'Premium chalta rahe to cover bhi chalta rahe - 50+ tak.'},
      {head:'Aasaan nominee claim', sub:'Maut hone par nominee bank/post office mein form bhar ke claim karta hai.'},
      {head:'Net banking se bhi join', sub:'Bank ki branch jaane ki zaroorat nahi - online enrollment.'},
    ],
    eligibility:[
      {field:'age', text_hi:'Umar 18 se 50 saal', status:'yes'},
      {field:'bank', text_hi:'Bank ya post office mein savings khaata', status:'yes'},
      {field:'aadhaar', text_hi:'Aadhaar KYC', status:'yes'},
      {field:'autodebit', text_hi:'Auto-debit ki sahmati', status:'yes'},
    ],
    documents_needed:['Aadhaar card','Bank passbook','Mobile number','Nominee ka byora'],
  },
  'pmmy':{
    scheme_id:'pmmy', name_en:'Pradhan Mantri Mudra Yojana', name_hi:'प्रधानमंत्री मुद्रा योजना',
    ministry:'Ministry of Finance (DFS)', ministry_hi:'वित्त मंत्रालय',
    category_label:'Vyaapar · Collateral-free loan', match_confidence:0.87,
    one_line_pitch_hi:'Chhote vyaapar ke liye ₹50,000 se ₹20 lakh tak collateral-free loan',
    helpline_phone:'1800-180-1111', helpline_hours:'Sub din · 24 ghante',
    source_url:'https://www.mudra.org.in',
    pdf_url:'https://www.mudra.org.in/Default/DownloadFile/MudraLoan-SalientFeatures-English.pdf',
    tags:['Vyaapar','MSME','Loan','Mudra','Self-employment'],
    summary_hi:'Mudra Yojana sookshma aur laghu udyamiyon ko bina kisi gehna rakhe loan deti hai. Char shreniyaan hain - Shishu (50,000 tak), Kishore (5 lakh tak), Tarun (10 lakh tak) aur Tarun Plus (20 lakh tak). Vyaapar shuru karna ho ya badhana - sab ke liye.',
    summary_en:'PMMY provides collateral-free loans to micro and small enterprises in the non-farm sector. Four categories: Shishu (up to ₹50,000), Kishore (up to ₹5 lakh), Tarun (up to ₹10 lakh), and Tarun Plus (up to ₹20 lakh) for those who have repaid a Tarun loan.',
    stats:[['₹20 lakh','Tak loan'],['No','Collateral'],['4','Shreniyaan']],
    benefits:[
      {head:'Collateral-free loan', sub:'Koi gehna ya zameen rakhne ki zaroorat nahi.'},
      {head:'4 shreniyaan', sub:'Shishu 50k, Kishore 5L, Tarun 10L, Tarun Plus 20L - apni zaroorat chuno.'},
      {head:'Vyaapar ke har kharch ke liye', sub:'Machinery, working capital, dukaan ka setup, vistaar - sab.'},
      {head:'Online apply', sub:'Udyamimitra portal par OTP se register karke apply karo.'},
      {head:'Saari banks par available', sub:'Sarkari bank, RRB, sahakari bank, NBFC, MFI - kahin bhi.'},
    ],
    eligibility:[
      {field:'enterprise', text_hi:'Vyaapar shuru karna ya chala rahe ho (non-farm)', status:'yes'},
      {field:'age', text_hi:'Umar 18 saal ya zyaada', status:'yes'},
      {field:'bank', text_hi:'Bank khaata zaroori', status:'yes'},
      {field:'default', text_hi:'Pehle ka bank default record nahi', status:'unk'},
    ],
    documents_needed:['Pehchaan praman','Pata praman','Photo','Vyaapar ka pata','Project report','Bank statements'],
  },
  'mmsby':{
    scheme_id:'mmsby', name_en:'Mukhmantri Sehat Bima Yojana', name_hi:'मुख्यमंत्री सेहत बीमा योजना',
    ministry:'Government of Punjab (SHA)', ministry_hi:'पंजाब सरकार · राज्य स्वास्थ्य एजेंसी',
    category_label:'Sehat · Cashless ilaaj (Punjab)', match_confidence:0.83,
    one_line_pitch_hi:'Punjab pariwaaron ke liye ₹5 lakh ka cashless ilaaj - sarkari aur niji aspataalon mein',
    helpline_phone:'104', helpline_hours:'Sub din · 24 ghante',
    source_url:'https://sha.punjab.gov.in/shapunjab/index.php',
    pdf_url:'',
    tags:['Sehat','Punjab','Cashless','Beema','State scheme'],
    summary_hi:'MMSBY (AB PM-JAY MMSBY) Punjab raajya ki swaasthya yojana hai. Pat-r pariwaaron ko har saal ₹5 lakh tak ka cashless ilaaj milta hai - sarkari aur empanelled niji aspataalon mein, paisa nahi dena. Punjab ki 65% aabaadi cover hai.',
    summary_en:'Mukhmantri Sehat Bima Yojana (AB PM-JAY MMSBY) is Punjab’s flagship health protection scheme. Eligible families receive ₹5 lakh per year of cashless treatment at empanelled government and private hospitals.',
    stats:[['₹5 lakh','Saal mein'],['Cashless','Ilaaj'],['65%','Punjab cover']],
    benefits:[
      {head:'₹5 lakh ka cover', sub:'Har pat-r pariwaar ko har saal - bada operation bhi cover.'},
      {head:'Cashless aur paperless', sub:'Aspataal mein paisa nahi dena - bill sarkar bhar deti hai.'},
      {head:'Secondary aur tertiary care', sub:'Aspataal mein bharti hone wali bimaariyaan - operation, ICU, dawai.'},
      {head:'Sarkari aur niji aspataal', sub:'Sirf sarkari nahi - sahi niji aspataal bhi shaamil.'},
      {head:'Aasaan e-card', sub:'Ayushman App ya portal par khud register karke e-card banaa lo.'},
    ],
    eligibility:[
      {field:'state', text_hi:'Punjab raajya ke nivaasi', status:'yes'},
      {field:'category', text_hi:'SECC/Smart Ration/J-form/etc shreni', status:'unk', rank_hi:'List mein naam check karna hoga'},
      {field:'aadhaar', text_hi:'Aadhaar zaroori', status:'yes'},
    ],
    documents_needed:['Aadhaar card','Ration card','Pariwaar ghoshna patra','Aay praman','Shreni ke anusaar (e.g. construction worker card)'],
  },
};
const SCHEME_ORDER = ['pmjdy','kcc','pmuy','pmjjby','pmmy','day-nrlm','mmsby'];
const top3 = ()=> ['pmjdy','kcc','pmjjby'].map(id=>{ const s=SCHEMES[id]; return {scheme_id:id,name_en:s.name_en,name_hi:s.name_hi,one_line_pitch_hi:s.one_line_pitch_hi,match_confidence:s.match_confidence}; });
"""

NEW_SAMPLE_BLOCK = """const SAMPLE_MESSAGES = [
  {id:'m-301', role:'user', modality:'voice', content_text:'Bank khaata kaise khulwayein muft mein', retrieved_schemes:['pmjdy'], created_at:Date.now()-1000*60*42, status:'Searched', scheme_id:'pmjdy'},
  {id:'m-298', role:'user', modality:'voice', content_text:'Mujhe kheti ke liye loan chahiye', retrieved_schemes:['kcc'], created_at:Date.now()-1000*60*180, status:'Saved', scheme_id:'kcc'},
  {id:'m-280', role:'user', modality:'text', content_text:'LPG connection free mein kaise milega', retrieved_schemes:['pmuy'], created_at:Date.now()-1000*60*60*26, status:'Applied', scheme_id:'pmuy'},
  {id:'m-265', role:'user', modality:'voice', content_text:'Sasta jeevan beema chahiye', retrieved_schemes:['pmjjby'], created_at:Date.now()-1000*60*60*30, status:'In progress', scheme_id:'pmjjby'},
  {id:'m-240', role:'user', modality:'text', content_text:'Chhota vyaapar shuru karne ke liye loan', retrieved_schemes:['pmmy'], created_at:Date.now()-1000*60*60*24*4, status:'Searched', scheme_id:'pmmy'},
];
"""

NEW_MOCK_ROUTER = """function mockChat(text){
  const t=(text||'').toLowerCase();
  let order=['pmjdy','kcc','pmjjby'];
  if(/kheti|kisan|farmer|fasal|khet/.test(t)) order=['kcc','pmjdy','pmmy'];
  else if(/lpg|gas|chulha|cylinder|ujjwala/.test(t)) order=['pmuy','pmjdy','pmjjby'];
  else if(/bank|khata|khaata|account|jan dhan/.test(t)) order=['pmjdy','pmjjby','pmmy'];
  else if(/beema|insurance|jeevan|life cover|maut/.test(t)) order=['pmjjby','pmjdy','mmsby'];
  else if(/loan|udhar|business|vyaapar|dukaan|mudra/.test(t)) order=['pmmy','kcc','pmjdy'];
  else if(/shg|grameen|mahila|self.help|livelihood|nrlm/.test(t)) order=['day-nrlm','pmjdy','kcc'];
  else if(/sehat|ilaaj|hospital|aspataal|punjab|health/.test(t)) order=['mmsby','pmjjby','pmjdy'];
"""


def main() -> int:
    text = WEB.read_text(encoding="utf-8")

    # 1. Replace SCHEMES dict + SCHEME_ORDER + top3. Match the whole block
    #    starting at "const SCHEMES = {" and ending at the top3 line.
    schemes_re = re.compile(
        r"const SCHEMES = \{[\s\S]*?const top3 = \(\)=>[^;]*;",
        re.MULTILINE,
    )
    if not schemes_re.search(text):
        print("FAIL: SCHEMES block not found")
        return 1
    text = schemes_re.sub(lambda m: NEW_SCHEMES_BLOCK.rstrip(), text, count=1)
    print("OK   SCHEMES dict + SCHEME_ORDER + top3 swapped")

    # 2. Replace SAMPLE_MESSAGES seeded conversation.
    sample_re = re.compile(
        r"const SAMPLE_MESSAGES = \[[\s\S]*?\];",
        re.MULTILINE,
    )
    if not sample_re.search(text):
        print("FAIL: SAMPLE_MESSAGES not found")
        return 1
    text = sample_re.sub(NEW_SAMPLE_BLOCK.rstrip(), text, count=1)
    print("OK   SAMPLE_MESSAGES swapped")

    # 3. Replace mockChat router (intent-based scheme reordering for fallback).
    mock_re = re.compile(
        r"function mockChat\(text\)\{\s*const t=\(text\|\|''\)\.toLowerCase\(\);[\s\S]*?(?=  const top=order\.map)",
        re.MULTILINE,
    )
    if not mock_re.search(text):
        print("WARN: mockChat router not matched (skipped)")
    else:
        text = mock_re.sub(NEW_MOCK_ROUTER, text, count=1)
        print("OK   mockChat intent-routing swapped")

    # 4. Fix the explain fallback that still references pm-kisan.
    text = text.replace(
        "SCHEMES[id]||SCHEMES['pm-kisan']",
        "SCHEMES[id]||SCHEMES['pmjdy']",
    )
    print("OK   explain-fallback default scheme updated")

    WEB.write_text(text, encoding="utf-8")
    print()
    print(f"wrote {WEB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
