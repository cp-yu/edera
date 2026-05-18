from stockimformation.config.loader import load_app_config
from stockimformation.services.collection import make_fetch_handler


async def run(input_data, parameters, context):
    config = load_app_config()
    handler = make_fetch_handler(config.portfolio, "rss", config.system)
    return await handler(_node_input(input_data, context))


def _node_input(input_data, context):
    from stockimformation.node.models import NodeInput

    return NodeInput(cycle_id=context.cycle_id, payload=input_data)
