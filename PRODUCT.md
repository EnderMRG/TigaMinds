# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: tea estate manager or owner based in Assam, India. They use CHAI-NET during their working day to make fast operational decisions — when to irrigate, when to harvest, whether a disease threat is real, and when to sell at auction. They are comfortable with smartphones and dashboards but are not data scientists; they need the system to surface the right action, not raw data.

Secondary: farm supervisors and pluckers who receive SMS worker alerts via the dashboard.

## Product Purpose

CHAI-NET is an integrated IoT + AI platform for Assam tea estate management. It ingests real-time sensor data (soil moisture, temperature, humidity, rainfall), runs computer-vision disease detection on leaf scan photos, applies ML models for drought and pest risk, forecasts Guwahati auction prices, and distils all of that into a single prioritised action plan. Success means an estate manager can open the dashboard every morning and know exactly what to do that day without calling an agronomist or manually inspecting records.

## Positioning

End-to-end IoT + AI in one product: sensor readings -> leaf scan -> market price forecast -> actionable daily plan, with no third-party stitching required. The ML models are trained on Assam tea disease images and Guwahati auction history, making the recommendations locally calibrated rather than generic.

## Operating Context

- Estate managers typically check the dashboard once in the morning and again after field rounds.
- IoT sensors push readings continuously; the dashboard reflects near-real-time state.
- Leaf scans are uploaded via mobile camera on-site.
- Market intelligence is consulted weekly around auction cycles.
- SMS alerts are sent to worker groups via Twilio when conditions require action.
- Demo mode allows prospective users to explore a fully populated dashboard without an account.

## Capabilities and Constraints

- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, Recharts, shadcn/ui components.
- Backend: FastAPI (Python), Firebase Firestore, Firebase Auth (Google Sign-In), Gemini AI, YOLOv5 + CNN for leaf classification, Scikit-learn for pest/drought prediction, Twilio for SMS.
- Bilingual UI: English and Assamese (language toggle exists).
- The Gemini API is currently on the free tier (5 req/min); fallback messages are in place.
- Demo mode authenticates via a local mock user; all demo data is served from the backend as static fixtures.
- Deployment target: Render (render.yaml present).

## Brand Commitments

None locked. Full creative freedom on name presentation, color, and typography.

## Evidence on Hand

- README.md with full feature descriptions and architecture diagram.
- Live running codebase: frontend at localhost:3000, backend at localhost:8000.
- Pre-populated demo farm data (fixture fallbacks in backend for daily metrics, sensor readings, market data).
- Guwahati auction price dataset (teadata.xlsx) used for ML price forecasting.

## Product Principles

1. **One screen, one decision.** Every dashboard view should surface a clear recommended action, not raw numbers.
2. **Locally calibrated.** Assam-specific disease models, Guwahati auction data, and Assamese language support make CHAI-NET credible to its users in a way a generic agri-platform cannot be.
3. **Always alive.** Demo mode, fallback fixtures, and Gemini rate-limit handling mean the product never shows a blank screen to a prospective user.
4. **Field-first.** The primary interaction is a quick morning check on a laptop or tablet; design for scannability and decisive action over analytical depth.
5. **Trust through transparency.** Confidence scores, data source labels, and AI attribution prevent the manager from treating model output as oracle.
