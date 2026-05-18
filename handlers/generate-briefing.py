from stockimformation.config.loader import load_app_config
from stockimformation.node.models import NodeInput
from stockimformation.services.briefing import make_briefing_handler


async def run(input_data, parameters, context):
    config = load_app_config()
    handler = make_briefing_handler(config.portfolio)
    return await handler(NodeInput(cycle_id=context.cycle_id, payload=input_data))
