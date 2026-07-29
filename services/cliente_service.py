"""services/cliente_service.py — CRUD de clientes (multi-tenant)."""
import logging
from sqlalchemy.orm import Session
from models.orm import Cliente
from models.schemas import ClienteCreate

log = logging.getLogger("msp.service.cliente")


def create_cliente(db: Session, data: ClienteCreate) -> Cliente:
    if db.query(Cliente).filter_by(email=data.email).first():
        raise ValueError(f"Email já cadastrado: {data.email}")
    cliente = Cliente(nome=data.nome, email=data.email, plano=data.plano)
    db.add(cliente); db.commit(); db.refresh(cliente)
    log.info(f"Cliente criado: {cliente.id} | {cliente.email}")
    return cliente


def get_cliente(db: Session, cliente_id: str) -> Cliente | None:
    return db.query(Cliente).filter_by(id=cliente_id, ativo=True).first()


def list_clientes(db: Session) -> list[Cliente]:
    return db.query(Cliente).filter_by(ativo=True).order_by(Cliente.criado_em).all()


def delete_cliente(db: Session, cliente_id: str) -> bool:
    c = db.query(Cliente).filter_by(id=cliente_id).first()
    if not c: return False
    c.ativo = False; db.commit(); return True
