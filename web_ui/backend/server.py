"""TextArena Web UI Backend Server"""

import re
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


# Models

class PlayerConfig(BaseModel):
    player_id: int
    player_type: str
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
    latest_observation: str
    current_phase: Optional[str] = None
    done: bool
    rewards: Optional[dict[int, int]] = None
    game_info: Optional[Any] = None


# Game Session


@dataclass
class GameSession:
    game_id: str
    env: ta.Env
    agents: dict[int, Optional[ta.Agent]]
    full_history: str = ""
    current_turn_observation: str = ""
    done: bool = False
    rewards: Optional[dict[int, int]] = None
    game_info: Optional[dict[str, Any]] = None
    current_player_id: int = 0

    def _get_phase(self) -> Optional[str]:
        env = self.env
        while hasattr(env, "env"):
            env = env.env
        if hasattr(env, "phase"):
            return getattr(env.phase, "value", str(env.phase))
        return None

    def _to_str(self, obs) -> str:
        return obs if isinstance(obs, str) else str(obs)

    def _append_history(self, player_id: int, obs: str, is_human: bool):
        label = "Human" if is_human else "AI"
        self.full_history += f"\n{'='*60}\n[Player {player_id} ({label}) Turn]\n{'='*60}\n{self._to_str(obs)}"

    def _set_human_observation(self, player_id: int, obs):
        self.current_turn_observation = self._to_str(obs)
        self._append_history(player_id, obs, is_human=True)

    def get_state(self) -> GameStateResponse:
        return GameStateResponse(
            game_id=self.game_id,
            current_player_id=self.current_player_id,
            is_human_turn=self.agents.get(self.current_player_id) is None,
            observation=self.full_history,
            latest_observation=self.current_turn_observation,
            current_phase=self._get_phase(),
            done=self.done,
            rewards=self.rewards,
            game_info=self.game_info,
        )

    def step(self, action: str):
        self.done, _ = self.env.step(action=action)
        if self.done:
            self.rewards, self.game_info = self.env.close()
        else:
            player_id, obs = self.env.get_observation()
            self.current_player_id = player_id
            if self.agents.get(player_id) is None:
                self._set_human_observation(player_id, obs)

    def run_agents(self) -> GameStateResponse:
        while not self.done:
            player_id, obs = self.env.get_observation()
            self.current_player_id = player_id
            agent = self.agents.get(player_id)

            if agent is None:
                self._set_human_observation(player_id, obs)
                break

            self._append_history(player_id, obs, is_human=False)
            action = agent(obs)
            self.done, _ = self.env.step(action=action)

            if self.done:
                self.rewards, self.game_info = self.env.close()

        return self.get_state()


# Game Manager

class GameManager:
    def __init__(self):
        self.sessions: dict[str, GameSession] = {}

    def create(self, config: GameConfig) -> GameSession:
        game_id = str(uuid.uuid4())[:8]

        agents: dict[int, Optional[ta.Agent]] = {}
        needs_json_render = False

        for p in config.players:
            if p.player_type == "human":
                agents[p.player_id] = None
            elif p.agent_model == "random-werewolf":
                agents[p.player_id] = ta.agents.RandomWerewolfAgent()
                needs_json_render = True
            else:
                agents[p.player_id] = ta.agents.OpenRouterAgent(
                    model_name=p.agent_model
                )

        # RandomWerewolfAgent requires JSON-formatted game state
        env_kwargs = {}
        if needs_json_render:
            from textarena.envs.Werewolf.renderer import RenderStateFormat

            env_kwargs["render_state_format"] = RenderStateFormat.JSON

        env = ta.make(env_id=config.env_id, **env_kwargs)
        if not env.is_wrapped_with(ta.wrappers.LLMObservationWrapper):
            env = ta.wrappers.LLMObservationWrapper(env)
        env.reset(num_players=len(agents), seed=config.seed)

        session = GameSession(game_id=game_id, env=env, agents=agents)
        player_id, obs = env.get_observation()
        session.current_player_id = player_id
        if agents.get(player_id) is None:
            session._set_human_observation(player_id, obs)

        self.sessions[game_id] = session
        return session

    def get(self, game_id: str) -> Optional[GameSession]:
        return self.sessions.get(game_id)

    def delete(self, game_id: str) -> bool:
        return self.sessions.pop(game_id, None) is not None


# Error Handling


def _parse_api_error(e: Exception) -> str:
    s = str(e).lower()

    if "429" in s or ("rate" in s and "limit" in s):
        match = re.search(r"'message':\s*'([^']+)'", str(e))
        if match:
            return f"API Rate Limit Error: {match.group(1)}"
        return (
            "API Rate Limit Error: Quota exceeded. Add credits or wait before retrying."
        )

    if "401" in s or "unauthorized" in s or "authentication" in s:
        return "API Authentication Error: Invalid API key."

    if "quota" in s or "credit" in s:
        return f"API Quota Error: {e}"

    if "timeout" in s:
        return "API Timeout Error: Model took too long. Try again."

    if any(code in s for code in ["500", "502", "503"]):
        return "API Server Error: Service temporarily unavailable."

    return f"AI Agent Error: {e}"


# FastAPI App

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
        return games.create(config).get_state()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/games/{game_id}/run_agents", response_model=GameStateResponse)
def run_agents(game_id: str):
    session = games.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        return session.run_agents()
    except Exception as e:
        raise HTTPException(status_code=503, detail=_parse_api_error(e))


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
    try:
        session.step(request.action)
        return session.run_agents()
    except Exception as e:
        raise HTTPException(status_code=503, detail=_parse_api_error(e))


@app.delete("/games/{game_id}")
def delete_game(game_id: str):
    if games.delete(game_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Game not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
