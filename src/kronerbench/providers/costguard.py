"""Reserve a conservative ceiling before each paid request."""

import asyncio
from decimal import Decimal


class CostCap(RuntimeError):
    pass


class CostGuard:
    def __init__(self, cap: float, spent: float = 0):
        self.cap = Decimal(str(cap))
        self.spent = Decimal(str(spent))
        self.reserved = Decimal(0)
        self.condition = asyncio.Condition()

    async def reserve(self, maximum: Decimal) -> None:
        async with self.condition:
            while self.spent + self.reserved + maximum > self.cap:
                if self.reserved == 0:
                    raise CostCap(
                        f"Cost cap reached: spent {self.spent}; next request can cost {maximum}; cap {self.cap}. Raise --max-cost or resume with fewer trials."
                    )
                await self.condition.wait()
            self.reserved += maximum

    async def settle(self, maximum: Decimal, cost: Decimal) -> None:
        async with self.condition:
            self.reserved -= maximum
            self.spent += cost
            self.condition.notify_all()
            if self.spent > self.cap:
                raise CostCap(
                    "Provider billed more than its advertised request ceiling; run stopped."
                )
