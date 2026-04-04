from __future__ import annotations

from typing import Any, Optional

from ..environment.engine import SupplyChainEngine
from ..models import Action
from .action_catalog import ACTION_CATALOG_SIZE, build_action_catalog
from .encoding import OBSERVATION_VECTOR_LENGTH, encode_observation

try:
    import gymnasium as gym
    from gymnasium import spaces
    import numpy as np
except ImportError as exc:  # pragma: no cover - optional dependency
    gym = None
    spaces = None
    np = None
    GYM_IMPORT_ERROR = exc
else:
    GYM_IMPORT_ERROR = None


if gym is not None:
    class SupplyChainGymEnv(gym.Env):
        metadata = {"render_modes": ["human"], "render_fps": 4}

        def __init__(self, default_task_id: str = "task_easy"):
            self.engine = SupplyChainEngine()
            self.default_task_id = default_task_id
            self.current_observation = None
            self._action_catalog: list[dict[str, Any]] = []

            self.action_space = spaces.Discrete(ACTION_CATALOG_SIZE)
            self.observation_space = spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(OBSERVATION_VECTOR_LENGTH,),
                dtype=np.float32,
            )

        def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
            super().reset(seed=seed)
            task_id = (options or {}).get("task_id", self.default_task_id)
            self.current_observation = self.engine.reset(task_id)
            encoded = np.asarray(encode_observation(self.current_observation), dtype=np.float32)
            self._action_catalog = build_action_catalog(self.current_observation)
            info = {
                "task_id": task_id,
                "action_catalog": list(self._action_catalog),
                "raw_observation": self.current_observation.model_dump(),
            }
            return encoded, info

        def step(self, action_index: int):
            if self.current_observation is None:
                raise RuntimeError("Call reset() before step().")

            safe_index = int(action_index) % ACTION_CATALOG_SIZE
            action_payload = self._action_catalog[safe_index]
            result = self.engine.step(Action(**action_payload))
            self.current_observation = result["observation"]
            self._action_catalog = build_action_catalog(self.current_observation)

            encoded = np.asarray(encode_observation(self.current_observation), dtype=np.float32)
            reward = float(result["reward"]["value"])
            terminated = bool(result["done"])
            truncated = False
            info = {
                **result["info"],
                "action_payload": action_payload,
                "action_catalog": list(self._action_catalog),
                "raw_observation": self.current_observation.model_dump(),
            }
            return encoded, reward, terminated, truncated, info

        def render(self):
            if self.current_observation is None:
                return "Environment not reset."
            return self.current_observation.message

        def get_action_catalog(self) -> list[dict[str, Any]]:
            return list(self._action_catalog)

else:
    class SupplyChainGymEnv:  # pragma: no cover - optional dependency
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "gymnasium and numpy are required for SupplyChainGymEnv. "
                "Install requirements-rl.txt first."
            ) from GYM_IMPORT_ERROR
