# Care-Plan Portal (Next.js)

Doctor-facing Next.js UI that orchestrates the Care-Plan Agent and supporting services.

## Setup
1. `cd frontend`
2. `cp .env.local.example .env.local` and adjust URLs/tokens (set `OPENAI_API_KEY` to enable LLM-backed nodes).
3. Install dependencies: `npm install`

## Develop
```bash
npm run dev
```
The app runs on <http://127.0.0.1:8080> by default (`next dev -p 8080`).

## Build & start
```bash
npm run build
npm run start
```

## API proxy routes
- `POST /api/care-plan` → forwards to `CARE_PLAN_URL` (Care-Plan Agent)
- `POST /api/evidence` → forwards to `EVIDENCE_URL` (auto-derives payload from EHR when only `patient_id` is supplied)
- `GET /api/labs` → proxies `EHR_URL/patients/{id}/labs`

All external calls are made server-side so tokens in `.env.local` remain private.
