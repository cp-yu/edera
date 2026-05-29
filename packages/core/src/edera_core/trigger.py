from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from edera_core.config.entities import EntityStore
from edera_core.config.schema import EntityConfig
from edera_core.errors import ConfigError
from edera_core.storage.entities import EmitRecord, EventGroupBit


logger = logging.getLogger(__name__)
TriggerTarget = Callable[[str, object | None], Awaitable[object]]


@dataclass(frozen=True)
class TokenExpr:
    value: str


@dataclass(frozen=True)
class BinaryExpr:
    op: str
    left: Expr
    right: Expr


Expr = TokenExpr | BinaryExpr


class TriggerExpressionError(ConfigError):
    pass


class TriggerExpression:
    def __init__(self, text: str) -> None:
        self.text = text
        self.root = _Parser(text).parse()
        self.tokens = sorted(_expr_tokens(self.root))

    def evaluate(self, active: set[str]) -> bool:
        return _eval_expr(self.root, active)

    def matched_tokens(self, active: set[str]) -> set[str]:
        return {token for token in self.tokens if token in active}


class EventGroup:
    def __init__(self, factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.factory = factory
        self.events: set[str] = set()

    async def load(self) -> None:
        if self.factory is None:
            return
        async with self.factory() as session:
            result = await session.exec(select(EventGroupBit.event))
            self.events = set(result.all())

    async def set(self, event: str) -> None:
        if not event:
            raise ConfigError("event must not be blank")
        self.events.add(event)
        if self.factory is None:
            return
        async with self.factory() as session:
            bit = await session.exec(select(EventGroupBit).where(EventGroupBit.event == event))
            if bit.first() is None:
                session.add(EventGroupBit(event=event))
            await session.commit()

    async def clear(self, event: str) -> None:
        self.events.discard(event)
        if self.factory is None:
            return
        async with self.factory() as session:
            bit = await session.exec(select(EventGroupBit).where(EventGroupBit.event == event))
            current = bit.first()
            if current is not None:
                await session.delete(current)
            await session.commit()

    async def consume(self, tokens: Iterable[str]) -> None:
        for token in tokens:
            await self.clear(token)


@dataclass
class CronEmitter:
    executor: TriggerExecutor
    emitted_minutes: set[tuple[str, datetime]] = field(default_factory=set)

    def cron_tokens(self) -> set[str]:
        return {token for token in self.executor.reverse_index() if token.startswith('cron:"')}

    async def tick(self, now: datetime | None = None) -> list[str]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(second=0, microsecond=0)
        fired: list[str] = []
        for token in sorted(self.cron_tokens()):
            key = (token, current)
            if key in self.emitted_minutes or not _cron_matches(_cron_value(token), current):
                continue
            self.emitted_minutes.add(key)
            await self.executor.emit(token, source="cron")
            fired.append(token)
        return fired


@dataclass
class TriggerExecutor:
    store: EntityStore
    run_dag: TriggerTarget | None = None
    run_node: TriggerTarget | None = None
    factory: async_sessionmaker[AsyncSession] | None = None
    max_depth: int = 3
    events: EventGroup = field(init=False)
    records: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.events = EventGroup(self.factory)
        if self.run_dag is not None:
            self.run_dag = _payload_adapter(self.run_dag)
        if self.run_node is not None:
            self.run_node = _payload_adapter(self.run_node)

    async def load(self) -> None:
        await self.events.load()

    def triggers(self) -> list[EntityConfig]:
        return self.store.query("trigger")

    def reverse_index(self) -> dict[str, list[EntityConfig]]:
        index: dict[str, list[EntityConfig]] = {}
        for trigger in self.triggers():
            expr = _trigger_expression(trigger)
            if expr is None:
                continue
            for token in expr.tokens:
                index.setdefault(token, []).append(trigger)
        return index

    async def emit(
        self,
        event: str,
        payload: object | None = None,
        *,
        source: str = "rpc",
        depth: int = 0,
    ) -> list[str]:
        if depth >= self.max_depth:
            logger.warning("trigger emit depth exceeded: event=%s depth=%s", event, depth)
            raise ConfigError("max trigger depth exceeded")
        await self._record_emit(event, payload, source, depth)
        if event.startswith("manual:"):
            target = _manual_target(event)
            await self.fire(target, payload, depth + 1)
            return [target]
        if event.startswith("clear:"):
            await self.events.clear(event.removeprefix("clear:"))
            return []
        await self.events.set(event)
        fired: list[str] = []
        for trigger in self._affected_triggers(event):
            if trigger.attributes.get("enabled", True) is False:
                continue
            expr = _trigger_expression(trigger)
            if expr is None or not expr.evaluate(self.events.events):
                continue
            target = str(trigger.attributes.get("target", ""))
            await self.fire(target, payload, depth + 1)
            fired.append(target)
            await self.events.consume(expr.matched_tokens(self.events.events))
            if _is_oneshot(expr.tokens):
                self._disable_trigger(trigger)
        return fired

    async def fire(self, target: str, payload: object | None = None, depth: int = 0) -> None:
        if target.startswith("clear:"):
            await self.events.clear(target.removeprefix("clear:"))
            return
        if target.startswith("dag:") and self.run_dag is not None:
            await self.run_dag(target.removeprefix("dag:"), payload)
            return
        if target.startswith("node:") and self.run_node is not None:
            await self.run_node(target.removeprefix("node:"), payload)
            return
        raise ConfigError(f"unsupported trigger target: {target}")

    def entity_changed(self, ref: str) -> str:
        return f"event:entity-changed:{ref}"

    def config_changed(self) -> str:
        return "event:config-changed"

    def schedule_event(self, cron_value: str) -> str:
        return f'cron:"{cron_value}"'

    def node_output_event(self, name: str) -> str:
        return f"event:{name}"

    def _affected_triggers(self, event: str) -> list[EntityConfig]:
        return self.reverse_index().get(event, [])

    async def _record_emit(self, event: str, payload: object | None, source: str, depth: int) -> None:
        now = datetime.now(timezone.utc)
        record = {
            "event": event,
            "payload": payload,
            "source": source,
            "depth": depth,
            "created_at": now.isoformat(),
        }
        self.records.append(record)
        if self.factory is None:
            return
        async with self.factory() as session:
            session.add(
                EmitRecord(
                    event=event,
                    payload=payload,
                    source=source,
                    depth=depth,
                    created_at=now,
                )
            )
            await session.commit()

    def _disable_trigger(self, trigger: EntityConfig) -> None:
        updated = trigger.model_copy(update={"attributes": {**trigger.attributes, "enabled": False}})
        self.store.save(updated)


def parse_trigger_expression(text: str) -> TriggerExpression:
    return TriggerExpression(text)


def _payload_adapter(target):
    async def wrapped(name: str, payload: object | None) -> object:
        try:
            return await target(name, payload)
        except TypeError:
            return await target(name)

    return wrapped


def _trigger_expression(trigger: EntityConfig) -> TriggerExpression | None:
    wait_for = trigger.attributes.get("wait_for")
    if not isinstance(wait_for, str) or not wait_for.strip():
        return None
    return TriggerExpression(wait_for)


def _manual_target(event: str) -> str:
    parts = event.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"dag", "node"} or not parts[2]:
        raise ConfigError(f"unsupported manual trigger event: {event}")
    return f"{parts[1]}:{parts[2]}"


