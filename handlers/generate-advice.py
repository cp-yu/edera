from stockimformation.config.loader import load_app_config
from stockimformation.node.models import NodeInput
from stockimformation.services.advisory import make_advice_handler


async def run(input_data, parameters, context):
    config = load_app_config()
    handler = make_advice_handler(config.portfolio)
    return await handler(NodeInput(cycle_id=context.cycle_id, payload=input_data))
