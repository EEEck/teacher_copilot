"""Backend-owned, reviewable skills selected from class configuration."""

from app.teacher_agent.skills.chemie_bayern import lesson_skill_for_subject
from app.teacher_agent.skills.loader import compose_active_skill

__all__ = ["compose_active_skill", "lesson_skill_for_subject"]
