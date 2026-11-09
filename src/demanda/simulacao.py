"""Simula pedidos por hora, zona e categoria a partir do clima real e das premissas do config.yaml.

pedidos ~ Poisson( base(periodo, categoria) x volume(zona) x dia_da_semana x fator_clima )
fator_clima = produto, sobre os gatilhos ativos, de (1 + (fator - 1) * k_zona)

Uso:  python -m src.demanda.simulacao
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.clima.coleta import carregar_config

RAIZ = Path(__file__).resolve().parents[2]
CATEGORIAS = ["sopas", "sorvete", "bebidas", "comfort", "cafe"]


def periodo_da_hora(hora: pd.Series, periodos: dict) -> pd.Series:
    saida = pd.Series(index=hora.index, dtype=object)
    for nome, (ini, fim) in periodos.items():
        if ini <= fim:
            mask = (hora >= ini) & (hora <= fim)
        else:  # atravessa a meia-noite
            mask = (hora >= ini) | (hora <= fim)
        saida[mask] = nome
    return saida


def marcar_gatilhos(clima: pd.DataFrame, gat: dict) -> pd.DataFrame:
    clima = clima.copy()
    clima["calor"] = (clima["apparent_temperature"] >= gat["calor"]["sensacao_termica_min_c"]).astype(int)
    clima["frio"] = (clima["apparent_temperature"] <= gat["frio"]["sensacao_termica_max_c"]).astype(int)
    clima["chuva"] = (clima["precipitation"] >= gat["chuva"]["precipitacao_min_mm_h"]).astype(int)
    return clima


def simular(cfg: dict) -> pd.DataFrame:
    dem = cfg["demanda"]
    rng = np.random.default_rng(dem["semente"])

    clima = pd.read_csv(RAIZ / "dados" / "clima.csv", parse_dates=["datahora"])
    clima = marcar_gatilhos(clima, cfg["gatilhos"])
    clima["hora"] = clima["datahora"].dt.hour
    clima["dia_semana"] = clima["datahora"].dt.day_of_week
    clima["periodo"] = periodo_da_hora(clima["hora"], dem["periodos"])

    partes = []
    for cat in CATEGORIAS:
        d = clima.copy()
        d["categoria"] = cat
        base = d["periodo"].map(lambda p: dem["base"][p][cat]).astype(float)
        volume = d["zona"].map(lambda z: dem["zonas"][z]["volume"])
        k = d["zona"].map(lambda z: dem["zonas"][z]["k"])
        dia = d["dia_semana"].map(lambda i: dem["dia_semana"][i])
        fator = np.ones(len(d))
        for g in ["calor", "frio", "chuva"]:
            efeito = 1 + (dem["fatores_clima"][g][cat] - 1) * k
            fator = fator * np.where(d[g] == 1, efeito, 1.0)
        d["fator_verdadeiro"] = fator
        d["pedidos"] = rng.poisson(base * volume * dia * fator)
        partes.append(d)

    df = pd.concat(partes, ignore_index=True)
    return df[["datahora", "zona", "categoria", "periodo", "hora", "dia_semana",
               "calor", "frio", "chuva", "fator_verdadeiro", "pedidos"]]


def main() -> None:
    cfg = carregar_config()
    df = simular(cfg)
    saida = RAIZ / "dados" / "demanda.csv"
    df.to_csv(saida, index=False)
    print(f"{len(df)} linhas salvas em {saida}")
    print(df.groupby("categoria")["pedidos"].sum())


if __name__ == "__main__":
    main()
