class StockImformationError(Exception):
    """Base exception for application failures."""


class ConfigError(StockImformationError):
    pass


class DatabaseError(StockImformationError):
    pass


class NodeExecutionError(StockImformationError):
    pass


class DagError(StockImformationError):
    pass
