"""Pipeline de campanha: decisão -> geração -> regras -> juiz -> (até N regenerações).

Uso:
  python -m src.campanha.pipeline --n 3          # amostra pequena para testar
  python -m src.campanha.pipeline --n 30         # lote
Saída: dados/campanhas.jsonl (uma linha por campanha) e resumo no terminal.
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd

from src.campanha import gerador, juiz, llm, regras
from src.campanha.decisao import decidir
from src.clima.coleta import carregar_config

RAIZ = Path(__file__).resolve().parents[2]


def processar(ctx: dict, cfg: dict, modelo_gerador: str | None = None) -> dict:
    """Roda uma campanha completa. Devolve o registro com push final, notas, tempo e custo."""
    inicio = time.perf_counter()
    max_reg = cfg["campanha"]["max_regeneracoes"]
    erros, tentativas, custo = None, [], 0.0
    status, push, veredito = "reprovado", None, None

    for i in range(max_reg + 1):
        g = gerador.gerar(ctx, cfg, modelo=modelo_gerador, erros_anteriores=erros)
        custo += g["custo_usd"]
        push = g["push"]
        falhas = regras.validar(push, ctx, cfg)
        tent = {"tentativa": i + 1, "push": push, "falhas_regras": falhas, "latencia_gerador_s": g["latencia_s"]}
        if falhas:
            tentativas.append(tent)
            erros = falhas
            continue
        j = juiz.avaliar(push, ctx, cfg)
        custo += j["custo_usd"]
        veredito = j["veredito"]
        tent["juiz"] = veredito
        tentativas.append(tent)
        if veredito["aprovado"]:
            status = "aprovado_pelo_pipeline"
            break
        erros = [f"juiz: {veredito['motivo']}"]

    return {
        "contexto": ctx, "status": status, "push_final": push, "juiz": veredito,
        "n_tentativas": len(tentativas), "tentativas": tentativas,
        "modelo_gerador": modelo_gerador or cfg["campanha"]["modelo_gerador"],
        "tempo_total_s": round(time.perf_counter() - inicio, 2), "custo_usd": round(custo, 6),
    }


def amostrar_momentos(cfg: dict, n: int, semente: int = 7) -> list[dict]:
    """Sorteia n momentos reais do histórico em que algum gatilho disparou, balanceando os gatilhos."""
    clima = pd.read_csv(RAIZ / "dados" / "clima.csv", parse_dates=["datahora"])
    clima["hora"] = clima["datahora"].dt.hour
    momentos = []
    g = cfg["gatilhos"]
    clima["calor"] = clima["apparent_temperature"] >= g["calor"]["sensacao_termica_min_c"]
    clima["frio"] = clima["apparent_temperature"] <= g["frio"]["sensacao_termica_max_c"]
    clima["chuva"] = clima["precipitation"] >= g["chuva"]["precipitacao_min_mm_h"]
    escolhidos = []
    por_tipo = max(1, n // 3)
    for tipo in ["calor", "frio", "chuva"]:
        pool = clima[clima[tipo]]
        escolhidos.append(pool.sample(min(por_tipo, len(pool)), random_state=semente))
    amostra = pd.concat(escolhidos).drop_duplicates().head(n)
    for _, r in amostra.iterrows():
        ctx = decidir(r["zona"], int(r["hora"]), float(r["apparent_temperature"]), float(r["precipitation"]), cfg)
        if ctx["dispara"]:
            momentos.append(ctx)
    return momentos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--modelo", default=None, help="sobrescreve o modelo gerador (comparação)")
    ap.add_argument("--saida", default="campanhas.jsonl")
    ap.add_argument("--pular", type=int, default=0, help="pula os N primeiros momentos (retomar um lote)")
    args = ap.parse_args()

    cfg = carregar_config()
    momentos = amostrar_momentos(cfg, args.n)[args.pular:]
    saida = RAIZ / "dados" / args.saida
    resultados = []
    with open(saida, "a", encoding="utf-8") as f:
        for i, ctx in enumerate(momentos, 1):
            try:
                res = processar(ctx, cfg, args.modelo)
            except llm.TetoDeGastoExcedido:
                raise
            except Exception as e:  # uma falha isolada não derruba o lote
                print(f"[{i}/{len(momentos)}] ERRO ({type(e).__name__}): {e}")
                continue
            resultados.append(res)
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(momentos)}] {ctx['nome_zona']} {ctx['hora']:02d}h {'+'.join(ctx['gatilhos'])} "
                  f"-> {res['status']} ({res['n_tentativas']} tent., {res['tempo_total_s']}s, ${res['custo_usd']:.4f})")

    df = pd.DataFrame(resultados)
    print("\nResumo:")
    print("aprovadas:", (df["status"] == "aprovado_pelo_pipeline").mean().round(2))
    print("tempo médio (s):", df["tempo_total_s"].mean().round(2))
    print("custo total (US$):", df["custo_usd"].sum().round(4))


if __name__ == "__main__":
    main()
