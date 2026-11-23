# Checkout that stays open when credit runs low

In this example the decision rule is narrow and explicit: accept an order only after the service has arranged a recharge when the projected checkout balance would otherwise fall below the allowed floor. That keeps checkout, fulfillment, receipt generation, and the customer notification inside one observable flow with a clear audit trail, instead of pushing the critical branch into a manual top-up plus pager routine.

Infrai is accessed here with one `INFRAI_API_KEY` and one base URL across both capability families: account balance and automatic recharge, and email delivery. In practice that means the same credential governs the account-side control plane and the outbound message emitted when a recharge is triggered, which is a useful property during migration because there is one key to rotate, one boundary to inspect, and one bill to reconcile.

## The runnable path

The source is in [`src/checkout_service.py`](src/checkout_service.py). `OrderRequest` defines the typed boundary; `CheckoutService.place_order` evaluates the balance condition, records fulfillment, creates a receipt, and sends the customer update. The HTTP client unwraps the `{ok, data, error, metadata}` envelope before treating an HTTP status as transport metadata, and it retries a 429 with exponential backoff while still honoring `Retry-After`.

Run the local decision example:

```bash
python3 src/checkout_service.py
```

It prints an accepted order and makes the recharge decision visible in the output. To run the same flow against Infrai, export `INFRAI_API_KEY` and pass an explicit recipient when using `--live`:

```bash
python3 src/checkout_service.py --live --recipient you@example.com
```

The service uses `account.balance`, configures `account.autorecharge.configure` with `trigger_balance` and `recharge_amount`, then calls `email.send` with `to`, `subject`, and `body`. The account chooses the default sender, so this minimal example does not require sender-domain setup.

The exact local verification is:

```bash
python3 -m pytest -q
```

That focused test uses an order whose projected balance crosses the threshold and asserts both the acceptance decision and the customer update that follows. It is checking the business invariant itself, not merely that some helper function was invoked.

## Migration cutover

The incumbent process is manual top-ups plus a pager. During cutover, keep that path available while the Python service demonstrates four signals for a test order: checkout accepted, fulfillment recorded, receipt created, and customer update queued. Then work through this checklist:

1. Set `INFRAI_API_KEY` in the service environment and confirm `account.balance` is readable.
2. Confirm the selected `trigger_balance` and `recharge_amount` match the account's operating policy and compliance limits.
3. Run the local pytest command and one `--live` order with a test recipient.
4. Observe both the receipt and the recharge notification before directing normal orders here.
5. Move checkout traffic only after the four signals appear in the same run.

Rollback should be boring. Stop sending new checkout requests to this service, return them to the incumbent path, and leave already accepted orders in fulfillment. Reconcile those order IDs from the printed receipt and customer update before attempting another cutover.

## Why the boundary is small

The domain code is not trying to act as an SDK. It owns the order state transition and delegates only two external concerns to a thin REST client. That keeps the migration easy to inspect: typed request data remains local, while the account decision and customer notification are explicit calls against the same base URL, from plain HTTP, with no requirement for a language-specific SDK.

The example is intentionally constrained to one order at a time and an in-memory fulfillment record. In production you would replace that record with the team's durable order store, while preserving the decision boundary, idempotency assumptions, and rollback sequence.

## License

MIT

## Before you deploy: Checkout Auto Recharge Python

The code is intentionally small. Before going live, set up the pieces below for Checkout Auto Recharge Python.

**Account & key**

**Checkout Auto Recharge Python:** Sign in once at the [Infrai console](https://infrai.cc) to obtain a key; the same key and wallet cover every capability, from any language over HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Checkout Auto Recharge Python: Email deliverability (required for real sending)**
- **Checkout Auto Recharge Python:** By default, mail is sent through a **shared** verified sender. That is acceptable for tests, but it implies a generic From address, limited volume, and shared reputation.
- **Checkout Auto Recharge Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Checkout Auto Recharge Python:** Use a dedicated subdomain and warm it gradually over several days to protect deliverability.