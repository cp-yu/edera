from __future__ import annotations

from edera_core.config.schema import EntityTypeConfig
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.storage.repository._helpers import (
    CORE_ENTITY_TABLES,
    DeleteEntityResult,
    _entity_exists,
    entity_type_record_to_config,
)
from edera_core.storage.repository._entity_type import (
    count_entities_for_type,
    delete_entity_type_record,
    get_entity_type_config,
    list_entity_type_configs,
    seed_entity_type_records,
    upsert_entity_type_record,
)
from edera_core.storage.repository._core_entity import (
    core_dag_to_entity,
    core_input_mapping_to_entity,
    core_node_to_entity,
    core_resource_to_entity,
    core_trigger_to_entity,
    delete_core_entity,
    get_core_entity,
    get_dag_config,
    get_dag_entity,
    get_node_config,
    list_core_entities,
    list_dag_configs,
    list_dag_names,
    list_node_configs,
    list_node_summaries,
    save_core_entity,
)
from edera_core.storage.repository._ordinary import (
    create_ordinary_entity,
    delete_ordinary_entity,
    find_ordinary_entity,
    get_ordinary_entity,
    list_ordinary_entities,
    query_ordinary_entities,
    save_ordinary_entity,
    update_ordinary_entity,
)
from edera_core.storage.repository._relation import (
    create_relation,
    delete_relation,
    force_delete_entity_relations,
    list_relations,
    list_relations_for_entity,
    list_relations_for_entity_refs,
)
from edera_core.storage.repository._skill import (
    create_skill,
    delete_skill,
    get_skill,
    list_skill_configs,
    list_skills,
    skill_to_config,
    update_skill,
    upsert_skill,
)
from edera_core.storage.repository._extension import (
    delete_installed_extension,
    get_installed_extension,
    list_enabled_extensions,
    list_installed_extensions,
    save_installed_extension,
)
from edera_core.storage.repository._log_index import (
    query_log_index,
    record_log_index,
)
from edera_core.storage.repository._runtime import (
    analyses_for_advice,
    cleanup_node_output_entities,
    create_dag_run,
    current_dag_run,
    delete_node_output_entity,
    delete_node_outputs_for_nodes,
    edge_inputs_for_run,
    event_evidence_details,
    event_records_for_advices,
    finish_dag_run,
    get_advice,
    get_briefing,
    get_dag_run,
    latest_briefing,
    latest_finished_dag_run,
    list_advices,
    list_briefings,
    list_event_records,
    mark_node_run,
    node_output_to_entity,
    node_run_for_run_node,
    node_runs_for_run,
    query_node_output_entities,
    raw_items_for_analyses,
    recent_dag_runs,
    restart_dag_run,
    save_node_output_entity,
    source_execution_logs,
    source_health_summary,
    source_recoveries,
    store_node_output_entities,
    upsert_edge_input,
    upsert_source_recovery,
)


async def entity_exists(
    session: AsyncSession,
    ref: str,
    entity_types: dict[str, EntityTypeConfig],
) -> bool:
    from edera_core.storage.repository._core_entity import get_core_entity
    from edera_core.storage.repository._ordinary import find_ordinary_entity
    return await _entity_exists(
        session, ref, entity_types,
        get_core_entity_fn=get_core_entity,
        find_ordinary_entity_fn=find_ordinary_entity,
    )
