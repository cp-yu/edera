"""Help text catalog for the `edera` CLI.

Keeps argparse kwargs (`description`, `epilog`, `help`) separate from
`cli.py` so the command registration stays readable.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandHelp:
    description: str
    help_line: str
    epilog: str
    subcommands: dict[str, str] = field(default_factory=dict)


def _fmt_epilog(description: str, examples: list[tuple[str, str]]) -> str:
    header = description.strip()
    lines = ["EXAMPLES"]
    for invocation, note in examples:
        lines.append(f"  {invocation}")
        if note:
            lines.append(f"    # {note}")
    return header + "\n\n" + "\n".join(lines)


TOP_DESCRIPTION = textwrap.dedent(
    """\
    Edera CLI — the unified entry point to the Edera control plane
    (Entity 原语 + DAG 执行模型的编排内核).

    Connects to a running `edera-server` over gRPC + mTLS and exposes
    every control capability (entities, DAGs, events, skills, ...).
    """
).strip()

TOP_EPILOG = _fmt_epilog(
    "Environment variables override defaults for connection and identity.",
    [
        ("edera entity list --type document", "list entities filtered by type"),
        ("edera entity get doc-42 --output table", "render one entity as a table"),
        ("EDERA_SERVER_ADDR=server.lan:9090 edera dag run my-dag", "run a DAG against a remote server"),
        ("EDERA_IDENTITY=node:llm-analyze edera entity get stock:AAPL", "act as a specific node identity"),
    ],
)


_COMMAND_HELP: dict[str, CommandHelp] = {
    "entity": CommandHelp(
        description="Manage entities (实体管理): the unified primitive of the kernel.",
        help_line="Manage entities (实体管理)",
        epilog=_fmt_epilog(
            "An entity is identified by `<type>:<id>` and stores typed attributes.",
            [
                ("edera entity create --type document --attributes title=\"Hello\"", "create a new entity"),
                ("edera entity list --type document --filter 'status=active'", "list with filters"),
                ("edera entity get stock:AAPL --output table", "render as a table"),
                ("edera entity import ./entities.yaml", "bulk import from YAML"),
            ],
        ),
        subcommands={
            "get": "Show a single entity by ref.",
            "show": "Show a single entity (alias of get).",
            "create": "Create a new entity.",
            "import": "Import entities from a YAML/JSON file.",
            "export": "Export a single entity to a file.",
            "template": "Emit a starter template for a given type.",
            "list": "List entities, optionally filtered.",
            "update": "Patch one field or full attributes on an entity.",
            "query": "Run an inline query expression against entities.",
            "delete": "Delete an entity (--force to bypass checks).",
        },
    ),
    "relation": CommandHelp(
        description="Manage relations (关系) between entities.",
        help_line="Manage entity relations (关系)",
        epilog=_fmt_epilog(
            "A relation links two entities with a type and optional metadata.",
            [
                ("edera relation create --from stock:AAPL --to sector:tech --type belongs_to", "create a relation"),
                ("edera relation list --from stock:AAPL", "list outgoing relations"),
            ],
        ),
        subcommands={
            "list": "List relations, optionally filtered by endpoint or type.",
            "create": "Create a new typed relation between two entities.",
            "delete": "Delete a relation by id.",
            "import": "Import relations from a YAML/JSON file.",
            "export": "Export all relations to a file.",
        },
    ),
    "entity-type": CommandHelp(
        description="Inspect and materialize entity-type schemas (实体类型).",
        help_line="Manage entity-type schemas (实体类型)",
        epilog=_fmt_epilog(
            "Entity types describe attribute schemas; materialize promotes a field to a typed column.",
            [
                ("edera entity-type materialize plan stock --field sentiment --type string", "preview materialization"),
                ("edera entity-type materialize apply stock --field sentiment --type string", "apply materialization"),
                ("edera entity-type materialize inspect stock", "inspect current materialization state"),
            ],
        ),
        subcommands={
            "materialize": "Promote a field into a typed, indexed column (subcommands: plan, apply, inspect).",
        },
    ),
    "node": CommandHelp(
        description="Operate on DAG node instances (节点实例) during a run.",
        help_line="Operate on DAG node instances (节点)",
        epilog=_fmt_epilog(
            "Node subcommands act on a single node instance within a DAG run.",
            [
                ("edera node status my-dag.node-1", "show runtime status"),
                ("edera node resume my-dag.node-1 --prompt retry", "resume a paused node"),
                ("edera node logs my-dag.node-1 --run-id r-001 --tail", "tail node logs"),
            ],
        ),
        subcommands={
            "status": "Show runtime status of a node instance.",
            "stop": "Stop a node instance.",
            "resume": "Resume a paused node instance with an optional prompt.",
            "output": "Read or write a node's output artifact.",
            "logs": "Read node logs (--tail to follow).",
        },
    ),
    "node-type": CommandHelp(
        description="Manage node-type definitions (节点类型).",
        help_line="Manage node-type definitions (节点类型)",
        epilog=_fmt_epilog(
            "Node types are registered from YAML definitions and referenced by DAG nodes.",
            [
                ("edera node-type list", "list registered node types"),
                ("edera node-type create llm-analyze --file ./node-types/llm-analyze.yaml", "register a node type"),
                ("edera node-type delete llm-analyze", "remove a node type"),
            ],
        ),
        subcommands={
            "list": "List registered node types.",
            "show": "Show a single node type by name.",
            "create": "Register a node type from a YAML file.",
            "save": "Replace a node type from a YAML file.",
            "delete": "Delete a node type by name.",
        },
    ),
    "skill": CommandHelp(
        description="Manage the skill registry (技能).",
        help_line="Manage skills (技能)",
        epilog=_fmt_epilog(
            "A skill bundles a YAML manifest plus handler assets, importable from a directory.",
            [
                ("edera skill list", "list installed skills"),
                ("edera skill import-dir ./skills/my-skill", "register a skill from a directory"),
                ("edera skill export my-skill -o ./out", "export a skill to a directory"),
            ],
        ),
        subcommands={
            "list": "List installed skills.",
            "show": "Show a single skill by name.",
            "create": "Register a skill from a source directory.",
            "update": "Replace an existing skill from a source directory.",
            "import-dir": "Register a skill from a directory (alias of create).",
            "import-batch": "Register multiple skills from a parent directory.",
            "export": "Export a skill to an output directory.",
            "delete": "Delete a skill by name.",
        },
    ),
    "dag": CommandHelp(
        description="Submit, watch, edit and inspect DAG runs (DAG 运行).",
        help_line="Submit and inspect DAG runs (DAG)",
        epilog=_fmt_epilog(
            "A DAG is the unit of execution; edit subcommands mutate a saved DAG definition.",
            [
                ("edera dag run my-dag", "start a new run"),
                ("edera dag status my-dag --watch", "watch run status"),
                ("edera dag retry my-dag --nodes node-1", "retry specific nodes"),
                ("edera dag edit my-dag add-node --type llm-analyze --alias n2", "mutate definition"),
            ],
        ),
        subcommands={
            "list": "List saved DAG definitions.",
            "show": "Show a saved DAG definition.",
            "create": "Create an empty DAG definition.",
            "save": "Replace a DAG definition from a YAML file.",
            "import": "Import a DAG definition from a YAML file (alias of save).",
            "export": "Export a DAG definition to a YAML file.",
            "runtime-status": "Show runtime status of one or all runs (--watch).",
            "run": "Start a new DAG run with optional input overrides.",
            "status": "Show status of the latest or a specific run (--watch).",
            "stop": "Stop a running DAG.",
            "retry": "Retry failed nodes of a DAG run.",
            "edit": "Edit a saved DAG definition (subcommands: add-node, add-edge, remove-edge).",
        },
    ),
    "event": CommandHelp(
        description="Emit events into the event stream (事件).",
        help_line="Emit events into the stream (事件)",
        epilog=_fmt_epilog(
            "Events trigger registered handlers; payload is JSON.",
            [
                ("edera event emit my.event --payload-json '{\"k\":1}'", "emit a typed event"),
            ],
        ),
        subcommands={
            "emit": "Emit a typed event with optional payload and source.",
        },
    ),
    "system": CommandHelp(
        description="Inspect and control server runtime state (系统).",
        help_line="Control server runtime (系统)",
        epilog=_fmt_epilog(
            "System subcommands control the scheduler and repair sources.",
            [
                ("edera system scheduler-status", "show scheduler status"),
                ("edera system pause-scheduler", "pause the scheduler"),
                ("edera system repair-source my-source", "repair a stalled source"),
            ],
        ),
        subcommands={
            "pause-scheduler": "Pause the global scheduler.",
            "resume-scheduler": "Resume the global scheduler.",
            "scheduler-status": "Show scheduler status (--watch).",
            "repair-source": "Trigger repair for a specific source.",
        },
    ),
    "client": CommandHelp(
        description="Manage the local client identity and certificates (客户端).",
        help_line="Manage client identity/certs (客户端)",
        epilog=_fmt_epilog(
            "client init runs against the server bootstrap port to mint a client certificate.",
            [
                ("edera client init --server 127.0.0.1:9091", "bootstrap a client cert over the bootstrap port"),
            ],
        ),
        subcommands={
            "init": "Bootstrap the local client against a server bootstrap port.",
        },
    ),
    "config": CommandHelp(
        description="Inspect and edit effective configuration (配置).",
        help_line="Inspect and edit configuration (配置)",
        epilog=_fmt_epilog(
            "Config subcommands cover system config, named configs, and entity-type schemas managed via config.",
            [
                ("edera config list", "list top-level config kinds"),
                ("edera config system show", "show system.toml"),
                ("edera config save source my-src --file ./src.yaml", "save a named config from a file"),
                ("edera config entity-type create stock --file ./stock.yaml", "register an entity-type schema via config"),
            ],
        ),
        subcommands={
            "list": "List available config kinds.",
            "system": "Inspect or save system.toml (subcommands: show, save).",
            "read": "Read a named config item.",
            "save": "Save a named config from a file.",
            "entity-type": "Manage entity-type schemas via config (subcommands: list, show, create, save, delete).",
        },
    ),
    "query": CommandHelp(
        description="Run ad-hoc queries over briefing/advice/results (查询).",
        help_line="Query briefings, advice, results (查询)",
        epilog=_fmt_epilog(
            "Query subcommands expose the read-side projections of the kernel.",
            [
                ("edera query briefing latest", "show the latest briefing"),
                ("edera query advice list --stock-code AAPL", "list advice for a stock"),
                ("edera query results summary --direction bullish", "aggregate results by direction"),
                ("edera query node-outputs --node-id n1 --run-id r1", "read node outputs"),
            ],
        ),
        subcommands={
            "briefing": "Briefing projection (subcommands: latest, list, show).",
            "advice": "Advice projection (subcommands: list, show).",
            "results": "Results projection (subcommands: summary).",
            "node-outputs": "Read node output artifacts with pagination.",
            "node-history": "Read the history of a node within a DAG.",
            "child-run": "List child runs spawned by a parent node.",
        },
    ),
    "source": CommandHelp(
        description="Inspect information-source health and logs (信息源).",
        help_line="Inspect info sources (信息源)",
        epilog=_fmt_epilog(
            "Source subcommands expose runtime diagnostics for information sources.",
            [
                ("edera source health", "watch source health"),
                ("edera source logs --source-name minimax-docs --tail", "tail a source's logs"),
                ("edera source repair-task minimax-docs", "repair a single source task"),
            ],
        ),
        subcommands={
            "health": "Show source health (--watch).",
            "logs": "Read source logs with pagination and optional --tail.",
            "repair-task": "Repair a single source task by source name.",
        },
    ),
    "handler": CommandHelp(
        description="Manage event handlers (处理器).",
        help_line="Manage event handlers (处理器)",
        epilog=_fmt_epilog(
            "Handlers are named, versioned modules invoked by the event bus.",
            [
                ("edera handler list", "list registered handlers"),
                ("edera handler show my-handler", "show one handler"),
                ("edera handler save my-handler --file ./handler.yaml", "save a handler"),
            ],
        ),
        subcommands={
            "list": "List registered handlers.",
            "show": "Show a single handler by name.",
            "save": "Save a handler definition from a YAML file.",
        },
    ),
    "extension": CommandHelp(
        description="Manage installed extensions (扩展).",
        help_line="Manage extensions (扩展)",
        epilog=_fmt_epilog(
            "Extensions package handlers, entity-types and skills; install/uninstall drive lifecycle.",
            [
                ("edera extension list --installed", "list installed extensions"),
                ("edera extension install my-ext", "install an extension"),
                ("edera extension uninstall my-ext --strategy purge", "fully remove an extension"),
                ("edera extension import ./my-ext --install", "import and install from a path"),
            ],
        ),
        subcommands={
            "list": "List available or installed extensions.",
            "show": "Show a single extension by name.",
            "install": "Install an extension by name.",
            "delete": "Delete an installed extension (alias of uninstall --strategy deactivate).",
            "uninstall": "Uninstall with a strategy (purge | keep-modified | deactivate).",
            "reactivate": "Reactivate a previously deactivated extension.",
            "import": "Import an extension from a path (optionally --install).",
            "export": "Export an extension to an archive.",
            "import-entities": "Import entities bundled in an extension.",
            "export-entities": "Export entities into an extension archive.",
        },
    ),
    "handler-validate": CommandHelp(
        description="Validate a handler module on disk without contacting the server.",
        help_line="Validate a handler module (offline)",
        epilog=_fmt_epilog(
            "Runs schema validation directly against a handler file; does not need a running server.",
            [
                ("edera handler-validate ./handlers/my-handler.yaml", "validate a handler definition"),
            ],
        ),
        subcommands={},
    ),
}


COMMANDS: dict[str, CommandHelp] = _COMMAND_HELP
