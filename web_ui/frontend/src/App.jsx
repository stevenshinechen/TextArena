import { useState, useEffect, useRef } from 'react';
import { fetchEnvironments, createGame, submitAction, deleteGame, runAgents } from './api';

const DEFAULT_AGENTS = [
  { label: "GPT-4o Mini", value: "openai/gpt-4o-mini" },
  { label: "Claude 3 Haiku", value: "anthropic/claude-3-haiku" },
  { label: "Gemini Flash", value: "google/gemini-flash-1.5" },
  { label: "DeepSeek Chat", value: "deepseek/deepseek-chat" },
  { label: "Llama 3.1 8B", value: "meta-llama/llama-3.1-8b-instruct" },
  { label: "GPT-oss free", value: "openai/gpt-oss-20b:free" },
];

const WEREWOLF_AGENTS = [
  { label: "Random Werewolf Agent", value: "random-werewolf" },
  ...DEFAULT_AGENTS,
];

const PHASE_MESSAGES = {
  "Werewolf-Discussion": "Werewolves debating...",
  "Werewolf-Vote": "Werewolves voting...",
  "Guard-Protect": "Guard deciding...",
  "Witch-Choice": "Witch deciding...",
  "Seer-Reveal": "Seer investigating...",
  "Day-Discussion": "Day discussion...",
  "Day-Vote": "Village voting...",
};

const isApiError = (msg) => {
  const lower = msg.toLowerCase();
  return [
    "credit",
    "api",
    "quota",
    "rate limit",
    "ratelimit",
    "unauthorized",
    "authentication",
    "timeout",
    "ai agent error",
    "429",
    "500",
    "502",
    "503",
  ].some((term) => lower.includes(term));
};

