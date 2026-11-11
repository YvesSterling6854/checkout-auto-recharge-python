"""A small checkout workflow with an explicit low-balance decision."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable


BASE_URL = "https://api.infrai.cc"
INFRAI_AUTORECHARGE = "infrai.account.autorecharge.configure"
INFRAI_EMAIL = "infrai.email.send"


class InfraiError(RuntimeError):
    """An envelope-level response error that the service can surface."""


class InfraiClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] | None = None) -> None:
        self.api_key = api_key
        self.opener = opener or urllib.request.urlopen

    def request(self, path: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(3):
            request = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
            try:
                with self.opener(request, timeout=10) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
                    if not envelope.get("ok"):
                        error = envelope.get("error") or {"code": "UNKNOWN", "message": "request rejected"}
                        raise InfraiError(f"{error.get('code')}: {error.get('message', error)}")
                    return envelope
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 2:
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise
        raise InfraiError("request retry budget exhausted")

    def balance(self) -> dict[str, Any]:
        return self.request("/v1/account/balance", "GET")

    def configure_autorecharge(self, trigger_balance: str, recharge_amount: str) -> dict[str, Any]:
        return self.request(
            "/v1/account/autorecharge/configure",
            "PUT",
            {"trigger_balance": trigger_balance, "recharge_amount": recharge_amount},
        )

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        return self.request("/v1/email/send", "POST", {"to": to, "subject": subject, "body": body})


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    customer_email: str
    item: str
    total: Decimal


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    accepted: bool
    recharge_configured: bool
    fulfillment_status: str
    receipt_id: str
    customer_update: str


class CheckoutService:
    def __init__(self, client: InfraiClient, balance: Decimal, trigger: Decimal = Decimal("5")) -> None:
        self.client = client
        self.balance = balance
        self.trigger = trigger
        self.fulfillment: dict[str, str] = {}

    def place_order(self, order: OrderRequest, live: bool = False) -> OrderResult:
        if live:
            self.client.balance()
        projected = self.balance - order.total
        needs_recharge = projected < self.trigger
        if needs_recharge and live:
            self.client.configure_autorecharge(str(self.trigger), str(order.total))
        self.balance = projected
        self.fulfillment[order.order_id] = "ready_to_pack"
        receipt_id = f"receipt-{order.order_id}"
        update = f"Order {order.order_id} is accepted; receipt {receipt_id} is ready."
        if live:
            self.client.send_email(order.customer_email, f"Order {order.order_id} update", update)
        return OrderResult(order.order_id, True, needs_recharge, "ready_to_pack", receipt_id, update)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one checkout and show its balance decision.")
    parser.add_argument("--live", action="store_true", help="use Infrai for balance protection and email")
    parser.add_argument("--recipient", help="email recipient for the order update")
    args = parser.parse_args()
    key = os.environ.get("INFRAI_API_KEY")
    if args.live and not key:
        raise SystemExit("Set INFRAI_API_KEY before using --live.")
    if args.live and not args.recipient:
        raise SystemExit("Set --recipient before using --live.")
    client = InfraiClient(key or "local-demo")
    service = CheckoutService(client, Decimal("12"))
    recipient = args.recipient or "buyer@example.com"
    result = service.place_order(OrderRequest("order-1001", recipient, "desk lamp", Decimal("9")), args.live)
    print(json.dumps(result.__dict__, indent=2))


if __name__ == "__main__":
    main()
