from pathlib import Path

from stockimformation.errors import NodeExecutionError
from stockimformation.node.models import SkillDefinition


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


def load_skill_handler(name: str, skill_handlers_dir: Path = Path("skill_handlers")) -> Path:
    path = skill_handlers_dir / f"{name}.py"
    if not path.exists():
        raise NodeExecutionError(f"missing skill handler: {name}")
    return path.resolve()
