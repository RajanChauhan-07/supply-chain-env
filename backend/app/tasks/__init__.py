# backend/app/tasks/__init__.py

from .task_easy   import TaskEasy
from .task_medium import TaskMedium
from .task_hard   import TaskHard

# Registry — maps task_id to task class
TASK_REGISTRY = {
    "task_easy":   TaskEasy,
    "task_medium": TaskMedium,
    "task_hard":   TaskHard,
}

TASK_LIST = [
    {
        "id":          "task_easy",
        "name":        "Single Lane Disruption",
        "difficulty":  "easy",
        "description": TaskEasy.task_description,
        "max_steps":   TaskEasy.max_steps,
    },
    {
        "id":          "task_medium",
        "name":        "Multi-Point Failure",
        "difficulty":  "medium",
        "description": TaskMedium.task_description,
        "max_steps":   TaskMedium.max_steps,
    },
    {
        "id":          "task_hard",
        "name":        "Cascade Crisis",
        "difficulty":  "hard",
        "description": TaskHard.task_description,
        "max_steps":   TaskHard.max_steps,
    },
]

__all__ = [
    "TaskEasy",
    "TaskMedium",
    "TaskHard",
    "TASK_REGISTRY",
    "TASK_LIST",
]