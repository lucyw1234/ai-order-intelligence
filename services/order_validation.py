from models import OrderRequest, OrderResponse


def validate_order(quantity: float, unit_price: float, stated_total: float) -> OrderResponse:
    calculated_total = quantity * unit_price

    if abs(calculated_total - stated_total) < 0.01:
        return OrderResponse(
            id=None,
            valid=True,
            calculated_total=calculated_total,
            error=None
        )
    else:
        return OrderResponse(
            id=None,
            valid=False,
            calculated_total=calculated_total,
            error="Total mismatch"
        )