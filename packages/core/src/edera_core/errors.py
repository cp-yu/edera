class EderaError(Exception):
    """Base exception for application failures."""


class ConfigError(EderaError):
    pass


class ConfigEditError(ConfigError):
    pass


class DatabaseError(EderaError):
    pass


class NodeExecutionError(EderaError):
    pass


class DagError(EderaError):
    pass
