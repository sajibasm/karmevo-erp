from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, ClassVar

from pydantic import BeforeValidator, PlainSerializer


class Money:
    """Decimal money helpers (PLT-06)."""

    # ISO 4217 minor units for the currencies enabled so far.
    # Add currencies deliberately; never guess.
    MINOR_UNITS: ClassVar[dict[str, int]] = {
        "BDT": 2,
        "USD": 2,
        "EUR": 2,
        "JPY": 0,
        "KWD": 3,
    }

    @classmethod
    def quantize(cls, amount: Decimal, currency: str, rounding: str = ROUND_HALF_UP) -> Decimal:
        """Round to the currency's minor unit.

        Callers pass the rounding mode from the applicable tax or
        pricing policy; the default only keeps the policy visible at
        call sites.
        """
        try:
            places = cls.MINOR_UNITS[currency]
        except KeyError:
            raise ValueError(f"unsupported currency {currency!r}") from None
        return amount.quantize(Decimal(1).scaleb(-places), rounding=rounding)

    @staticmethod
    def reject_float(value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("decimal values must be sent as strings")
        return value


DecimalStr = Annotated[
    Decimal,
    BeforeValidator(Money.reject_float),
    PlainSerializer(str, return_type=str, when_used="json"),
]
