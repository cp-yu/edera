from __future__ import annotations

import argparse

from edera_core.cli._common import _created_range_args, _offset_argument, _time_range_arguments
import edera_core.cli as _cli
from edera_core.cli._common import CommandHelp, _fmt_epilog

HELP = CommandHelp(
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
        "briefing-latest": "Show the latest briefing.",
        "briefing-list": "List briefings with optional time range.",
        "briefing-show": "Show a single briefing by ID.",
        "advice": "Advice projection (subcommands: list, show).",
        "advice-list": "List advice entries with optional filters.",
        "advice-show": "Show a single advice entry by ID.",
        "results": "Results projection (subcommands: summary).",
        "results-summary": "Show aggregated results summary.",
        "node-outputs": "Read node output artifacts with pagination.",
        "node-history": "Read the history of a node within a DAG.",
        "child-run": "List child runs spawned by a parent node.",
    },
)


def add_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest="query_command", required=True)
    sub = HELP.subcommands
    briefing = subparsers.add_parser("briefing", help=sub["briefing"])
    briefing_sub = briefing.add_subparsers(dest="briefing_command", required=True)
    briefing_sub.add_parser("latest", help=sub["briefing-latest"])
    briefing_list = briefing_sub.add_parser("list", help=sub["briefing-list"])
    _time_range_arguments(briefing_list)
    show_briefing = briefing_sub.add_parser("show", help=sub["briefing-show"])
    show_briefing.add_argument("briefing_id", help="Briefing ID.")
    advice = subparsers.add_parser("advice", help=sub["advice"])
    advice_sub = advice.add_subparsers(dest="advice_command", required=True)
    advice_list = advice_sub.add_parser("list", help=sub["advice-list"])
    advice_list.add_argument("--stock-code", default="", help="Filter by stock code.")
    advice_list.add_argument("--direction", default="", help="Filter by advice direction.")
    _time_range_arguments(advice_list)
    show_advice = advice_sub.add_parser("show", help=sub["advice-show"])
    show_advice.add_argument("advice_id", help="Advice ID.")
    results = subparsers.add_parser("results", help=sub["results"])
    results_sub = results.add_subparsers(dest="results_command", required=True)
    summary = results_sub.add_parser("summary", help=sub["results-summary"])
    summary.add_argument("--stock-code", default="", help="Filter by stock code.")
    summary.add_argument("--direction", default="", help="Filter by direction.")
    _created_range_args(summary)
    node_outputs = subparsers.add_parser("node-outputs", help=sub["node-outputs"])
    node_outputs.add_argument("--node-id", default="", help="Node ID.")
    node_outputs.add_argument("--run-id", default="", help="Run ID.")
    node_outputs.add_argument("--limit", type=int, default=100, help="Max results (default: 100).")
    _offset_argument(node_outputs)
    node_history = subparsers.add_parser("node-history", help=sub["node-history"])
    node_history.add_argument("dag_name", help="DAG name.")
    node_history.add_argument("node_id", help="Node reference <dag>.<alias>.")
    node_history.add_argument("--limit", type=int, default=50, help="Max results (default: 50).")
    child_run = subparsers.add_parser("child-run", help=sub["child-run"])
    child_run.add_argument("--parent-run-id", required=True, help="Parent run ID.")
    child_run.add_argument("--parent-node-id", required=True, help="Parent node ID.")


async def dispatch(args: argparse.Namespace) -> object:
    client = _cli.GrpcClient(args.server, identity=args.identity)
    try:
        if args.query_command == "briefing":
            if args.briefing_command == "latest":
                return await client.query_latest_briefing()
            if args.briefing_command == "list":
                return await client.query_list_briefings(args.created_from, args.created_to, args.limit)
            if args.briefing_command == "show":
                return await client.query_get_briefing(args.briefing_id)
        if args.query_command == "advice":
            if args.advice_command == "list":
                return await client.query_list_advices(args.stock_code, args.direction, args.created_from, args.created_to, args.limit)
            if args.advice_command == "show":
                return await client.query_get_advice(args.advice_id)
        if args.query_command == "results":
            if args.results_command == "summary":
                return await client.query_results_summary(args.stock_code, args.direction, args.created_from, args.created_to)
        if args.query_command == "node-outputs":
            return await client.query_node_outputs(args.node_id, args.run_id, args.limit)
        if args.query_command == "node-history":
            return await client.query_node_history(args.dag_name, args.node_id, args.limit)
        if args.query_command == "child-run":
            return await client.query_child_run_for_parent(args.parent_run_id, args.parent_node_id)
    finally:
        await client.close()
    raise ValueError(f"unknown query command: {args.query_command}")
