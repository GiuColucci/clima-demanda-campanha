"""Cliente mínimo da OpenRouter, com medição de tempo/custo e teto de gasto.

A chave vem de OPENROUTER_API_KEY (arquivo .env). Nunca é impressa nem gravada.
"""
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
URL = "https://openrouter.ai/api/v1/chat/completions"
ARQ_GASTO = RAIZ / "dados" / "gasto_llm.json"


class TetoDeGastoExcedido(RuntimeError):
    pass


def _gasto_atual() -> float:
    if ARQ_GASTO.exists():
        return json.loads(ARQ_GASTO.read_text())["total_usd"]
    return 0.0


def _somar_gasto(valor: float) -> float:
    total = _gasto_atual() + valor
    ARQ_GASTO.write_text(json.dumps({"total_usd": round(total, 6)}))
    return total


def extrair_json(texto: str) -> dict:
    """Aceita JSON puro ou dentro de ``` ... ```."""
    texto = texto.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.S)
    if m:
        texto = m.group(1)
    else:
        ini, fim = texto.find("{"), texto.rfind("}")
        if ini != -1 and fim != -1:
            texto = texto[ini:fim + 1]
    return json.loads(texto)


def chamar(modelo: str, sistema: str, usuario: str, cfg: dict, temperatura: float = 0.7,
           max_tokens: int = 600) -> dict:
    """Devolve {'json': dict, 'latencia_s', 'custo_usd', 'tokens_in', 'tokens_out'}."""
    load_dotenv(RAIZ / ".env")
    chave = os.getenv("OPENROUTER_API_KEY")
    if not chave:
        raise RuntimeError("OPENROUTER_API_KEY não encontrada. Crie o arquivo .env (veja .env.example).")
    teto = cfg["campanha"]["teto_gasto_usd"]
    if _gasto_atual() >= teto:
        raise TetoDeGastoExcedido(f"Gasto acumulado passou de US$ {teto:.2f}. Pipeline interrompido.")

    inicio = time.perf_counter()
    resp = requests.post(
        URL,
        headers={"Authorization": f"Bearer {chave}"},
        json={
            "model": modelo,
            "temperature": temperatura,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        },
        timeout=90,
    )
    latencia = time.perf_counter() - inicio
    resp.raise_for_status()
    dados = resp.json()
    texto = dados["choices"][0]["message"]["content"]
    if dados["choices"][0].get("finish_reason") == "length":
        raise RuntimeError(f"Resposta de {modelo} cortada por max_tokens={max_tokens}. Aumente o limite.")
    uso = dados.get("usage", {})
    t_in, t_out = uso.get("prompt_tokens", 0), uso.get("completion_tokens", 0)
    preco_in, preco_out = cfg["campanha"]["precos"][modelo]
    custo = (t_in * preco_in + t_out * preco_out) / 1_000_000
    _somar_gasto(custo)
    return {"json": extrair_json(texto), "latencia_s": latencia, "custo_usd": custo,
            "tokens_in": t_in, "tokens_out": t_out}
