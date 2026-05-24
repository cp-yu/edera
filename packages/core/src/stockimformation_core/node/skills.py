from pathlib import Path

from stockimformation_core.errors import NodeExecutionError
from stockimformation_core.node.models import SkillDefinition


def load_skill(name: str, skills_dir: Path = Path("skills")) -> SkillDefinition:
    path = skills_dir / name
    skill_path = path / "skill.md"
    workflow_path = path / "workflow.md"
    if not skill_path.exists() or not workflow_path.exists():
        raise NodeExecutionError(f"missing skill: {name}")
    return SkillDefinition(
        name=name,
        path=path.resolve(),
        skill_md=skill_path.read_text(),
        workflow_md=workflow_path.read_text(),
    )