function GameSetup({ onGameCreated }) {
  const [environments, setEnvironments] = useState([]);
  const [selectedEnv, setSelectedEnv] = useState("");
  const [numPlayers, setNumPlayers] = useState(6);
  const [players, setPlayers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEnvironments()
      .then((data) => {
        setEnvironments(data.environments || []);
        if (data.environments?.length > 0) {
          setSelectedEnv(
            data.environments.find((e) => e.includes("Werewolf")) ||
              data.environments[0]
          );
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setPlayers(
      Array.from({ length: numPlayers }, (_, i) => ({
        player_id: i,
        player_type: i === 0 ? "human" : "agent",
        agent_model: DEFAULT_AGENTS[0].value,
      }))
    );
  }, [numPlayers]);

  const updatePlayer = (index, field, value) => {
    setPlayers((prev) => {
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
        players: players.map((p) => ({
          player_id: p.player_id,
          player_type: p.player_type,
          agent_model: p.player_type === "agent" ? p.agent_model : null,
        })),
      };
      onGameCreated(await createGame(config));
    } catch (err) {
      const msg = err.message || "An unexpected error occurred";
      if (isApiError(msg)) alert(msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const agentOptions = selectedEnv.includes("Werewolf")
    ? WEREWOLF_AGENTS
    : DEFAULT_AGENTS;

  return (
    <div className="setup-panel">
      <h2>Game Setup</h2>
      {error && <div className="error">{error}</div>}

      <div className="form-group">
        <label>Environment</label>
        <select
          value={selectedEnv}
          onChange={(e) => setSelectedEnv(e.target.value)}
        >
          {environments.map((env) => (
            <option key={env} value={env}>
              {env}
            </option>
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
          onChange={(e) =>
            setNumPlayers(
              Math.max(1, Math.min(20, parseInt(e.target.value) || 1))
            )
          }
        />
      </div>

      <div className="players-config">
        <label>Player Configuration</label>
        {players.map((player, i) => (
          <div key={i} className="player-row">
            <span>Player {i}</span>
            <select
              value={player.player_type}
              onChange={(e) => updatePlayer(i, "player_type", e.target.value)}
            >
              <option value="human">Human</option>
              <option value="agent">AI Agent</option>
            </select>
            {player.player_type === "agent" && (
              <select
                value={player.agent_model}
                onChange={(e) => updatePlayer(i, "agent_model", e.target.value)}
              >
                {agentOptions.map((agent) => (
                  <option key={agent.value} value={agent.value}>
                    {agent.label}
                  </option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>

      <button
        className="primary"
        onClick={handleCreateGame}
        disabled={loading || !selectedEnv}
      >
        {loading ? (
          <span className="loading">
            <span className="spinner" /> Creating...
          </span>
        ) : (
          "Start Game"
        )}
      </button>
    </div>
  );
}

function GamePanel({ gameState, onGameEnd, onGameUpdate }) {
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [adminMode, setAdminMode] = useState(false);
  const observationRef = useRef(null);
  const initialRunDone = useRef(false);

  const handleError = (err) => {
    const msg = err.message || "An unexpected error occurred";
    if (isApiError(msg)) alert(msg);
    setError(msg);
  };

  // Run agent turns on initial load if AI starts
  useEffect(() => {
    if (
      !initialRunDone.current &&
      !gameState.done &&
      !gameState.is_human_turn
    ) {
      initialRunDone.current = true;
      setLoading(true);
      runAgents(gameState.game_id)
        .then(onGameUpdate)
        .catch(handleError)
        .finally(() => setLoading(false));
    }
  }, [
    gameState.game_id,
    gameState.is_human_turn,
    gameState.done,
    onGameUpdate,
  ]);

  useEffect(() => {
    if (observationRef.current) {
      observationRef.current.scrollTop = observationRef.current.scrollHeight;
    }
  }, [gameState.observation]);

  useEffect(() => {
    if (gameState.done) setAdminMode(true);
  }, [gameState.done]);

  const handleSubmit = async () => {
    if (!action.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const newState = await submitAction(gameState.game_id, action);
      setAction("");
      onGameUpdate(newState);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEndGame = async () => {
    try {
      await deleteGame(gameState.game_id);
    } catch {}
    onGameEnd();
  };

  const phaseMsg = PHASE_MESSAGES[gameState.current_phase] || "AI thinking...";

  const statusBadge = gameState.done ? (
    <span className="status-badge finished">Game Over</span>
  ) : loading ? (
    <span className="status-badge waiting">
      <span className="spinner small" /> {phaseMsg}
    </span>
  ) : gameState.is_human_turn ? (
    <span className="status-badge your-turn">Your Turn</span>
  ) : (
    <span className="status-badge waiting">{phaseMsg}</span>
  );

  const observation = adminMode
    ? gameState.observation || "Waiting for game to start..."
    : gameState.latest_observation ||
      gameState.observation ||
      "Waiting for game to start...";

  return (
    <div className="game-panel">
      <div className="game-header">
        <div>
          <h2>Game in Progress</h2>
          <span className="game-id">Game ID: {gameState.game_id}</span>
        </div>
        <div className="header-actions">
          {statusBadge}
          <button className="danger" onClick={handleEndGame}>
            End Game
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="observation-panel">
        <div className="observation-header">
          <h3>Game State</h3>
          <button
            className={`toggle-btn ${adminMode ? "active" : ""}`}
            onClick={() => setAdminMode(!adminMode)}
            title={
              adminMode
                ? "Showing full game history"
                : "Showing latest message only"
            }
          >
            {adminMode ? "📜 Full History" : "💬 Latest Only"}
          </button>
        </div>
        <div
          className={`observation-content ${adminMode ? "admin-mode" : ""}`}
          ref={observationRef}
        >
          {observation}
        </div>
      </div>

      {!gameState.done && (
        <div className="action-panel">
          <textarea
            value={action}
            onChange={(e) => setAction(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder={
              gameState.is_human_turn
                ? "Enter your action... (Press Enter to submit)"
                : "Waiting for AI..."
            }
            disabled={!gameState.is_human_turn || loading}
          />
          <button
            className="primary"
            onClick={handleSubmit}
            disabled={!gameState.is_human_turn || loading || !action.trim()}
          >
            {loading ? (
              <span className="loading">
                <span className="spinner" />
              </span>
            ) : (
              "Submit"
            )}
          </button>
        </div>
      )}

      {gameState.done && gameState.rewards && (
        <div className="results-panel">
          <h3>🏆 Game Results</h3>
          <div className="rewards">
            {Object.entries(gameState.rewards).map(([id, reward]) => (
              <div
                key={id}
                className={`reward-item ${
                  reward > 0 ? "winner" : reward < 0 ? "loser" : ""
                }`}
              >
                Player {id}: {reward > 0 ? "+" : ""}
                {reward}
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
