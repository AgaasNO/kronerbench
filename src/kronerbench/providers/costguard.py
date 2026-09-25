"""Reserve a conservative ceiling before each paid request."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path


class CostCap(RuntimeError):
    pass


class CostGuard:
    def __init__(self, cap: float, spent: float = 0, ledger: Path | None = None):
        self.cap = Decimal(str(cap))
        self.spent = Decimal(str(spent))
        self.reserved = Decimal(0)
        self.ledger = ledger
        if ledger is not None and ledger.exists():
            saved = json.loads(ledger.read_text())
            # A request outstanding at process death may already have been billed.
            self.spent = max(self.spent, Decimal(saved["spent"]) + Decimal(saved["reserved"]))
        self.condition = asyncio.Condition()

    def persist(self) -> None:
        if self.ledger is not None:
            temporary = self.ledger.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {"spent": str(self.spent), "reserved": str(self.reserved), "cap": str(self.cap)}
                )
                + "\n"
            )
            temporary.replace(self.ledger)

    async def reserve(self, maximum: Decimal) -> None:
        if not maximum.is_finite() or maximum < 0:
            raise ValueError("A reservation must be finite and nonnegative.")
        async with self.condition:
            while self.spent + self.reserved + maximum > self.cap:
                if self.reserved == 0:
                    raise CostCap(
                        f"Cost cap reached: spent {self.spent}; next request can cost {maximum}; cap {self.cap}. Raise --max-cost or resume with fewer trials."
                    )
                await self.condition.wait()
            self.reserved += maximum
            self.persist()

    async def settle(self, maximum: Decimal, cost: Decimal) -> None:
        async with self.condition:
            if maximum > self.reserved or not cost.is_finite() or cost < 0:
                raise ValueError("Invalid cost settlement.")
            self.reserved -= maximum
            self.spent += cost
            self.persist()
            self.condition.notify_all()
            if self.spent > self.cap:
                raise CostCap(
                    "Provider billed more than its advertised request ceiling; run stopped."
                )