def _is_oneshot(tokens: Iterable[str]) -> bool:
    return any(token.startswith('cron:"') and _cron_value(token).split()[2:5] != ["*", "*", "*"] for token in tokens)


def _cron_value(token: str) -> str:
    return token.removeprefix('cron:"').removesuffix('"')


def _cron_matches(cron: str, now: datetime) -> bool:
    fields = cron.split()
    if len(fields) != 5:
        raise TriggerExpressionError("cron token must contain five fields")
    values = [now.minute, now.hour, now.day, now.month, now.weekday()]
    return all(_cron_field_matches(field, value, index) for index, (field, value) in enumerate(zip(fields, values, strict=True)))


def _cron_field_matches(field: str, value: int, index: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return step > 0 and value % step == 0
    if "," in field:
        return any(_cron_field_matches(part, value, index) for part in field.split(","))
    if "-" in field:
        start, end = [int(part) for part in field.split("-", 1)]
        return start <= value <= end
    expected = int(field)
    if index == 4 and expected == 7:
        expected = 6
    return value == expected


def _expr_tokens(expr: Expr) -> set[str]:
    if isinstance(expr, TokenExpr):
        return {expr.value}
    return _expr_tokens(expr.left) | _expr_tokens(expr.right)


def _eval_expr(expr: Expr, active: set[str]) -> bool:
    if isinstance(expr, TokenExpr):
        return expr.value in active
    if expr.op == "AND":
        return _eval_expr(expr.left, active) and _eval_expr(expr.right, active)
    return _eval_expr(expr.left, active) or _eval_expr(expr.right, active)


@dataclass(frozen=True)
class _LexToken:
    kind: str
    value: str


class _Parser:
    def __init__(self, text: str) -> None:
        self.tokens = _lex(text)
        self.index = 0

    def parse(self) -> Expr:
        expr = self._or()
        if self._peek() is not None:
            raise TriggerExpressionError("unexpected token")
        return expr

    def _or(self) -> Expr:
        expr = self._and()
        while self._match("OR"):
            expr = BinaryExpr("OR", expr, self._and())
        return expr

    def _and(self) -> Expr:
        expr = self._primary()
        while self._match("AND"):
            expr = BinaryExpr("AND", expr, self._primary())
        return expr

    def _primary(self) -> Expr:
        if self._match("("):
            expr = self._or()
            if not self._match(")"):
                raise TriggerExpressionError("missing closing parenthesis")
            return expr
        token = self._consume("TOKEN")
        return TokenExpr(token.value)

    def _peek(self) -> _LexToken | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _match(self, kind: str) -> bool:
        if self._peek() is None or self._peek().kind != kind:
            return False
        self.index += 1
        return True

    def _consume(self, kind: str) -> _LexToken:
        token = self._peek()
        if token is None or token.kind != kind:
            raise TriggerExpressionError(f"expected {kind}")
        self.index += 1
        return token


def _lex(text: str) -> list[_LexToken]:
    tokens: list[_LexToken] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "()":
            tokens.append(_LexToken(char, char))
            index += 1
            continue
        end = index
        quoted = False
        while end < len(text) and not text[end].isspace() and text[end] not in "()":
            if text[end] == '"':
                quoted = not quoted
                end += 1
                while end < len(text):
                    if text[end] == '"':
                        quoted = not quoted
                        end += 1
                        break
                    end += 1
                continue
            end += 1
        if quoted:
            raise TriggerExpressionError("unterminated quote")
        value = text[index:end]
        upper = value.upper()
        if upper in {"AND", "OR"}:
            tokens.append(_LexToken(upper, upper))
        else:
            _validate_token(value)
            tokens.append(_LexToken("TOKEN", value))
        index = end
    if not tokens:
        raise TriggerExpressionError("expression must not be blank")
    return tokens


def _validate_token(value: str) -> None:
    if value.startswith("manual:"):
        raise TriggerExpressionError("manual prefix is reserved for emit")
    if value.startswith("cron:"):
        if not (value.startswith('cron:"') and value.endswith('"')):
            raise TriggerExpressionError("cron token must be quoted")
        cron = _cron_value(value)
        if len(cron.split()) != 5:
            raise TriggerExpressionError("cron token must contain five fields")
    if '"' in value and not (value.startswith('cron:"') and value.endswith('"')):
        try:
            json.loads(value.split(":", 1)[1])
        except Exception as exc:
            raise TriggerExpressionError("invalid quoted token") from exc
