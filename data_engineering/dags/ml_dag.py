"""data_engineering/dags/ml_dag.py — DAG de retreino semanal do modelo ML."""
import logging
from datetime import datetime, timedelta

log = logging.getLogger("msp.dag.ml")


def _build_dag():
    try:
        from airflow import DAG
        from airflow.operators.python import PythonOperator

        default_args = {
            "owner": "msp", "depends_on_past": False,
            "start_date": datetime(2024, 1, 1),
            "retries": 2, "retry_delay": timedelta(minutes=10),
        }
        dag = DAG(
            "msp_ml_retrain",
            default_args=default_args,
            description="Retreino semanal do modelo de precificação",
            schedule_interval="0 2 * * 0",
            catchup=False,
            tags=["msp", "ml"],
        )

        def task_build_features(**ctx):
            from db.base import SessionLocal
            from data_engineering.feature_store.store import build_product_features
            from models.orm import Product
            db = SessionLocal()
            try:
                for p in db.query(Product).filter_by(ativo=True).all():
                    build_product_features(db, p.id)
            finally:
                db.close()

        def task_train(**ctx):
            from db.base import SessionLocal
            from services.ml_service import train_model
            db = SessionLocal()
            try:
                train_model(db, "mercadolivre", force=True)
            finally:
                db.close()

        t1 = PythonOperator(task_id="build_features", python_callable=task_build_features, dag=dag)
        t2 = PythonOperator(task_id="train_model",    python_callable=task_train,          dag=dag)
        t1 >> t2
        return dag
    except ImportError:
        return None


dag = _build_dag()


def run_retrain():
    """Retreino manual sem Airflow."""
    from db.base import SessionLocal
    from services.ml_service import train_model
    db = SessionLocal()
    try:
        result = train_model(db, "mercadolivre", force=True)
        log.info(f"Retreino concluído: {result}")
        return result
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_retrain()
