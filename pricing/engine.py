"""pricing/engine.py — Motor de precificação inteligente."""
import logging
from decimal import Decimal, ROUND_UP
from typing import Optional
from sqlalchemy.orm import Session

from config.settings import MARKETPLACE_COMMISSIONS, TAX_RATE, ML_MIN_MARGIN
from scrapers.ml_scraper import get_competitor_stats
from ml.inference.predictor import predict_price
from models.orm import Product, PricingResult

log = logging.getLogger("msp.pricing")


def calculate_price(
    db: Session,
    product_id: str,
    cliente_id: str,
    marketplace: str = "mercadolivre",
    modo: str = "rule_based",
    markup_override: Optional[float] = None,
) -> dict:
    """
    Calcula preço ideal para um produto.
    Modos: rule_based | ml_assisted
    Nunca viola: custo + margem_mínima.
    """
    product = db.query(Product).filter_by(id=product_id, cliente_id=cliente_id).first()
    if not product:
        raise ValueError(f"Produto {product_id} não encontrado")

    custo    = float(product.custo or 0)
    margem   = float(product.margem_minima or ML_MIN_MARGIN)
    comissao = MARKETPLACE_COMMISSIONS.get(marketplace, 0.14)
    imposto  = TAX_RATE
    markup   = markup_override or (margem + 0.10)

    # Concorrência
    conc = get_competitor_stats(db, product_id, marketplace)

    row = {
        "custo":                         custo,
        "margem_minima":                 margem,
        "comissao_pct":                  comissao,
        "imposto_pct":                   imposto,
        "preco_concorrencia_min":        conc.get("preco_min"),
        "preco_concorrencia_med":        conc.get("preco_medio"),
        "preco_concorrencia_max":        conc.get("preco_max"),
        "n_concorrentes":                conc.get("n_ofertas", 0),
        "pct_frete_gratis_concorrentes": 0.5,
        "vendas_media_concorrentes":     20,
    }

    ml_resultado = None
    if modo == "ml_assisted":
        ml_resultado = predict_price(row, marketplace)
        preco = ml_resultado["preco_previsto"]
    else:
        preco = _rule_based(custo, comissao, imposto, markup,
                            conc.get("preco_min"), conc.get("preco_medio"))

    # Garante margem mínima
    preco_minimo = custo / max(1 - comissao - imposto - margem, 0.01)
    preco        = max(preco, preco_minimo)

    # Arredondamento psicológico
    preco = _round_price(preco)

    lucro       = preco - custo - (preco * comissao) - (preco * imposto)
    margem_real = lucro / preco if preco > 0 else 0
    score_comp  = ml_resultado.get("score_competitividade", 0.5) if ml_resultado else \
                  _score_competitividade(preco, conc)

    breakdown = {
        "custo":          round(custo, 2),
        "comissao":       round(preco * comissao, 2),
        "imposto":        round(preco * imposto, 2),
        "lucro_estimado": round(lucro, 2),
        "margem_real_pct": round(margem_real * 100, 2),
        "markup_aplicado": round(markup * 100, 2),
    }

    result = PricingResult(
        cliente_id             = cliente_id,
        product_id             = product_id,
        marketplace            = marketplace,
        modo                   = modo,
        custo                  = custo,
        comissao_pct           = comissao,
        imposto_pct            = imposto,
        markup_pct             = markup,
        preco_sugerido         = preco,
        preco_concorrencia_min = conc.get("preco_min"),
        preco_concorrencia_med = conc.get("preco_medio"),
        lucro_estimado         = lucro,
        margem_real_pct        = margem_real,
        score_competitividade  = score_comp,
        ml_usado               = (modo == "ml_assisted"),
        ml_confianca           = ml_resultado.get("confianca") if ml_resultado else None,
        features_json          = row,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "product_id":             product_id,
        "marketplace":            marketplace,
        "modo":                   modo,
        "custo":                  custo,
        "preco_sugerido":         preco,
        "preco_concorrencia_min": conc.get("preco_min"),
        "preco_concorrencia_med": conc.get("preco_medio"),
        "lucro_estimado":         lucro,
        "margem_real_pct":        margem_real,
        "score_competitividade":  score_comp,
        "ml_usado":               modo == "ml_assisted",
        "ml_confianca":           ml_resultado.get("confianca") if ml_resultado else None,
        "breakdown":              breakdown,
        "result_id":              result.id,
    }


def _rule_based(custo, comissao, imposto, markup, conc_min=None, conc_med=None) -> float:
    preco_base = custo / max(1 - comissao - imposto - markup, 0.01)
    if conc_min and conc_med:
        preco_comp = conc_min * 0.35 + conc_med * 0.65
        if preco_comp > custo * 1.15:
            preco_base = min(preco_base, preco_comp * 1.01)
    return round(preco_base, 2)


def _round_price(preco: float) -> float:
    """Arredondamento psicológico: R$49,97 → R$49,99."""
    d = Decimal(str(preco))
    base = d.quantize(Decimal("1"), rounding=ROUND_UP)
    return float(base - Decimal("0.01"))


def _score_competitividade(preco: float, conc: dict) -> float:
    min_ = conc.get("preco_min", 0)
    max_ = conc.get("preco_max", 0)
    if not min_ or not max_ or max_ <= min_:
        return 0.5
    score = 1.0 - (preco - min_) / (max_ - min_)
    return round(max(0.0, min(1.0, score)), 4)


def batch_price(
    db: Session,
    cliente_id: str,
    marketplace: str = "mercadolivre",
    modo: str = "rule_based",
) -> list[dict]:
    """Precifica todos os produtos ativos de um cliente."""
    products = db.query(Product).filter_by(cliente_id=cliente_id, ativo=True).all()
    results  = []
    for p in products:
        try:
            r = calculate_price(db, p.id, cliente_id, marketplace, modo)
            results.append(r)
        except Exception as e:
            log.error(f"Erro ao precificar {p.id}: {e}")
            results.append({"product_id": p.id, "erro": str(e)})
    return results
