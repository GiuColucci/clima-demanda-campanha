"""Decide se há gatilho de campanha e qual categoria destacar (sem IA, só regra e conta).

Mesma lógica do protótipo: ganho = pedidos-base x (fator de clima - 1), vence a categoria de maior ganho.
"""
from src.demanda.simulacao import CATEGORIAS, periodo_da_hora
import pandas as pd

NOME_CATEGORIA = {
    "sopas": "sopas e caldos",
    "sorvete": "açaí e sorvete",
    "bebidas": "bebidas geladas",
    "comfort": "comfort food (lanches e massas)",
    "cafe": "café da manhã e padaria",
}


def gatilhos_ativos(sensacao: float, chuva_mm_h: float, cfg: dict) -> list[str]:
    g = cfg["gatilhos"]
    ativos = []
    if sensacao >= g["calor"]["sensacao_termica_min_c"]:
        ativos.append("calor")
    if sensacao <= g["frio"]["sensacao_termica_max_c"]:
        ativos.append("frio")
    if chuva_mm_h >= g["chuva"]["precipitacao_min_mm_h"]:
        ativos.append("chuva")
    return ativos


def decidir(zona: str, hora: int, sensacao: float, chuva_mm_h: float, cfg: dict) -> dict:
    """Devolve o contexto da campanha, ou {'dispara': False} em dia normal."""
    dem = cfg["demanda"]
    ativos = gatilhos_ativos(sensacao, chuva_mm_h, cfg)
    periodo = periodo_da_hora(pd.Series([hora]), dem["periodos"]).iloc[0]
    if not ativos:
        return {"dispara": False, "zona": zona, "hora": hora, "periodo": periodo, "gatilhos": []}

    k = dem["zonas"][zona]["k"]
    ganhos = {}
    for cat in CATEGORIAS:
        fator = 1.0
        for g in ativos:
            fator *= 1 + (dem["fatores_clima"][g][cat] - 1) * k
        base = dem["base"][periodo][cat]
        ganhos[cat] = base * (fator - 1)
    destaque = max(ganhos, key=ganhos.get)
    return {
        "dispara": True,
        "zona": zona,
        "nome_zona": cfg["zonas"][zona]["nome"],
        "hora": hora,
        "periodo": periodo,
        "sensacao": sensacao,
        "chuva_mm_h": chuva_mm_h,
        "gatilhos": ativos,
        "categoria": destaque,
        "categoria_nome": NOME_CATEGORIA[destaque],
        "ganho_estimado": round(ganhos[destaque], 1),
    }
