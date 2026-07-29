from services.rate_limit_service import SlidingWindowRateLimiter


def test_oauth_state_is_signed_and_rejects_tampering():
    from integrations.mercadolivre.auth import MLAuthError, _encode_state, validate_oauth_state

    state = _encode_state("tenant-123")
    assert validate_oauth_state(state) == "tenant-123"
    body, signature = state.split(".", 1)
    replacement = "0" if signature[-1] != "0" else "1"
    tampered = f"{body}.{signature[:-1]}{replacement}"
    try:
        validate_oauth_state(tampered)
        assert False, "state adulterado deveria ser rejeitado"
    except MLAuthError:
        pass


def test_oauth_state_nonce_can_only_be_consumed_once(db, cliente):
    import hashlib
    from datetime import datetime, timedelta

    from integrations.mercadolivre.auth import MLAuthError, _encode_state, validate_oauth_state
    from models.orm import OAuthState

    state = _encode_state(cliente.id)
    db.add(OAuthState(
        tenant_id=cliente.id,
        state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    ))
    db.commit()

    assert validate_oauth_state(state, db) == cliente.id
    try:
        validate_oauth_state(state, db)
        assert False, "nonce OAuth consumido não pode ser reutilizado"
    except MLAuthError:
        pass


def test_rate_limiter_blocks_after_window_limit():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("client")
    assert limiter.allow("client")
    assert not limiter.allow("client")


def test_invite_lifecycle_creates_user_and_invalidates_token(db, cliente):
    from models.orm import Organization, User, UserInvite
    from services.auth_service import hash_password
    from services.saas_service import accept_invite, get_invite, invite_user

    cliente.plano = "PROFESSIONAL"
    org = Organization(nome="Equipe Teste", slug=f"equipe-{cliente.id}", cliente_id=cliente.id)
    db.add(org)
    db.flush()
    owner = User(
        organization_id=org.id,
        cliente_id=cliente.id,
        nome="Owner Teste",
        email=f"owner-{cliente.id}@example.test",
        hashed_password=hash_password("senha-segura-owner"),
        role="owner",
        ativo=True,
    )
    db.add(owner)
    db.commit()

    invite_user(db, owner, {"email": "recrutador@example.test", "role": "viewer"})
    invite = db.query(UserInvite).filter_by(email="recrutador@example.test").one()
    assert get_invite(db, invite.token)["organization"] == "Equipe Teste"
    result = accept_invite(
        db,
        invite.token,
        {"name": "Pessoa Recrutadora", "password": "senha-forte-123"},
    )

    assert result["status"] == "accepted"
    assert db.query(User).filter_by(email="recrutador@example.test", ativo=True).count() == 1
    assert db.query(UserInvite).filter_by(id=invite.id, status="accepted").count() == 1


def test_privacy_retention_starts_in_dry_run(db, cliente):
    from datetime import datetime, timedelta

    from models.orm import ApiLog
    from services.privacy_service import cleanup_expired_data

    row = ApiLog(
        cliente_id=cliente.id,
        endpoint="/expired",
        metodo="GET",
        status_code=200,
        criado_em=datetime.utcnow() - timedelta(days=91),
    )
    db.add(row)
    db.commit()
    row_id = row.id

    preview = cleanup_expired_data(db)
    assert preview["dry_run"] is True
    assert preview["eligible"]["api_logs"] == 1
    assert db.query(ApiLog).filter_by(id=row_id).count() == 1

    applied = cleanup_expired_data(db, apply=True)
    assert applied["dry_run"] is False
    assert applied["deleted"]["api_logs"] == 1
    assert db.query(ApiLog).filter_by(id=row_id).count() == 0


def test_ml_dataset_filters_products_by_tenant(db, produto):
    from ml.datasets.dataset_builder import build_training_dataset

    frame = build_training_dataset(
        db,
        marketplace="mercadolivre",
        min_rows=1,
        tenant_id=produto.cliente_id,
    )
    assert len(frame) == 1
    assert float(frame.iloc[0]["custo"]) == float(produto.custo)
