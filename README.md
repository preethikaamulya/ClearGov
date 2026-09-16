# ClearGov Nexus — Full Working Prototype

## Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

## Frontend
cd frontend
npm install
npm run dev

The frontend uses the real FastAPI endpoints. A judge can create a fresh application, enter real data, upload a real PDF/PNG/JPEG, send it to the backend, process the submitted evidence, receive a decision trace, and create human-review cases. The current processing layer records real uploaded evidence and structured application facts; production OCR/issuer verification/LLM extraction can be plugged into the backend without changing the workflow.
