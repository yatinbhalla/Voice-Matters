# API Contracts

Versioned under `/api/v1`. All stubs return `{"status": "not_implemented"}`
until backed by real services.

## Endpoints

- `POST /conversation/{id}/voice` — multipart audio upload, returns transcript + reply
- `POST /conversation/{id}/chat` — text message, returns reply
- `GET  /conversation/{id}/messages` — message history
- `GET  /conversations` — list user conversations
- `GET  /schemes/{scheme_id}` — scheme metadata
- `GET  /schemes/{scheme_id}/explain` — plain-Hindi explanation
- `GET  /schemes/{scheme_id}/apply-steps` — ordered application steps
- `POST /conversation/{id}/action` — log a user action (bookmark, share, etc.)
- `GET  /admin/trust-metrics` — aggregated quality + trust signals
