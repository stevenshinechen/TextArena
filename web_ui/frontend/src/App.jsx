import { useState, useEffect, useRef } from 'react';
import { fetchEnvironments, createGame, submitAction, deleteGame, runAgents } from './api';

// Default agent models
const DEFAULT_AGENTS = [
  { label: 'GPT-4o Mini', value: 'openai/gpt-4o-mini' },
  { label: 'Claude 3 Haiku', value: 'anthropic/claude-3-haiku' },
  { label: 'Gemini Flash', value: 'google/gemini-flash-1.5' },
  { label: 'DeepSeek Chat', value: 'deepseek/deepseek-chat' },
  { label: 'Llama 3.1 8B', value: 'meta-llama/llama-3.1-8b-instruct' },
  { label: 'GPT-oss free', value: 'openai/gpt-oss-20b:free' },
];

// Werewolf-specific agents
const WEREWOLF_AGENTS = [
  { label: 'Random Werewolf Agent', value: 'random-werewolf' },
  ...DEFAULT_AGENTS,
];

function GameSetup({ onGameCreated }) {
  const [environments, setEnvironments] = useState([]);
  const [selectedEnv, setSelectedEnv] = useState('');
  const [numPlayers, setNumPlayers] = useState(2);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch available environments
  useEffect(() => {
    fetchEnvironments()
      .then(data => {
        setEnvironments(data.environments || []);
        if (data.environments?.length > 0) {
          // Default to Werewolf if available, otherwise first env
          const defaultEnv = data.environments.find(e => e.includes('Werewolf')) || data.environments[0];
          setSelectedEnv(defaultEnv);
        }
      })
      .catch(err => setError(err.message));
  }, []);

  // Update players when numPlayers changes
  useEffect(() => {
    setPlayers(
      Array.from({ length: numPlayers }, (_, i) => ({
        player_id: i,
        player_type: i === 0 ? 'human' : 'agent',
        agent_model: DEFAULT_AGENTS[0].value,
      }))
    );
  }, [numPlayers]);

  const updatePlayer = (index, field, value) => {
    setPlayers(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleCreateGame = async () => {
    setLoading(true);
    setError(null);
    try {
      const config = {
        env_id: selectedEnv,
        players: players.map(p => ({
          player_id: p.player_id,
          player_type: p.player_type,
          agent_model: p.player_type === 'agent' ? p.agent_model : null,
        })),
      };
      const gameState = await createGame(config);
      onGameCreated(gameState);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="setup-panel">
      <h2>Game Setup</h2>
      
      {error && <div className="error">{error}</div>}
      
      <div className="form-group">
        <label>Environment</label>
        <select value={selectedEnv} onChange={e => setSelectedEnv(e.target.value)}>
          {environments.map(env => (
            <option key={env} value={env}>{env}</option>
          ))}
        </select>
      </div>
      
      <div className="form-group">
        <label>Number of Players</label>
        <input
          type="number"
          min="1"
          max="20"
          value={numPlayers}
          onChange={e => setNumPlayers(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
        />
      </div>
      
      <div className="players-config">
        <label>Player Configuration</label>
        {players.map((player, i) => (
          <div key={i} className="player-row">
            <span>Player {i}</span>
            <select
              value={player.player_type}
              onChange={e => updatePlayer(i, 'player_type', e.target.value)}
            >
              <option value="human">Human</option>
              <option value="agent">AI Agent</option>
            </select>
            {player.player_type === 'agent' && (
              <select
                value={player.agent_model}
                onChange={e => updatePlayer(i, 'agent_model', e.target.value)}
              >
                {(selectedEnv.includes('Werewolf') ? WEREWOLF_AGENTS : DEFAULT_AGENTS).map(agent => (
                  <option key={agent.value} value={agent.value}>{agent.label}</option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>
      
      <button className="primary" onClick={handleCreateGame} disabled={loading || !selectedEnv}>
        {loading ? <span className="loading"><span className="spinner" /> Creating...</span> : 'Start Game'}
      </button>
    </div>
  );
}


function GamePanel({ gameState, onGameEnd, onGameUpdate }) {
  const [action, setAction] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const observationRef = useRef(null);
  const initialRunDone = useRef(false);

  // Run agent turns ONLY on initial load when it's AI's turn
  // After that, submitAction handles running agents on the backend
  useEffect(() => {
    if (!initialRunDone.current && !gameState.done && !gameState.is_human_turn) {
      initialRunDone.current = true;
      setLoading(true);
      runAgents(gameState.game_id)
        .then(newState => {
          onGameUpdate(newState);
        })
        .catch(err => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [gameState.game_id, gameState.is_human_turn, gameState.done, onGameUpdate]);

  // Auto-scroll observation to bottom
  useEffect(() => {
    if (observationRef.current) {
      observationRef.current.scrollTop = observationRef.current.scrollHeight;
    }
  }, [gameState.observation]);

  const handleSubmit = async () => {
    if (!action.trim() || loading) return;
    
    setLoading(true);
    setError(null);
    try {
      const newState = await submitAction(gameState.game_id, action);
      setAction('');
      onGameUpdate(newState);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleEndGame = async () => {
    try {
      await deleteGame(gameState.game_id);
    } catch (err) {
      console.error('Failed to delete game:', err);
    }
    onGameEnd();
  };

  const getStatusBadge = () => {
    if (gameState.done) return <span className="status-badge finished">Game Over</span>;
    if (gameState.is_human_turn) return <span className="status-badge your-turn">Your Turn</span>;
    return <span className="status-badge waiting">AI Thinking...</span>;
  };

  return (
    <div className="game-panel">
      <div className="game-header">
        <div>
          <h2>Game in Progress</h2>
          <span className="game-id">ID: {gameState.game_id} | Player {gameState.current_player_id}'s turn</span>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {getStatusBadge()}
          <button className="danger" onClick={handleEndGame}>End Game</button>
        </div>
      </div>
      
      {error && <div className="error">{error}</div>}
      
      <div className="observation-panel">
        <h3>Game State</h3>
        <div className="observation-content" ref={observationRef}>
          {gameState.observation || 'Waiting for game to start...'}
        </div>
      </div>
      
      {!gameState.done && (
        <div className="action-panel">
          <textarea
            value={action}
            onChange={e => setAction(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={gameState.is_human_turn ? "Enter your action... (Press Enter to submit)" : "Waiting for AI..."}
            disabled={!gameState.is_human_turn || loading}
          />
          <button
            className="primary"
            onClick={handleSubmit}
            disabled={!gameState.is_human_turn || loading || !action.trim()}
          >
            {loading ? <span className="loading"><span className="spinner" /></span> : 'Submit'}
          </button>
        </div>
      )}
      
      {gameState.done && gameState.rewards && (
        <div className="results-panel">
          <h3>Game Results</h3>
          <div className="rewards">
            {Object.entries(gameState.rewards).map(([playerId, reward]) => (
              <div
                key={playerId}
                className={`reward-item ${reward > 0 ? 'winner' : reward < 0 ? 'loser' : ''}`}
              >
                Player {playerId}: {reward > 0 ? '+' : ''}{reward}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


export default function App() {
  const [gameState, setGameState] = useState(null);

  return (
    <div className="app">
      <h1>🎮 TextArena</h1>
      
      {!gameState ? (
        <GameSetup onGameCreated={setGameState} />
      ) : (
        <GamePanel
          gameState={gameState}
          onGameEnd={() => setGameState(null)}
          onGameUpdate={setGameState}
        />
      )}
    </div>
  );
}
