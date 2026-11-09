"""API do projeto: serve os dados das campanhas, registra a aprovação humana e entrega a página web.

Rodar:  uvicorn src.api.main:app --port 8000   (depois abra http://localhost:8000)
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "dados"
WEB = RAIZ / "app" / "web"

app = FastAPI(title="Clima → Campanha")


def _linhas(arq: Path) -> list[dict]:
    if not arq.exists():
        return []
    return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]


def _campanhas() -> list[dict]:
    itens = _linhas(DADOS / "campanhas.jsonl")
    for it in itens:
        c, p = it["contexto"], it["push_final"] or {}
        chave = f"{c['zona']}|{c['hora']}|{','.join(c['gatilhos'])}|{p.get('titulo')}|{p.get('corpo')}"
        it["id"] = hashlib.md5(chave.encode()).hexdigest()[:10]
    return itens


def _envios() -> dict:
    return {r["id"]: r for r in _linhas(DADOS / "envios.jsonl")}


@app.get("/api/campanhas")
def listar_campanhas() -> list[dict]:
    envios = _envios()
    saida = []
    for c in _campanhas():
        e = envios.get(c["id"])
        saida.append({**c, "decisao": e["decisao"] if e else None, "decidida_em": e["quando"] if e else None})
    return saida


class Decisao(BaseModel):
    decisao: str  # "aprovado" ou "rejeitado"


@app.post("/api/campanhas/{campanha_id}/decisao")
def decidir(campanha_id: str, corpo: Decisao) -> dict:
    if corpo.decisao not in ("aprovado", "rejeitado"):
        raise HTTPException(400, "decisao deve ser 'aprovado' ou 'rejeitado'")
    item = next((c for c in _campanhas() if c["id"] == campanha_id), None)
    if item is None:
        raise HTTPException(404, "campanha não encontrada")
    reg = {"id": campanha_id, "decisao": corpo.decisao, "quando": datetime.now().isoformat(timespec="seconds"),
           "push": item["push_final"], "contexto": item["contexto"]}
    with open(DADOS / "envios.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return {"ok": True, "decisao": corpo.decisao, "quando": reg["quando"]}


class TempoManual(BaseModel):
    minutos: list[float]


@app.get("/api/resultados")
def resultados() -> dict:
    camp = _campanhas()
    out: dict = {"n": len(camp)}
    if camp:
        df = pd.DataFrame([{"ok": c["status"] == "aprovado_pelo_pipeline", "tent": c["n_tentativas"],
                            "tempo": c["tempo_total_s"], "custo": c["custo_usd"]} for c in camp])
        out["aprovadas_pct"] = float(df["ok"].mean() * 100)
        out["tentativas_media"] = float(df["tent"].mean())
        out["tempo_medio_s"] = float(df["tempo"].mean())
        out["custo_medio_usd"] = float(df["custo"].mean())
    arq = DADOS / "metricas_modelo.csv"
    if arq.exists():
        m = pd.read_csv(arq).groupby("modelo")[["MAE", "MAE_horas_com_gatilho"]].mean()
        out["modelo"] = {k: {"mae": float(v["MAE"]), "mae_gatilho": float(v["MAE_horas_com_gatilho"])}
                         for k, v in m.iterrows()}
    arq = DADOS / "teste_juiz.json"
    if arq.exists():
        tj = json.loads(arq.read_text(encoding="utf-8"))
        out["juiz"] = {"acertos": sum(t["acertou"] for t in tj), "total": len(tj)}
    arq = DADOS / "tempo_manual.json"
    out["tempo_manual_min"] = json.loads(arq.read_text())["minutos"] if arq.exists() else [0, 0, 0]
    return out


@app.post("/api/tempo")
def salvar_tempo(corpo: TempoManual) -> dict:
    (DADOS / "tempo_manual.json").write_text(json.dumps({"minutos": corpo.minutos}))
    return {"ok": True}


@app.get("/")
def pagina() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
