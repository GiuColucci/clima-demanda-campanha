"""Modelo de uplift: estima quanto cada gatilho de clima muda os pedidos de cada categoria.

Para cada categoria ajusta uma regressão de Poisson com zona, período e dia da semana
(+ flags calor/frio/chuva). exp(coeficiente) = fator de uplift estimado.
Baseline: o mesmo modelo SEM as flags de clima.
Validação temporal: treino até `corte_treino_ate`, teste depois.

Uso:  python -m src.demanda.modelo
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.clima.coleta import carregar_config
from src.demanda.simulacao import CATEGORIAS

RAIZ = Path(__file__).resolve().parents[2]
GATILHOS = ["calor", "frio", "chuva"]


def matriz(df: pd.DataFrame, com_clima: bool) -> pd.DataFrame:
    X = pd.get_dummies(df[["zona", "periodo"]], dtype=float)
    X = X.join(pd.get_dummies(df["dia_semana"].astype(str), prefix="dia", dtype=float))
    if com_clima:
        X = X.join(df[GATILHOS].astype(float))
    return X


def main() -> None:
    cfg = carregar_config()
    df = pd.read_csv(RAIZ / "dados" / "demanda.csv", parse_dates=["datahora"])
    corte = pd.Timestamp(cfg["demanda"]["corte_treino_ate"]) + pd.Timedelta(days=1)
    verdade = cfg["demanda"]["fatores_clima"]

    linhas_metricas, linhas_fatores = [], []
    for cat in CATEGORIAS:
        d = df[df["categoria"] == cat]
        treino, teste = d[d["datahora"] < corte], d[d["datahora"] >= corte]
        resultados = {}
        for nome, com_clima in [("baseline", False), ("modelo", True)]:
            Xtr = matriz(treino, com_clima)
            Xte = matriz(teste, com_clima).reindex(columns=Xtr.columns, fill_value=0.0)
            m = PoissonRegressor(alpha=0.0, max_iter=500).fit(Xtr, treino["pedidos"])
            pred = m.predict(Xte)
            resultados[nome] = pred
            if com_clima:
                for g in GATILHOS:
                    linhas_fatores.append({
                        "categoria": cat, "gatilho": g,
                        "fator_estimado": float(np.exp(m.coef_[list(Xtr.columns).index(g)])),
                        "fator_config": verdade[g][cat],
                    })
        y = teste["pedidos"].to_numpy()
        # métrica principal também nas horas COM gatilho, onde o clima importa
        com_g = (teste[GATILHOS].sum(axis=1) > 0).to_numpy()
        for nome, pred in resultados.items():
            linhas_metricas.append({
                "categoria": cat, "modelo": nome,
                "MAE": mean_absolute_error(y, pred),
                "RMSE": mean_squared_error(y, pred) ** 0.5,
                "MAE_horas_com_gatilho": mean_absolute_error(y[com_g], pred[com_g]),
            })

    met = pd.DataFrame(linhas_metricas)
    fat = pd.DataFrame(linhas_fatores)
    met.to_csv(RAIZ / "dados" / "metricas_modelo.csv", index=False)
    fat.to_csv(RAIZ / "dados" / "fatores_estimados.csv", index=False)

    pd.options.display.float_format = "{:.3f}".format
    print("\nMétricas no teste (2026):")
    print(met.pivot(index="categoria", columns="modelo", values=["MAE", "MAE_horas_com_gatilho"]))
    print("\nMédia geral: ", met.groupby("modelo")[["MAE", "RMSE", "MAE_horas_com_gatilho"]].mean().to_string())
    print("\nFatores estimados x configurados:")
    print(fat.pivot(index="categoria", columns="gatilho", values=["fator_estimado", "fator_config"]))


if __name__ == "__main__":
    main()
