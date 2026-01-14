# TextArena Web UI Backend

## Requirements
- fastapi
- uvicorn
- websockets

## Installation
```bash
pip install fastapi uvicorn websockets
```

## Running
```bash
cd web_ui/backend
python server.py
```

Or with uvicorn directly:
```bash
uvicorn server:app --reload --port 8000
```

## API Endpoints

- `GET /` - Health check
- `GET /environments` - List available environments
- `POST /games` - Create a new game
- `GET /games/{game_id}` - Get game state
- `POST /games/{game_id}/action` - Submit player action
- `DELETE /games/{game_id}` - Delete game session
- `WS /ws/{game_id}` - WebSocket for real-time updates
