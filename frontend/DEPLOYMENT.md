# Kautilya AI Frontend - Deployment Guide

## Overview
This is the frontend for Kautilya AI, integrated with the jarvis backend. It's a React application built with Vite/Craco, featuring a chat interface and dashboard for managing AI agents, campaigns, and analytics.

## Prerequisites
- Node.js 18+ 
- npm or yarn
- Backend API running (jarvis)

## Local Development

### 1. Install Dependencies
```bash
npm install --legacy-peer-deps
```

### 2. Configure Environment
Create a `.env` file:
```
REACT_APP_API_URL=http://localhost:5000
```

### 3. Start Development Server
```bash
npm start
```
The app will be available at `http://localhost:3000`

## Building for Production

### 1. Build the Application
```bash
npm run build
```
This creates an optimized production build in the `build/` directory.

### 2. Test Production Build Locally
```bash
npm install -g serve
serve -s build -l 3000
```

## Deployment on Koyeb

### Using koyeb.yaml
The `koyeb.yaml` file is pre-configured for deployment.

```bash
koyeb deploy
```

### Manual Deployment
1. Build the application: `npm run build`
2. Deploy the `build/` directory to your hosting service
3. Set environment variable: `REACT_APP_API_URL=https://your-api-url.com`

## Environment Variables

- `REACT_APP_API_URL`: Base URL for the backend API (default: `http://localhost:5000`)
- Production: Set to your production API URL

## Firebase Authentication

The frontend uses Firebase authentication. The backend handles Firebase token verification. Set the token in localStorage as `firebase_token` after authentication.

## API Endpoints

The frontend communicates with the following backend endpoints:

- `/api/jarvis/stream` - Chat streaming
- `/api/jarvis/history` - Chat history
- `/api/agents/*` - Agent management
- `/api/campaigns/*` - Campaign management
- `/api/user/*` - User profile

## Components

### Chat Interface
- Real-time streaming chat with AI
- Conversation history management
- Markdown rendering for responses
- Canvas integration for artifacts

### Dashboard
- **Agent Studio**: Create and manage AI agents
- **Campaign Dialer**: Manage outbound calling campaigns
- **Lead Management**: Track and manage leads
- **Call Analytics**: View call performance metrics
- **BI Analytics**: Business intelligence dashboards
- **Widget Preview**: Generate embeddable chat widgets

## Troubleshooting

### Build Errors
If you encounter peer dependency errors, use:
```bash
npm install --legacy-peer-deps
```

### API Connection Issues
- Verify `REACT_APP_API_URL` is set correctly
- Check CORS configuration on the backend
- Ensure Firebase token is set in localStorage

## Support
For issues or questions, refer to the jarvis backend documentation.
