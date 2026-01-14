# TextArena Web UI

A minimal interactive web interface for playing TextArena games with human players against AI agents.

## Features

- **Universal**: Works with any TextArena environment
- **Flexible Players**: Support for any combination of human and AI players
- **Multiple AI Models**: Choose from various AI models via OpenRouter
- **Real-time**: Instant updates as the game progresses
- **Clean UI**: Minimal, readable interface

## Quick Start

### 1. Install Dependencies

```bash
# Backend
pip install fastapi uvicorn websockets

# Frontend
cd web_ui/frontend
npm install
```

### 2. Set API Key (for AI agents)

```bash
# Windows PowerShell
$env:OPENROUTER_API_KEY = "your-api-key"

# Linux/Mac
export OPENROUTER_API_KEY="your-api-key"
```

### 3. Run the Servers

**Backend** (Terminal 1):
```bash
cd web_ui/backend
python server.py
```

**Frontend** (Terminal 2):
```bash
cd web_ui/frontend
npm run dev
```

### 4. Open the UI

Navigate to http://localhost:3000

## Architecture

```
web_ui/
├── backend/
│   ├── server.py      # FastAPI server managing game sessions
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── App.jsx    # Main React component
│   │   ├── api.js     # API client
│   │   ├── styles.css # Styling
│   │   └── main.jsx   # Entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/environments` | GET | List available games |
| `/games` | POST | Create new game session |
| `/games/{id}` | GET | Get current game state |
| `/games/{id}/action` | POST | Submit player action |
| `/games/{id}` | DELETE | End game session |

## Customization

### Adding AI Models

Edit `DEFAULT_AGENTS` in `frontend/src/App.jsx`:

```javascript
const DEFAULT_AGENTS = [
  { label: 'My Model', value: 'provider/model-name' },
  // ...
];
```

### Using Different Environments

The UI automatically loads all registered TextArena environments. To use Werewolf:

1. Select "Werewolf-v0" from the dropdown
2. Set 6+ players (typical Werewolf game)
3. Configure which players are human vs AI

## Development

The frontend uses Vite with a proxy to the backend, so all `/api/*` requests are forwarded to `localhost:8000`.

For hot reloading during development:
- Backend: Use `uvicorn server:app --reload`
- Frontend: `npm run dev` includes hot reload
