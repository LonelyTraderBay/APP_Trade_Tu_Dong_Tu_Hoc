"""T033 — BrokerHubController: cert-gated enable, fail-closed switch (no Qt).

Mirrors `tests/unit/test_tray_controller.py`'s pattern: pure `migrated_uow`
fixture, no PySide6 import anywhere in this file. Never touches real
network/ccxt — `FakeCcxtExchange` only, injected via `exchange_factory`.

`fake_keyring` (autouse) mirrors `test_settings_controller.py`'s in-memory
`FakeKeyring` stand-in. It has to be autouse here — unlike Settings, every
`BrokerHubController.snapshot()` call (used by nearly every test below, via
`_render`-equivalent assertions or indirectly) now calls
`demo_credentials_configured()`, which reads the keyring. Before this task
`test_broker_hub_controller.py` never touched keyring/`persistence.secrets`
at all; this fixture keeps this suite hitting only an in-memory fake instead
of a real OS credential store (portability for headless CI).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from autotrade.app_ui.controllers.broker_hub import (
    DEFAULT_PAPER_ACCOUNT_ID,
    BrokerHubController,
)
from autotrade.app_ui.services.broker_hub import build_broker_hub_state
from autotrade.core.adapters.ccxt_demo.adapter import FakeCcxtExchange
from autotrade.core.domain.allowlist import D1B_ALLOWLIST
from autotrade.core.oms.fsm import IntentState
from autotrade.persistence.models import (
    Account,
    AccountSecretsRef,
    CertificationRecord,
    OrderIntent,
    ReconBreak,
)
from autotrade.persistence.uow import UnitOfWork

from .test_settings_controller import FakeKeyring

DEMO_ACCOUNT_ID = "demo-binance"


@pytest.fixture(autouse=True)
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr("autotrade.persistence.secrets.keyring", fake)
    return fake


def _seed_paper_active(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEFAULT_PAPER_ACCOUNT_ID,
                adapter_id="paper",
                mode="PAPER",
                status="READY",
                eligibility="PAPER",
                is_active=True,
            )
        )


def _seed_demo_ready(uow: UnitOfWork, *, is_active: bool = False) -> None:
    with uow.session() as session:
        session.add(
            Account(
                account_id=DEMO_ACCOUNT_ID,
                adapter_id="ccxt",
                mode="DEMO",
                endpoint="binance_spot_testnet",
                status="READY",
                eligibility="DEMO_CERTIFIED",
                is_active=is_active,
            )
        )


def _seed_valid_cert(uow: UnitOfWork) -> None:
    with uow.session() as session:
        session.add(
            CertificationRecord(
                cert_id="cert-valid",
                tuple_key=D1B_ALLOWLIST.canonical_key,
                valid=True,
                lifecycle_count=50,
                soak_passed=True,
            )
        )


# --- test_connection ---------------------------------------------------


@pytest.mark.d1c
def test_test_connection_returns_redacted_capabilities_on_success(
    migrated_uow: UnitOfWork,
) -> None:
    controller = BrokerHubController(
        migrated_uow, exchange_factory=FakeCcxtExchange
    )

    result = controller.test_connection()

    assert result.ok is True
    assert result.error_redacted is None
    assert result.capabilities is not None
    assert result.capabilities["exchange_id"] == "binance"
    assert result.capabilities["endpoint_class"] == "binance_spot_testnet"
    # G7 step 5 — a clean connect()+get_capabilities() is VERIFIED.
    assert result.verdict == "VERIFIED"


@pytest.mark.d1c
def test_test_connection_never_raises_and_redacts_the_error(
    migrated_uow: UnitOfWork,
) -> None:
    controller = BrokerHubController(
        migrated_uow, exchange_factory=lambda: FakeCcxtExchange(fail_auth=True)
    )

    result = controller.test_connection()  # must not raise

    assert result.ok is False
    assert result.capabilities is None
    assert result.error_redacted is not None
    # Honest limitation (see `_classify_connection_error`'s docstring):
    # `FakeCcxtExchange(fail_auth=True)` raises a plain `RuntimeError`, which
    # is indistinguishable from a network failure without a real ccxt
    # `AuthenticationError`/`PermissionDenied` type — so this resolves to
    # UNKNOWN, not DENIED. DENIED is only reachable against a real ccxt
    # client raising a real typed auth error (not exercised by this suite,
    # which never touches real network/ccxt).
    assert result.verdict == "UNKNOWN"


@pytest.mark.d1c
def test_test_connection_records_an_auditable_snapshot(migrated_uow: UnitOfWork) -> None:
    controller = BrokerHubController(migrated_uow, exchange_factory=FakeCcxtExchange)

    controller.test_connection()

    with migrated_uow.session() as session:
        state = build_broker_hub_state(session, demo_credentials_configured=False)
    assert state.last_test_at is not None
    assert state.last_error_redacted is None
    assert state.capabilities_redacted is not None
    assert state.last_verdict == "VERIFIED"


@pytest.mark.d1c
def test_test_connection_paper_mode_does_not_touch_ccxt(migrated_uow: UnitOfWork) -> None:
    # exchange_factory intentionally omitted — a PAPER-mode test must never
    # need it, since Paper is a local adapter with nothing to connect to.
    controller = BrokerHubController(migrated_uow)

    result = controller.test_connection(mode="PAPER")

    assert result.ok is True
    assert result.capabilities == {"adapter_id": "paper", "connected": True}


# --- enable_demo (T031 cert gate) ---------------------------------------


@pytest.mark.d1c
def test_enable_demo_refuses_with_no_cert_row(migrated_uow: UnitOfWork) -> None:
    controller = BrokerHubController(migrated_uow)

    result = controller.enable_demo(DEMO_ACCOUNT_ID)  # must not raise

    assert result.ok is False
    assert result.account_id is None
    assert result.refused_reason is not None
    with migrated_uow.session() as session:
        assert session.get(Account, DEMO_ACCOUNT_ID) is None


@pytest.mark.d1c
def test_enable_demo_refuses_when_cert_invalid(migrated_uow: UnitOfWork) -> None:
    with migrated_uow.session() as session:
        session.add(
            CertificationRecord(
                cert_id="cert-invalid",
                tuple_key=D1B_ALLOWLIST.canonical_key,
                valid=False,
            )
        )
    controller = BrokerHubController(migrated_uow)

    result = controller.enable_demo(DEMO_ACCOUNT_ID)

    assert result.ok is False
    assert result.refused_reason is not None
    with migrated_uow.session() as session:
        assert session.get(Account, DEMO_ACCOUNT_ID) is None


@pytest.mark.d1c
def test_enable_demo_succeeds_when_cert_valid(migrated_uow: UnitOfWork) -> None:
    _seed_valid_cert(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.enable_demo(DEMO_ACCOUNT_ID)

    assert result.ok is True
    assert result.account_id == DEMO_ACCOUNT_ID
    assert result.refused_reason is None
    with migrated_uow.session() as session:
        acc = session.get(Account, DEMO_ACCOUNT_ID)
        assert acc is not None
        assert acc.mode == "DEMO"
        assert acc.status == "READY"
        assert acc.is_active is True


@pytest.mark.d1c
def test_enable_demo_captures_real_baseline_versions(migrated_uow: UnitOfWork) -> None:
    """FR-009: `enable_demo` must call `cert.capture_baseline` with real,
    non-placeholder values — before this fix `snapshot_versions` was never
    called anywhere in production (headless or UI), only in tests."""
    import ccxt

    from autotrade import __version__ as app_version

    _seed_valid_cert(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.enable_demo(DEMO_ACCOUNT_ID)

    assert result.ok is True
    with migrated_uow.session() as session:
        row = (
            session.query(CertificationRecord)
            .filter_by(tuple_key=D1B_ALLOWLIST.canonical_key)
            .one()
        )
        assert row.app_version == app_version
        assert row.ccxt_version == ccxt.__version__
        assert row.endpoint_fingerprint == D1B_ALLOWLIST.canonical_key
        assert row.instrument_metadata_hash
        assert len(row.instrument_metadata_hash) == 64  # sha256 hex digest


@pytest.mark.d1c
def test_enable_demo_still_succeeds_when_baseline_capture_fails(
    migrated_uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Baseline capture is best-effort provenance, not a new gate — a
    failure inside `capture_baseline` must never refuse or raise into the
    view once the real cert gate has already passed."""
    from autotrade.app_ui.controllers import broker_hub as broker_hub_module

    def _boom(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("simulated snapshot failure")

    monkeypatch.setattr(broker_hub_module, "capture_baseline", _boom)

    _seed_valid_cert(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.enable_demo(DEMO_ACCOUNT_ID)

    assert result.ok is True
    assert result.account_id == DEMO_ACCOUNT_ID


@pytest.mark.d1c
def test_disable_demo_locks_and_deactivates_demo_accounts(migrated_uow: UnitOfWork) -> None:
    _seed_valid_cert(migrated_uow)
    controller = BrokerHubController(migrated_uow)
    controller.enable_demo(DEMO_ACCOUNT_ID)

    controller.disable_demo()

    with migrated_uow.session() as session:
        acc = session.get(Account, DEMO_ACCOUNT_ID)
        assert acc.status == "SAFE_LOCK"
        assert acc.is_active is False


# --- switch_account (T032 fail-closed) ----------------------------------


@pytest.mark.d1c
def test_switch_account_refused_not_flat(migrated_uow: UnitOfWork) -> None:
    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("demo", position_qty=1.0)  # must not raise

    assert result.ok is False
    assert result.reasons == ("not_flat",)
    assert result.error is None


@pytest.mark.d1c
def test_switch_account_refused_open_recon(migrated_uow: UnitOfWork) -> None:
    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            ReconBreak(
                type="orphan",
                payload={"account_id": DEFAULT_PAPER_ACCOUNT_ID},
                status="open",
                at=datetime.now(UTC),
            )
        )
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("demo")

    assert result.ok is False
    assert result.reasons == ("open_recon",)


@pytest.mark.d1c
def test_switch_account_refused_unknown_or_submitting(migrated_uow: UnitOfWork) -> None:
    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    with migrated_uow.session() as session:
        session.add(
            OrderIntent(
                intent_id="i1",
                client_order_id="c1",
                state=IntentState.UNKNOWN.value,
                account_id=DEFAULT_PAPER_ACCOUNT_ID,
                side="buy",
                qty=1,
                symbol="PAPER-INTERNAL-1",
            )
        )
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("demo")

    assert result.ok is False
    assert result.reasons == ("unknown_or_submitting",)


@pytest.mark.d1c
def test_switch_account_to_demo_refused_when_not_yet_provisioned(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_paper_active(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("demo")  # must not raise

    assert result.ok is False
    assert result.reasons == ()
    assert result.error is not None


@pytest.mark.d1c
def test_switch_account_succeeds_when_flat_and_clean(migrated_uow: UnitOfWork) -> None:
    _seed_paper_active(migrated_uow)
    _seed_demo_ready(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("demo")

    assert result.ok is True
    assert result.account_id == DEMO_ACCOUNT_ID
    assert result.mode == "DEMO"
    with migrated_uow.session() as session:
        assert session.get(Account, DEMO_ACCOUNT_ID).is_active is True
        assert session.get(Account, DEFAULT_PAPER_ACCOUNT_ID).is_active is False


@pytest.mark.d1c
def test_switch_account_to_paper_provisions_default_when_missing(
    migrated_uow: UnitOfWork,
) -> None:
    _seed_demo_ready(migrated_uow, is_active=True)
    controller = BrokerHubController(migrated_uow)

    result = controller.switch_account("paper")

    assert result.ok is True
    assert result.account_id == DEFAULT_PAPER_ACCOUNT_ID
    with migrated_uow.session() as session:
        assert session.get(Account, DEFAULT_PAPER_ACCOUNT_ID) is not None


# --- store_credentials (G1.2/G7 "tự kết nối") ---------------------------


@pytest.mark.d1c
def test_store_credentials_creates_a_new_account_row_when_none_exists(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = BrokerHubController(migrated_uow)

    result = controller.store_credentials(
        DEMO_ACCOUNT_ID, api_key="demo-key-abc", api_secret="demo-secret-xyz"
    )

    assert result.ok is True
    assert result.error is None
    # Never carries the plaintext back.
    assert "demo-key-abc" not in repr(result)
    assert "demo-secret-xyz" not in repr(result)

    with migrated_uow.session() as session:
        acc = session.get(Account, DEMO_ACCOUNT_ID)
        assert acc is not None
        assert acc.status == "NEW"
        assert acc.eligibility == "INELIGIBLE"
        assert acc.is_active is False
        assert acc.adapter_id == "ccxt"
        assert acc.mode == "DEMO"
        assert acc.endpoint == "binance_spot_testnet"
        ref = session.get(AccountSecretsRef, DEMO_ACCOUNT_ID)
        assert ref is not None
        assert ref.keyring_service == "AutoTradeAI"
        assert ref.keyring_user == f"{DEMO_ACCOUNT_ID}:api_key"

    # Exact keyring keys `_demo_store_creds` uses — CLI and UI must never
    # disagree about where a DEMO credential lives.
    assert fake_keyring.get_password("AutoTradeAI", f"{DEMO_ACCOUNT_ID}:api_key") == (
        "demo-key-abc"
    )
    assert fake_keyring.get_password("AutoTradeAI", f"{DEMO_ACCOUNT_ID}:api_secret") == (
        "demo-secret-xyz"
    )


@pytest.mark.d1c
def test_store_credentials_does_not_overwrite_an_existing_accounts_status(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    _seed_demo_ready(migrated_uow, is_active=True)
    controller = BrokerHubController(migrated_uow)

    result = controller.store_credentials(
        DEMO_ACCOUNT_ID, api_key="new-key", api_secret="new-secret"
    )

    assert result.ok is True
    with migrated_uow.session() as session:
        acc = session.get(Account, DEMO_ACCOUNT_ID)
        # Untouched — still whatever `_seed_demo_ready` set, not reset to
        # NEW/INELIGIBLE/inactive.
        assert acc.status == "READY"
        assert acc.eligibility == "DEMO_CERTIFIED"
        assert acc.is_active is True
    assert fake_keyring.get_password("AutoTradeAI", f"{DEMO_ACCOUNT_ID}:api_key") == "new-key"


@pytest.mark.d1c
def test_store_credentials_requires_both_fields(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = BrokerHubController(migrated_uow)

    result = controller.store_credentials(DEMO_ACCOUNT_ID, api_key="", api_secret="x")

    assert result.ok is False
    assert result.error is not None
    with migrated_uow.session() as session:
        assert session.get(Account, DEMO_ACCOUNT_ID) is None
    assert fake_keyring.get_password("AutoTradeAI", f"{DEMO_ACCOUNT_ID}:api_key") is None


@pytest.mark.d1c
def test_demo_credentials_configured_reflects_keyring_presence(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = BrokerHubController(migrated_uow)

    assert controller.demo_credentials_configured() is False

    controller.store_credentials(DEMO_ACCOUNT_ID, api_key="k", api_secret="s")

    assert controller.demo_credentials_configured() is True


# --- snapshot / read model ------------------------------------------------


@pytest.mark.d1c
def test_snapshot_reflects_accounts_and_cert(migrated_uow: UnitOfWork) -> None:
    _seed_paper_active(migrated_uow)
    _seed_valid_cert(migrated_uow)
    controller = BrokerHubController(migrated_uow)

    state = controller.snapshot()

    assert state.paper_account is not None
    assert state.paper_account.account_id == DEFAULT_PAPER_ACCOUNT_ID
    assert state.demo_account is None
    assert state.cert_valid is True
    assert state.can_enable_demo is True
    assert state.demo_credentials_configured is False


@pytest.mark.d1c
def test_snapshot_reflects_stored_demo_credentials(
    migrated_uow: UnitOfWork, fake_keyring: FakeKeyring
) -> None:
    controller = BrokerHubController(migrated_uow)
    controller.store_credentials(
        DEMO_ACCOUNT_ID, api_key="a-very-secret-key", api_secret="a-very-secret-value"
    )

    state = controller.snapshot()

    # Presence-only — the state must report the boolean, never the values.
    assert state.demo_credentials_configured is True
    assert "a-very-secret-key" not in repr(state)
    assert "a-very-secret-value" not in repr(state)


@pytest.mark.d1c
def test_snapshot_empty_db_is_not_crashing(migrated_uow: UnitOfWork) -> None:
    controller = BrokerHubController(migrated_uow)

    state = controller.snapshot()

    assert state.paper_account is None
    assert state.demo_account is None
    assert state.cert_valid is False
    assert state.can_enable_demo is False
    assert state.last_test_at is None
