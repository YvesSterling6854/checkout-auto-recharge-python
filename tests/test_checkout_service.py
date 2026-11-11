from decimal import Decimal

from src.checkout_service import CheckoutService, InfraiClient, OrderRequest


def test_low_projected_balance_configures_recharge_and_updates_customer() -> None:
    service = CheckoutService(InfraiClient("test-key"), Decimal("12"))

    result = service.place_order(OrderRequest("order-7", "buyer@example.com", "keyboard", Decimal("9")))

    assert result.accepted is True
    assert result.recharge_configured is True
    assert result.fulfillment_status == "ready_to_pack"
    assert result.receipt_id == "receipt-order-7"
    assert "Order order-7 is accepted" in result.customer_update
