# Kautilya AI

This repository is organized into two main parts:

- **/frontend**: React-based single-page application.
- **/backend**: Flask-based API, agents, and background workers.

## Running Locally

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Frontend
```bash
cd frontend
npm install
npm start
```

## Deployment
- Backend is configured for HuggingFace Spaces or Koyeb (see `backend/start.sh`).
- Frontend is configured for Koyeb Static Sites (see `frontend/deploy_frontend.sh`).
