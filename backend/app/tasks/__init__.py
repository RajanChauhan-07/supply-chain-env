# backend/app/tasks/__init__.py

# ── v1 tasks (legacy, still functional) ──
from .task_easy        import TaskEasy
from .task_medium      import TaskMedium
from .task_hard        import TaskHard
from .task_expert      import TaskExpert
from .task_adversarial import TaskAdversarial

# ── v2 tasks (God-level) ──
from .task_foundational    import TaskFoundational
from .task_multi_tier      import TaskMultiTier
from .task_stochastic      import TaskStochastic
from .task_adversarial_v2  import TaskAdversarialV2
from .task_full_sim        import TaskFullSim


# Registry — maps task_id to task class (includes both v1 & v2)
TASK_REGISTRY = {
    # v1 (backward compat)
    "task_easy":            TaskEasy,
    "task_medium":          TaskMedium,
    "task_hard":            TaskHard,
    "task_expert":          TaskExpert,
    "task_adversarial":     TaskAdversarial,
    # v2 (new)
    "task_foundational":    TaskFoundational,
    "task_multi_tier":      TaskMultiTier,
    "task_stochastic":      TaskStochastic,
    "task_adversarial_v2":  TaskAdversarialV2,
    "task_full_sim":        TaskFullSim,
}

TASK_LIST = [
    # v2 tasks (primary)
    {
        "id":          "task_foundational",
        "name":        "Basic Rerouting",
        "difficulty":  "easy",
        "description": TaskFoundational.task_description,
        "max_steps":   TaskFoundational.max_steps,
    },
    {
        "id":          "task_multi_tier",
        "name":        "Multi-Tier Crisis",
        "difficulty":  "medium",
        "description": TaskMultiTier.task_description,
        "max_steps":   TaskMultiTier.max_steps,
    },
    {
        "id":          "task_stochastic",
        "name":        "Stochastic Dynamic Risk",
        "difficulty":  "hard",
        "description": TaskStochastic.task_description,
        "max_steps":   TaskStochastic.max_steps,
    },
    {
        "id":          "task_adversarial_v2",
        "name":        "Trap & Verify",
        "difficulty":  "hard",
        "description": TaskAdversarialV2.task_description,
        "max_steps":   TaskAdversarialV2.max_steps,
    },
    {
        "id":          "task_full_sim",
        "name":        "Apple-Scale Full Simulation",
        "difficulty":  "expert",
        "description": TaskFullSim.task_description,
        "max_steps":   TaskFullSim.max_steps,
    },
    # v1 tasks (legacy, kept for backward compat)
    {
        "id":          "task_easy",
        "name":        "Single Lane Disruption (Legacy)",
        "difficulty":  "easy",
        "description": TaskEasy.task_description,
        "max_steps":   TaskEasy.max_steps,
    },
    {
        "id":          "task_medium",
        "name":        "Multi-Point Failure (Legacy)",
        "difficulty":  "medium",
        "description": TaskMedium.task_description,
        "max_steps":   TaskMedium.max_steps,
    },
    {
        "id":          "task_hard",
        "name":        "Cascade Crisis (Legacy)",
        "difficulty":  "hard",
        "description": TaskHard.task_description,
        "max_steps":   TaskHard.max_steps,
    },
    {
        "id":          "task_expert",
        "name":        "Cascading Domino Effect (Legacy)",
        "difficulty":  "expert",
        "description": TaskExpert.task_description,
        "max_steps":   TaskExpert.max_steps,
    },
    {
        "id":          "task_adversarial",
        "name":        "Supplier Trap Detection (Legacy)",
        "difficulty":  "adversarial",
        "description": TaskAdversarial.task_description,
        "max_steps":   TaskAdversarial.max_steps,
    },
]

__all__ = [
    "TaskEasy", "TaskMedium", "TaskHard", "TaskExpert", "TaskAdversarial",
    "TaskFoundational", "TaskMultiTier", "TaskStochastic",
    "TaskAdversarialV2", "TaskFullSim",
    "TASK_REGISTRY", "TASK_LIST",
]