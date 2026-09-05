"""Publish a fresh teacher workspace without inheriting personal seed memory."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Literal

from app.services.class_provisioning import _wiki_creation_lock
from app.teacher_agent.wiki_store import WikiStore

# A reviewed file allowlist, not a directory copy: unrelated uploads or teacher
# notes under a shared directory must not enter an empty teacher workspace.
SHARED_ASSETS = (
    "AGENTS.md",
    "wiki/subjects/chemie.md",
    "wiki/subjects/chemie/competency_model.md",
    "wiki/subjects/chemie/differentiation.md",
    "wiki/subjects/chemie/lesson_planning.md",
    "wiki/subjects/chemie/teaching_frameworks/index.md",
    "wiki/subjects/chemie/teaching_frameworks/08/key_summary.md",
    "wiki/subjects/chemie/teaching_frameworks/08/course_network_seed.json",
    "wiki/subjects/chemie/teaching_frameworks/09/key_summary.md",
    "wiki/subjects/chemie/teaching_frameworks/09/course_network_seed.json",
    "wiki/subjects/chemie/teaching_frameworks/09/competencies.md",
    "wiki/subjects/chemie/teaching_frameworks/09/differentiation.md",
    "wiki/subjects/chemie/teaching_frameworks/09/representations_and_models.md",
    "wiki/sources/bayern/lehrplanplus/chemie_fachprofil.md",
    "wiki/sources/bayern/lehrplanplus/chemie_8_ntg.md",
    "wiki/sources/bayern/lehrplanplus/chemie_9_ntg.md",
    "wiki/sources/bayern/lehrplanplus/chemie_10_ntg.md",
    "wiki/sources/bayern/kmk/chemie_ahr_chemie_2020.md",
    "raw/sources/bayern/lehrplanplus/chemie_8_ntg.pdf",
    "raw/sources/bayern/lehrplanplus/chemie_8_ntg.extracted.md",
    "raw/sources/bayern/lehrplanplus/chemie_9_ntg.pdf",
    "raw/sources/bayern/lehrplanplus/chemie_9_ntg.extracted.md",
    "raw/sources/bayern/kmk/chemie_ahr_2020.pdf",
    "raw/sources/bayern/kmk/chemie_ahr_2020.extracted.md",
)


def initialize_teacher_workspace(
    seed_root: Path, destination: Path, *, mode: Literal["empty", "demo"] = "empty"
) -> None:
    """Publish a complete staged wiki once; never replace an existing workspace."""
    if mode not in {"empty", "demo"}:
        raise ValueError("Workspace mode must be 'empty' or 'demo'.")
    seed_root, destination = Path(seed_root), Path(destination)
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".workspace-", dir=destination.parent))
    try:
        if mode == "demo":
            shutil.copytree(
                seed_root, staging, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("workflow"),
            )
        else:
            for relative in SHARED_ASSETS:
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(seed_root / relative, target)
            (staging / "wiki/classes").mkdir(parents=True)
            (staging / "wiki/teacher_profile.md").write_text(
                "# Teacher Profile\n\n"
                "> Global, cross-class teacher preferences.\n\n"
                "## Lesson Style\n_No preferences recorded yet._\n\n"
                "## Communication\n_No preferences recorded yet._\n",
                encoding="utf-8",
            )
            (staging / "log.md").write_text("# Wiki Change Log\n", encoding="utf-8")
            WikiStore(root=staging).rebuild_index()
        # Reuse the wiki's cross-process creation lock to serialize publication.
        with _wiki_creation_lock(destination.parent):
            if not destination.exists():
                staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
