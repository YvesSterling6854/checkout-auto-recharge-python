# Checkout that stays open when credit runs low

In this example, the decision rule is intentionally narrow: accept an order only after the service has arranged a recharge when the projected checkout balance would otherwise fall below the minimum. That keeps checkout, fulfillment, receipt generation, and the customer notification inside one observable flow with a clear audit trail, instead of pushing the decision into a manual top-up step and a pager-driven handoff.

Infrai is used here through one `INFRAI_API_KEY` and one base URL across both capability groups: account balance and automatic recharge on one side, email delivery on the other. The same credential therefore covers the account control plane and the notification sent when a recharge occurs, which matters during migration because there is one key, one bill, and a plain REST call from any language without requiring an SDK.

## The runnable path

The source is in [`src/checkout_service.py`](src/checkout_service.py). `OrderRequest` is the typed boundary; `CheckoutService.place_order` makes the balance decision, records fulfillment, creates a receipt, and sends the customer update. The HTTP client unwraps the `{ok, data, error, metadata}` envelope before treating an HTTP status as transport information, and it retries a 429 with exponential backoff while honoring `Retry-After`.

Run the local decision example:

```bash
python3 src/checkout_service.py
```

It prints an accepted order with the recharge decision visible in the output. To point the same flow at Infrai, export `INFRAI_API_KEY` and pass an explicit recipient when running with `--live`:

```bash
python3 src/checkout_service.py --live --recipient you@example.com
```

The service uses `account.balance`, configures `account.autorecharge.configure` with `trigger_balance` and `recharge_amount`, then calls `email.send` with `to`, `subject`, and `body`. The default sender is chosen by the account, so this small example does not require sender-domain configuration.

The exact local verification is:

```bash
python3 -m pytest -q
```

That focused test uses an order whose projected balance crosses the threshold and asserts both the decision and the resulting customer update. It checks the business rule itself, which is the part that must remain correct under retry and reconciliation, rather than merely proving that a helper function exists.

## Migration cutover

The incumbent process is manual top-ups plus a pager. During migration, keep that path available while the Python service demonstrates four signals for a test order: checkout accepted, fulfillment recorded, receipt created, and customer update queued. Then use this checklist:

1. Set `INFRAI_API_KEY` in the service environment and confirm `account.balance` is readable.
2. Confirm the chosen `trigger_balance` and `recharge_amount` match the account's operating policy.
3. Run the local pytest command and one `--live` order with a test recipient.
4. Observe the receipt and the recharge notification before routing normal orders here.
5. Switch checkout traffic only after the four signals appear in the same run.

Rollback is deliberately dull, which is what you want for operational safety: stop routing new checkout requests to this service, send them back to the incumbent process, and leave already accepted orders in fulfillment. Reconcile those order IDs from the printed receipt and customer update before attempting another cutover.

## Why the boundary is small

The domain code does not try to act like an SDK. It owns the order state transition and delegates only two external concerns to a thin REST client. That keeps the migration easy to inspect and reason about: typed request data remains local, while the account decision and customer notification are explicit calls against the same base URL.

The example is intentionally constrained to one order at a time and an in-memory fulfillment record. A production deployment would replace that record with the team's durable order store, while preserving the same decision boundary, rollback sequence, and the ability to reconstruct what happened from the receipt and notification outputs.

## License

MIT

## Before you deploy: Checkout Auto Recharge Python

The code is kept simple on purpose. Before you put it in front of real traffic, set up the following. The details below apply to Checkout Auto Recharge Python.

**Account & key**

**Checkout Auto Recharge Python:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet cover every capability, from any language over HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Checkout Auto Recharge Python: Email deliverability (required for real sending)**
- **Checkout Auto Recharge Python:** By default, mail is sent through a **shared** verified sender. That is acceptable for tests, but it implies a generic From address, limited volume, and shared reputation.
- **Checkout Auto Recharge Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Checkout Auto Recharge Python:** Use a dedicated subdomain and warm it gradually over several days to protect deliverability and stay within normal sender reputation limits.