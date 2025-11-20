import verifiers as vf

import time
from copy import deepcopy
from typing import Any, Callable

from openai import AsyncOpenAI

from verifiers import MultiTurnEnv
from verifiers.envs.textarena_env import TextArenaEnv
from verifiers.types import (
    ChatCompletion,
    ChatMessage,
    Completion,
    Info,
    Messages,
    SamplingArgs,
    State,
)
from verifiers.utils.async_utils import maybe_await
import textarena as ta


class MultiAgentTextArenaEnv(TextArenaEnv):
    def __init__(
        self,
        agents: dict[int, Callable[[str], str]],
        main_agent_id: int = 0,
        *args,
        **kwargs,
    ):
        self.agents = agents
        self.main_agent_id = main_agent_id
        self.number_of_agents = len(agents)
        super().__init__(*args, **kwargs)

    async def env_response(
        self, messages: Messages, state: State, **kwargs: Any
    ) -> tuple[Messages, State]:
        ta_env = self._ensure_environment_initialized(state)
        state.setdefault("agents", self.agents)
        state.setdefault("main_agent_id", self.main_agent_id)

        if not state.get("awaiting_model_action"):
            env_msgs = self._advance_until_main_turn(state)
            return env_msgs, state

        assert isinstance(messages[-1], dict)
        guess = self.parser.parse_answer(messages)
        is_completed, _ = ta_env.step(str(guess))
        state["is_completed"] = is_completed
        state["awaiting_model_action"] = False
        
        try:
            player_id, observation = ta_env.get_observation()
        except Exception:
            player_id, observation = state.get("main_agent_id", 0), "Game concluded."

        env_messages: list[dict[str, str]] = [
            {"role": "user", "content": str(self.feedback_fn(observation))}
        ]
        env_messages.extend(
            self._advance_until_main_turn(
                state,
                start_player_id=player_id,
                start_observation=observation,
                skip_initial_feedback=True,
            )
        )
        return env_messages, state

    async def rollout(
        self,
        client: AsyncOpenAI,
        model: str,
        prompt: Messages,
        completion: Messages | None = None,
        answer: str = "",
        state: State = {},
        task: str = "default",
        info: Info | None = None,
        example_id: int = 0,
        sampling_args: SamplingArgs | None = None,
        **kwargs,
    ) -> tuple[Messages, State]:
        """
        Generate a multi-turn rollout with the environment (messages, state).
        """
        completion = completion or await self.init_completion()
        info = info if info is not None else {}
        is_completed = False
        state = state or await self.init_state(
            prompt, completion, answer, task, info, example_id, agents=self.agents
        )
        start_time = time.time()
        state = await maybe_await(self.setup_state, state, **kwargs)
        if self.message_type == "chat":
            assert isinstance(state["prompt"], list)
            assert isinstance(state["completion"], list)
        else:
            assert isinstance(state["prompt"], str)
            assert isinstance(state["completion"], str)
            state["responses_start_idx"] = []
        while not is_completed:
            context_messages = await self.get_context_messages(state)
            if await maybe_await(self.is_completed, context_messages, state, **kwargs):
                is_completed = True
                break
            response = await self.get_model_response(
                client,
                model,
                context_messages,
                oai_tools=info.get("oai_tools", None),
                sampling_args=sampling_args,
                message_type=self.message_type,
                initial_prompt=len(state["responses"]) == 0,
                **kwargs,
            )
            if response is not None and response.id == "overlong-prompt":
                state["prompt_too_long"] = True
                break
            state["responses"].append(response)
            response_text: str = ""
            if self.message_type == "chat":
                assert isinstance(context_messages, list)
                assert isinstance(response, ChatCompletion)
                if response.choices and response.choices[0].message:
                    response_text = response.choices[0].message.content or ""
                response_message: ChatMessage = {
                    "role": "assistant",
                    "content": response_text,
                }
                if (
                    response.choices
                    and response.choices[0].message
                    and response.choices[0].message.tool_calls
                ):
                    tool_calls = response.choices[0].message.tool_calls
                    response_message["tool_calls"] = [  # type: ignore
                        tool_call.model_dump() for tool_call in tool_calls
                    ]
                state["completion"].append(response_message)
            else:
                assert isinstance(response, Completion)
                state["responses_start_idx"].append(len(completion))
                if response.choices and response.choices[0]:
                    response_text = response.choices[0].text or ""
                state["completion"] += response_text
            context_messages = await self.get_context_messages(state)
            state["turn"] += 1
            if await maybe_await(self.is_completed, context_messages, state, **kwargs):
                is_completed = True
                end_time = time.time()
                state["timing"]["generation_ms"] = (end_time - start_time) * 1000
                state["timing"]["total_ms"] = (end_time - start_time) * 1000
            else:
                env_msgs, state = await maybe_await(
                    self.env_response, context_messages, state, **kwargs
                )
                if self.message_type == "chat":
                    assert isinstance(env_msgs, list)
                    state["completion"] += env_msgs
                else:
                    assert isinstance(env_msgs, str)
                    state["completion"] += env_msgs
        return state["completion"], state

    async def init_state(
        self,
        prompt: Messages,
        completion: Messages,
        answer: str,
        task: str,
        info: Info,
        example_id: int,
        agents: dict | None = None,
        **kwargs,
    ) -> State:
        resolved_agents = agents or self.agents
        state = {
            "prompt": prompt,
            "completion": completion,
            "answer": answer,
            "task": task,
            "info": info,
            "example_id": example_id,
            "agents": resolved_agents,
            "main_agent_id": self.main_agent_id,
            "responses": [],
            "turn": 0,
            "timing": {
                "generation_ms": 0.0,
                "scoring_ms": 0.0,
                "total_ms": 0.0,
            },
            "awaiting_model_action": False,
        }
        return state

    async def setup_state(self, state: State, **kwargs: Any) -> State:
        state = await super().setup_state(state, **kwargs)
        state.setdefault("agents", self.agents)
        state.setdefault("main_agent_id", self.main_agent_id)
        if self.message_type == "chat":
            initial_msgs = self._advance_until_main_turn(state)
            if initial_msgs:
                assert isinstance(state["completion"], list)
                state["completion"] += initial_msgs
        return state

    def _ensure_environment_initialized(self, state: State):
        ta_env = state.get("ta_env")
        if ta_env is None:
            ta_env = deepcopy(self.ta_env)
            ta_env.reset(num_players=self.number_of_agents)
            if "answer" in state and hasattr(ta_env, "state"):
                try:
                    ta_env.state.game_state["secret_word"] = state["answer"]
                except Exception:
                    pass
            state["ta_env"] = ta_env
            state["awaiting_model_action"] = False
        return ta_env

    def _advance_until_main_turn(
        self,
        state: State,
        start_player_id: int | None = None,
        start_observation: str | None = None,
        skip_initial_feedback: bool = False,
    ) -> list[dict[str, str]]:
        ta_env = self._ensure_environment_initialized(state)
        agents = state.get("agents", self.agents)
        main_agent_id = state.get("main_agent_id", self.main_agent_id)

        if start_player_id is None or start_observation is None:
            player_id, observation = ta_env.get_observation()
            skip_initial_feedback = False
        else:
            player_id, observation = start_player_id, start_observation

        board_shared = skip_initial_feedback
        messages: list[dict[str, str]] = []

        while True:
            state["next_player_id"] = player_id
            if state.get("is_completed"):
                break

            if player_id == main_agent_id:
                if not board_shared:
                    messages.append(
                        {"role": "user", "content": str(self.feedback_fn(observation))}
                    )
                    board_shared = True
                state["awaiting_model_action"] = not state.get("is_completed", False)
                break

            agent_callable = agents.get(player_id)
            if agent_callable is None:
                raise ValueError(f"No agent registered for player id {player_id}.")

            action = agent_callable(observation)
            action_message = f"Player {player_id} action: {action}"
            messages.append({"role": "user", "content": action_message})

            is_completed, _ = ta_env.step(action)
            state["is_completed"] = is_completed
            if is_completed:
                board_shared = False
                break

            player_id, observation = ta_env.get_observation()
            messages.append({"role": "user", "content": str(self.feedback_fn(observation))})
            board_shared = True

        return messages
        
def load_environment(**kwargs) -> vf.Environment:
    '''
    Loads a custom environment.
    
    Expected kwargs:
        agents: dict[int, Callable[[str], str]] - Dictionary mapping player IDs to agent callables
        main_agent_id: int - ID of the main agent being trained (default: 0)
        All other TextArenaEnv parameters (game, num_train_examples, etc.)
    '''
    # Extract multi-agent specific parameters
    agents = kwargs.pop("agents", {})
    main_agent_id = kwargs.pop("main_agent_id", 0)
    
    if not agents:
        raise ValueError("'agents' dictionary must be provided in kwargs")
    
    return MultiAgentTextArenaEnv(
        agents=agents,
        main_agent_id=main_agent_id,
        **kwargs
    )
