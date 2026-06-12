"""Seed handler - 产出种子输入"""


async def run(ctx):
    """产出种子输入供下游使用"""
    return {
        "seed": "initial_data",
        "timestamp": ctx.input.get("timestamp", "unknown"),
        "source": "seed-handler"
    }
