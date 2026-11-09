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

from src.campanha.decisao import decidir as decidir_categoria
from src.campanha.llm import TetoDeGastoExcedido
from src.campanha.pipeline import processar
from src.clima.coleta import carregar_config

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


@app.get("/api/zonas")
def zonas() -> dict:
    """Zonas (com coordenadas) e limiares dos gatilhos, lidos do config.yaml. O n8n usa isto."""
    cfg = carregar_config()
    return {
        "zonas": [{"id": k, "nome": v["nome"], "lat": v["lat"], "lon": v["lon"]} for k, v in cfg["zonas"].items()],
        "gatilhos": {
            "calor_sensacao_min": cfg["gatilhos"]["calor"]["sensacao_termica_min_c"],
            "frio_sensacao_max": cfg["gatilhos"]["frio"]["sensacao_termica_max_c"],
            "chuva_mm_h_min": cfg["gatilhos"]["chuva"]["precipitacao_min_mm_h"],
        },
    }


class Momento(BaseModel):
    zona: str
    hora: int
    sensacao: float
    chuva_mm_h: float = 0.0


@app.post("/api/propostas")
def criar_proposta(m: Momento) -> dict:
    """Recebe um momento climático. Sem gatilho: não faz nada. Com gatilho: gera, avalia e,
    se o pipeline liberar, coloca a proposta na fila para aprovação humana."""
    cfg = carregar_config()
    if m.zona not in cfg["zonas"]:
        raise HTTPException(404, f"zona desconhecida: {m.zona}")
    ctx = decidir_categoria(m.zona, m.hora, m.sensacao, m.chuva_mm_h, cfg)
    if not ctx["dispara"]:
        return {"dispara": False, "motivo": "nenhum gatilho ativo"}
    try:
        res = processar(ctx, cfg)
    except TetoDeGastoExcedido as e:
        raise HTTPException(429, str(e))
    liberada = res["status"] == "aprovado_pelo_pipeline"
    if liberada:
        with open(DADOS / "campanhas.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
    return {"dispara": True, "gatilhos": ctx["gatilhos"], "categoria": ctx["categoria"],
            "liberada": liberada, "status": res["status"], "push": res["push_final"],
            "tentativas": res["n_tentativas"], "custo_usd": res["custo_usd"], "tempo_s": res["tempo_total_s"]}


@app.get("/")
def pagina() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
