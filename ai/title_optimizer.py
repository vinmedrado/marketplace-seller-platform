"""ai/title_optimizer.py — Otimização de títulos para SEO nos marketplaces."""
import re
import logging

log = logging.getLogger("msp.ai.title")

# Palavras proibidas / ruído
_STOP_WORDS = {
    "de", "do", "da", "dos", "das", "e", "ou", "para", "com",
    "em", "um", "uma", "o", "a", "os", "as", "no", "na",
}

# Abreviações comuns nos títulos ML
_ABBREV_MAP = {
    "p/":   "para",
    "c/":   "com",
    "s/":   "sem",
    "kit":  "Kit",
    "nfe":  "NF-e",
    "orig": "Original",
    "gar":  "Garantia",
}

# Palavras SEO de alto impacto por categoria
_SEO_KEYWORDS = {
    "eletronicos": ["Original", "Garantia", "NF-e", "Lacrado"],
    "moveis":      ["Montado", "MDF", "18mm", "Resistente"],
    "roupas":      ["Atacado", "Frete Grátis", "Pronta Entrega"],
    "default":     ["Original", "Qualidade", "Pronta Entrega"],
}

# Máx chars por marketplace
_MAX_CHARS = {
    "mercadolivre": 60,
    "shopee":       100,
    "amazon":       200,
}


def optimize_title(
    titulo: str,
    marketplace: str = "mercadolivre",
    categoria: str = "default",
    marca: str = "",
    modelo: str = "",
) -> dict:
    """
    Otimiza título para SEO no marketplace.
    Retorna dict com título otimizado e score.
    """
    max_chars = _MAX_CHARS.get(marketplace, 60)
    original  = titulo.strip()

    # 1. Limpeza básica
    cleaned = _clean(original)

    # 2. Capitalização
    capitalized = _capitalize(cleaned)

    # 3. Injeção de marca/modelo
    if marca and marca.lower() not in capitalized.lower():
        capitalized = f"{marca} {capitalized}"
    if modelo and modelo.lower() not in capitalized.lower():
        capitalized = f"{capitalized} {modelo}"

    # 4. Adiciona palavras SEO se couber
    cat_key  = categoria.lower() if categoria else "default"
    seo_tags = _SEO_KEYWORDS.get(cat_key, _SEO_KEYWORDS["default"])
    otimizado = capitalized
    for tag in seo_tags:
        if tag.lower() not in otimizado.lower():
            candidate = f"{otimizado} {tag}"
            if len(candidate) <= max_chars:
                otimizado = candidate
            else:
                break

    # 5. Truncate respeitando palavras
    otimizado = _truncate(otimizado, max_chars)

    # 6. Score simples
    score = _score(otimizado, max_chars, seo_tags)

    log.debug(f"Título otimizado: '{original}' → '{otimizado}' (score={score:.2f})")
    return {
        "original":  original,
        "otimizado": otimizado,
        "chars":     len(otimizado),
        "max_chars": max_chars,
        "score":     score,
        "sugestoes": _suggestions(otimizado, max_chars, seo_tags),
    }


def _clean(titulo: str) -> str:
    # Remove caracteres especiais desnecessários
    titulo = re.sub(r"[^\w\s\-/().,]", " ", titulo)
    # Expande abreviações
    for abbrev, full in _ABBREV_MAP.items():
        pat = r"(?<![a-zA-Z])" + re.escape(abbrev) + r"(?![a-zA-Z])"
        titulo = re.sub(pat, full, titulo, flags=re.IGNORECASE)
    # Remove espaços múltiplos
    titulo = re.sub(r"\s+", " ", titulo).strip()
    return titulo


def _capitalize(titulo: str) -> str:
    words = titulo.split()
    result = []
    for w in words:
        if w.lower() in _STOP_WORDS and result:
            result.append(w.lower())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def _truncate(titulo: str, max_chars: int) -> str:
    if len(titulo) <= max_chars:
        return titulo
    truncated = titulo[:max_chars].rsplit(" ", 1)[0]
    return truncated.rstrip(".,;- ")


def _score(titulo: str, max_chars: int, seo_tags: list) -> float:
    score = 0.0
    # Comprimento ótimo: 80-100% do máx
    ratio = len(titulo) / max_chars
    if 0.70 <= ratio <= 1.0:
        score += 0.4
    elif 0.50 <= ratio < 0.70:
        score += 0.2

    # Presença de SEO tags
    seo_found = sum(1 for t in seo_tags if t.lower() in titulo.lower())
    score += min(seo_found * 0.2, 0.4)

    # Capitalização correta
    if titulo[0].isupper():
        score += 0.1

    # Sem caracteres repetidos estranhos
    if not re.search(r"(.)\1{3,}", titulo):
        score += 0.1

    return round(min(score, 1.0), 3)


def _suggestions(titulo: str, max_chars: int, seo_tags: list) -> list:
    sugs = []
    if len(titulo) < max_chars * 0.7:
        sugs.append(f"Título muito curto ({len(titulo)}/{max_chars} chars) — adicione mais detalhes")
    missing = [t for t in seo_tags if t.lower() not in titulo.lower()]
    if missing:
        sugs.append(f"Considere adicionar: {', '.join(missing)}")
    if not re.search(r"\d", titulo):
        sugs.append("Adicione especificações numéricas (tamanho, voltagem, capacidade)")
    return sugs
