"""Coleta o clima histórico por hora das 5 zonas (Open-Meteo) e salva em dados/clima.csv.

Uso:  python -m src.clima.coleta
"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml

RAIZ = Path(__file__).resolve().parents[2]
URL = "https://archive-api.open-meteo.com/v1/archive"


def carregar_config() -> dict:
    with open(RAIZ / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def baixar_zona(zona_id: str, zona: dict, cfg: dict) -> pd.DataFrame:
    clima = cfg["clima"]
    fim = date.today() - timedelta(days=clima["atraso_dias"])
    params = {
        "latitude": zona["lat"],
        "longitude": zona["lon"],
        "start_date": clima["inicio"],
        "end_date": fim.isoformat(),
        "hourly": ",".join(clima["variaveis_horarias"]),
        "timezone": clima["fuso"],
    }
    resp = requests.get(URL, params=params, timeout=60)
    resp.raise_for_status()
    horario = resp.json()["hourly"]
    df = pd.DataFrame(horario).rename(columns={"time": "datahora"})
    df["datahora"] = pd.to_datetime(df["datahora"])
    df.insert(0, "zona", zona_id)
    return df


def main() -> None:
    cfg = carregar_config()
    partes = []
    for zona_id, zona in cfg["zonas"].items():
        print(f"Baixando {zona['nome']}...")
        partes.append(baixar_zona(zona_id, zona, cfg))
    df = pd.concat(partes, ignore_index=True)
    saida = RAIZ / "dados" / "clima.csv"
    df.to_csv(saida, index=False)
    print(f"{len(df)} linhas salvas em {saida}")


if __name__ == "__main__":
    main()
