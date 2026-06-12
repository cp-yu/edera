"""Condition handler - 读取上游结构化输出并产出条件字段"""


async def run(ctx):
    """
    读取 B 的结构化输出，产出条件字段决定是否执行 D

    Expected input from B: {"continue": bool, "data": str}
    """
    upstream = ctx.input

    # 从上游获取 continue 字段
    should_continue = upstream.get("continue", False)

    return {
        "condition_met": should_continue,
        "upstream_data": upstream.get("data", ""),
        "processed_by": "condition-handler"
    }
