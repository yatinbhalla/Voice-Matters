# Scheme Corpus

Source data for government schemes ingested into Pinecone.

## Storage convention

- `schemes/raw/` — original source PDFs, named `<scheme_id>.pdf`
  (e.g. `pmkisan.pdf`, `ayushman-bharat.pdf`). Treat as immutable.
- `schemes/processed/` — parsed JSON, named `<scheme_id>.json`. Each record
  contains normalized fields: `scheme_id`, `name`, `ministry`, `summary`,
  `eligibility`, `documents_required`, `apply_steps`, `source_url`,
  `chunks` (list of `{id, text, page}` ready for embedding).

Ingestion pipeline (raw -> processed -> Pinecone) lands in a later prompt.
