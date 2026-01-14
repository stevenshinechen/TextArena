"""
TextArena Web UI Backend Server

Follows the standard TextArena game loop pattern (see examples/werewolf_play.py).
"""

import uuid
from typing import Any, Optional
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import textarena as ta


# ============================================================================
# Models
# ============================================================================


class PlayerConfig(BaseModel):
    player_id: int
    player_type: str  # "human" or "agent"
    agent_model: Optional[str] = None


class GameConfig(BaseModel):
    env_id: str
    players: list[PlayerConfig]
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    action: str


class GameStateResponse(BaseModel):
    game_id: str
    current_player_id: int
    is_human_turn: bool
    observation: str
    done: bool
    rewards: Optional[dict[int, int]] = None
    game_info: Optional[Any] = None  # Can have int keys from TextArena


# ============================================================================
# Game Session (follows werewolf_play.py pattern)
# ============================================================================


@dataclass
class GameSession:
    """A game session following the standard TextArena pattern."""

    game_id: str
    env: ta.Env
    agents: dict[int, Optional[ta.Agent]]  # None = human player
    human_observation: str = ""  # Store human's last observation
    done: bool = False
    rewards: Optional[dict[int, int]] = None
    game_info: Optional[dict[str, Any]] = None

    current_player_id: int = 0  # Track current player

    def get_state(self) -> GameStateResponse:
        """Get current state - only show human's observation."""
        return GameStateResponse(
            game_id=self.game_id,
            current_player_id=self.current_player_id,
            is_human_turn=(self.agents.get(self.current_player_id) is None),
            observation=self.human_observation,
            done=self.done,
            rewards=self.rewards,
            game_info=self.game_info,
        )

    def _refresh_state(self):
        """Update current player and observation from env."""
        player_id, observation = self.env.get_observation()
        self.current_player_id = player_id

        # Only update human observation when it's human's turn
        if self.agents.get(player_id) is None:
            self.human_observation = (
                observation if isinstance(observation, str) else str(observation)
            )

    def step(self, action: str):
        """Execute one step: env.step(action)."""
        self.done, _ = self.env.step(action=action)
        if self.done:
            self.rewards, self.game_info = self.env.close()
        else:
            self._refresh_state()

    def run_agent_turns(self) -> GameStateResponse:
        """Run the game loop for agent turns until human turn or done."""
        while not self.done:
            player_id, observation = self.env.get_observation()
            self.current_player_id = player_id
            agent = self.agents.get(player_id)

            if agent is None:  # Human's turn - stop and wait for input
                self.human_observation = (
                    observation if isinstance(observation, str) else str(observation)
                )
                break

            # Agent takes action (standard TextArena pattern)
            action = agent(observation)
            self.done, _ = self.env.step(action=action)

            if self.done:
                self.rewards, self.game_info = self.env.close()

        return self.get_state()


# ============================================================================
# Game Manager
# ============================================================================


class GameManager:
    def __init__(self):
        self.sessions: dict[str, GameSession] = {}

    def create(self, config: GameConfig) -> GameSession:
        """Create game following werewolf_play.py pattern."""
        game_id = str(uuid.uuid4())[:8]

        # Build agents dict: {player_id: agent or None for human}
        agents: dict[int, Optional[ta.Agent]] = {}
        for p in config.players:
            if p.player_type == "human":
                agents[p.player_id] = None
            elif (
                p.agent_model == "random-werewolf"
            ):  # TODO try to make this more general
                agents[p.player_id] = ta.agents.RandomWerewolfAgent()
            else:
                agents[p.player_id] = ta.agents.OpenRouterAgent(
                    model_name=p.agent_model
                )

        # Initialize environment
        env = ta.make(env_id=config.env_id)

        # Only wrap if not already wrapped TODO maybe remove if
        if not env.is_wrapped_with(ta.wrappers.LLMObservationWrapper):
            env = ta.wrappers.LLMObservationWrapper(env)

        env.reset(num_players=len(agents), seed=config.seed)

        session = GameSession(game_id=game_id, env=env, agents=agents)
        # Initialize state from env
        player_id, observation = env.get_observation()
        session.current_player_id = player_id
        if agents.get(player_id) is None:  # Human's turn
            session.human_observation = (
                observation if isinstance(observation, str) else str(observation)
            )

        self.sessions[game_id] = session
        return session

    def get(self, game_id: str) -> Optional[GameSession]:
        return self.sessions.get(game_id)

    def delete(self, game_id: str) -> bool:
        return self.sessions.pop(game_id, None) is not None


# ============================================================================
# FastAPI App
# ============================================================================

games = GameManager()
app = FastAPI(title="TextArena Web UI", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/environments")
def list_environments():
    try:
        from textarena.envs.registration import ENV_REGISTRY

        return {"environments": sorted(ENV_REGISTRY.keys())}
    except Exception as e:
        return {"environments": [], "error": str(e)}


@app.post("/games", response_model=GameStateResponse)
def create_game(config: GameConfig):
    try:
        session = games.create(config)
        return session.get_state()  # Return immediately, don't run agents
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/games/{game_id}/run_agents", response_model=GameStateResponse)
def run_agents(game_id: str):
    """Run agent turns until human turn or game end."""
    session = games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    return session.run_agent_turns()


@app.get("/games/{game_id}", response_model=GameStateResponse)
def get_game(game_id: str):
    session = games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    return session.get_state()


@app.post("/games/{game_id}/action", response_model=GameStateResponse)
def submit_action(game_id: str, request: ActionRequest):
    session = games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    if session.done:
        raise HTTPException(status_code=400, detail="Game already finished")

    # Human step, then run agent turns
    session.step(request.action)
    return session.run_agent_turns()


@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    if games.delete(game_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Game not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
