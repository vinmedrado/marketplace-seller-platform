from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from time import sleep

from sqlalchemy.orm import Session

from db.base import SessionLocal
from models.orm import BackgroundJob, Product

LABELS = {
    "scraping": "Coletando concorrentes",
    "pricing": "Calculando preço ideal",
    "publish": "Preparando dry-run",
    "ml-train": "Treinando inteligência",
}
_executor = ThreadPoolExecutor(max_workers=2)


def create_job(db: Session, tenant_id: str, job_type: str, params: dict | None = None) -> BackgroundJob:
    job = BackgroundJob(
        tenant_id=tenant_id,
        cliente_id=tenant_id,
        job_type=job_type,
        status="queued",
        parameters_json=params or {},
        progress_current=0,
        progress_total=100,
        progress_label="Na fila",
        stdout_tail="Job registrado e aguardando worker.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _executor.submit(run_job_worker, job.id)
    return job


def _append(job: BackgroundJob, text: str) -> None:
    current = job.stdout_tail or ""
    job.stdout_tail = (current + "\n" + text).strip()[-4000:]


def _set_progress(db: Session, job: BackgroundJob, current: int, label: str) -> None:
    job.progress_current = current
    job.progress_label = label
    _append(job, f"[{datetime.utcnow().isoformat(timespec='seconds')}] {label}")
    db.commit()


def _pick_product(db: Session, tenant_id: str, params: dict) -> Product | None:
    product_id = params.get("product_id") if params else None
    q = db.query(Product).filter_by(cliente_id=tenant_id, ativo=True)
    if product_id:
        return q.filter_by(id=product_id).first()
    return q.first()


def run_job_worker(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(BackgroundJob).filter_by(id=job_id).first()
        if not job:
            return
        start = datetime.utcnow()
        job.status = "running"
        job.started_at = start
        job.progress_current = 5
        job.progress_label = LABELS.get(job.job_type, "Executando")
        _append(job, "Worker iniciado em background.")
        db.commit()

        params = job.parameters_json or {}
        tenant_id = job.tenant_id
        product = _pick_product(db, tenant_id, params)
        marketplace = params.get("marketplace", "mercadolivre")

        _set_progress(db, job, 20, "Preparando contexto do tenant")
        sleep(0.15)

        result: dict = {"ok": True, "job_type": job.job_type}
        if job.job_type == "scraping":
            if not product:
                raise ValueError("Nenhum produto ativo encontrado para scraping.")
            from services.scraping_service import run_scraping
            _set_progress(db, job, 40, "Executando coleta de concorrência")
            result = run_scraping(db, product.id, tenant_id, marketplace, params.get("query"), int(params.get("max_pages", 1)))
        elif job.job_type == "pricing":
            from pricing.engine import calculate_price, batch_price
            _set_progress(db, job, 45, "Calculando pricing")
            if product:
                result = calculate_price(db, product.id, tenant_id, marketplace, params.get("modo", "rule_based"))
            else:
                result = {"items": batch_price(db, tenant_id, marketplace, params.get("modo", "rule_based"))}
        elif job.job_type == "publish":
            if not product:
                raise ValueError("Nenhum produto ativo encontrado para publicação dry-run.")
            from services.publish_service import publish_product
            _set_progress(db, job, 45, "Gerando payload de publicação")
            result = publish_product(db, product.id, tenant_id, marketplace, dry_run=True)
        elif job.job_type == "ml-train":
            from services.ml_service import train_model
            _set_progress(db, job, 35, "Montando dataset e treinando modelo")
            result = train_model(
                db,
                marketplace=marketplace,
                force=bool(params.get("force", False)),
                tenant_id=tenant_id,
            )
        else:
            raise ValueError(f"Tipo de job inválido: {job.job_type}")

        _set_progress(db, job, 95, "Persistindo resultado")
        job.result_json = result
        job.status = "success"
        job.progress_current = 100
        job.progress_label = "Concluído"
        job.finished_at = datetime.utcnow()
        job.duration_seconds = (job.finished_at - start).total_seconds()
        _append(job, "Execução concluída com sucesso.")
        db.commit()
    except Exception as exc:
        job = db.query(BackgroundJob).filter_by(id=job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            if job.started_at:
                job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
            _append(job, f"Falha {type(exc).__name__}; consulte os logs internos com o id do job.")
            db.commit()
    finally:
        db.close()


def run_job_sync(db: Session, job_id: str):
    # Mantido por compatibilidade com testes/scripts antigos.
    run_job_worker(job_id)


def list_jobs(db: Session, tenant_id: str):
    return db.query(BackgroundJob).filter_by(tenant_id=tenant_id).order_by(BackgroundJob.created_at.desc()).all()


def rerun_job(db: Session, tenant_id: str, job_id: str) -> BackgroundJob | None:
    old = db.query(BackgroundJob).filter_by(id=job_id, tenant_id=tenant_id).first()
    if not old:
        return None
    new = create_job(db, tenant_id, old.job_type, old.parameters_json or {})
    return new
