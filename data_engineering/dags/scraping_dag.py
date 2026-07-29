"""
data_engineering/dags/scraping_dag.py
DAG Airflow para scraping diário + pipeline de dados.
Fallback: scheduler Python puro se Airflow não disponível.
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger("msp.dag.scraping")

# ── Airflow DAG (quando disponível) ──────────
def _build_airflow_dag():
    try:
        from airflow import DAG
        from airflow.operators.python import PythonOperator

        default_args = {
            "owner":            "msp",
            "depends_on_past":  False,
            "start_date":       datetime(2024, 1, 1),
            "retries":          3,
            "retry_delay":      timedelta(minutes=5),
        }

        dag = DAG(
            "msp_scraping_pipeline",
            default_args=default_args,
            description="Scraping diário de concorrência + pipeline de dados",
            schedule_interval="0 6 * * *",
            catchup=False,
            tags=["msp", "scraping", "pricing"],
        )

        def task_scraping(**ctx):
            from db.base import SessionLocal
            from services.scraping_service import run_scraping
            db = SessionLocal()
            try:
                from models.orm import Product, Cliente
                clientes = db.query(Cliente).filter_by(ativo=True).all()
                for c in clientes:
                    prods = db.query(Product).filter_by(cliente_id=c.id, ativo=True).all()
                    for p in prods:
                        try:
                            run_scraping(db, p.id, c.id, max_pages=3)
                        except Exception as e:
                            log.error(f"Scraping falhou produto {p.id}: {e}")
            finally:
                db.close()

        def task_staging(**ctx):
            from db.base import SessionLocal
            from data_engineering.pipelines.staging_pipeline import process_staging
            from models.orm import Cliente
            db = SessionLocal()
            try:
                for c in db.query(Cliente).filter_by(ativo=True).all():
                    process_staging(db, c.id, "mercadolivre")
            finally:
                db.close()

        def task_mart(**ctx):
            from db.base import SessionLocal
            from data_engineering.pipelines.mart_pipeline import build_pricing_mart
            from models.orm import Cliente
            db = SessionLocal()
            try:
                for c in db.query(Cliente).filter_by(ativo=True).all():
                    build_pricing_mart(db, c.id, "mercadolivre")
            finally:
                db.close()

        def task_pricing(**ctx):
            from db.base import SessionLocal
            from pricing.engine import batch_price
            from models.orm import Cliente
            db = SessionLocal()
            try:
                for c in db.query(Cliente).filter_by(ativo=True).all():
                    batch_price(db, c.id, "mercadolivre", "ml_assisted")
            finally:
                db.close()

        t_scraping = PythonOperator(task_id="scraping",  python_callable=task_scraping, dag=dag)
        t_staging  = PythonOperator(task_id="staging",   python_callable=task_staging,  dag=dag)
        t_mart     = PythonOperator(task_id="mart",      python_callable=task_mart,     dag=dag)
        t_pricing  = PythonOperator(task_id="pricing",   python_callable=task_pricing,  dag=dag)

        t_scraping >> t_staging >> t_mart >> t_pricing
        return dag

    except ImportError:
        log.warning("Airflow não instalado. Use o scheduler Python.")
        return None


dag = _build_airflow_dag()


# ── Fallback: scheduler Python puro ──────────
def run_pipeline_once():
    """Executa o pipeline completo sem Airflow."""
    from db.base import SessionLocal
    from models.orm import Cliente, Product
    from services.scraping_service import run_scraping
    from data_engineering.pipelines.mart_pipeline import run_full_pipeline
    from pricing.engine import batch_price

    db = SessionLocal()
    try:
        clientes = db.query(Cliente).filter_by(ativo=True).all()
        for c in clientes:
            prods = db.query(Product).filter_by(cliente_id=c.id, ativo=True).all()
            log.info(f"Pipeline cliente {c.id}: {len(prods)} produtos")
            for p in prods:
                try:
                    run_scraping(db, p.id, c.id, max_pages=2)
                except Exception as e:
                    log.error(f"Scraping {p.id}: {e}")
            run_full_pipeline(db, c.id, "mercadolivre")
            batch_price(db, c.id, "mercadolivre", "ml_assisted")
        log.info("Pipeline concluído")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline_once()
