from pathlib import Path


def test_save_entities() -> None:
    source = Path("frontend/src/features/workbench/components/Inspector.tsx").read_text()
    assert "EntitySelector" in source
    assert "entities" in source


def test_save_permissions() -> None:
    source = Path("frontend/src/features/workbench/components/Inspector.tsx").read_text()
    assert "PermissionConfigurator" in source
    assert "entity_permissions" in source
    assert "添加权限覆盖" in source
    assert "选择权限覆盖字段" in source
    assert "默认权限" in source
    assert "legalPermissionOptions" in source
    assert "移除 ${field} 权限覆盖" in source
    assert "onClick={() => update(type, field, '')}" in source


def test_entity_selector_prioritizes_source_relations() -> None:
    source = Path("frontend/src/features/workbench/components/Inspector.tsx").read_text()
    assert "node.config?.source" in source
    assert "typeof source === 'string' ? [source]" in source
