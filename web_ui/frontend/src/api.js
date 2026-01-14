const API_BASE = '/api';

export async function fetchEnvironments() {
  const res = await fetch(`${API_BASE}/environments`);
  if (!res.ok) throw new Error('Failed to fetch environments');
  return res.json();
}

export async function createGame(config) {
  const res = await fetch(`${API_BASE}/games`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to create game');
  }
  return res.json();
}

export async function runAgents(gameId) {
  const res = await fetch(`${API_BASE}/games/${gameId}/run_agents`, {
    method: 'POST',
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to run agents');
  }
  return res.json();
}

export async function getGameState(gameId) {
  const res = await fetch(`${API_BASE}/games/${gameId}`);
  if (!res.ok) throw new Error('Failed to get game state');
  return res.json();
}

export async function submitAction(gameId, action) {
  const res = await fetch(`${API_BASE}/games/${gameId}/action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to submit action');
  }
  return res.json();
}

export async function deleteGame(gameId) {
  const res = await fetch(`${API_BASE}/games/${gameId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete game');
  return res.json();
}
