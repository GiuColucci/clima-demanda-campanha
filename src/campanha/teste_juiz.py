"""Testa se o juiz realmente reprova pushes ruins (sem passar pelas regras determinísticas).

Contexto fixo: calor forte (42 °C) às 16h na Zona Sul, categoria destacada = açaí e sorvete.
Uso:  python -m src.campanha.teste_juiz
"""
import json
from pathlib import Path

from src.campanha import juiz
from src.campanha.decisao import decidir
from src.clima.coleta import carregar_config

RAIZ = Path(__file__).resolve().parents[2]

# (rótulo, deve_aprovar, push)
CASOS = [
    ("bom 1", True, {"titulo": "Calorão na Zona Sul? 🍧", "corpo": "42 °C pede açaí gelado. Que tal pedir um agora?", "cupom": ""}),
    ("bom 2", True, {"titulo": "Hoje o dia pede sorvete", "corpo": "Tá um forno aí! Use CLIMA10 e ganhe 10% no seu sorvete.", "cupom": "CLIMA10"}),
    ("tom robótico", False, {"titulo": "Notificação promocional", "corpo": "Prezado cliente, informamos que estão disponíveis produtos da categoria sorvete em sua região.", "cupom": ""}),
    ("exagerado", False, {"titulo": "🔥🔥 MEGA OFERTA IMPERDÍVEL!!! 🔥🔥", "corpo": "CORRA!!! ÚLTIMAS HORAS!!! SORVETE COM TUDO!!!", "cupom": ""}),
    ("desconto inventado", False, {"titulo": "Sorvete com 40% OFF", "corpo": "Hoje todo sorvete com 40% de desconto na Zona Sul. Aproveite!", "cupom": ""}),
    ("promessa de prazo", False, {"titulo": "Sorvete em 10 minutos ou grátis", "corpo": "Entregamos seu açaí em 10 minutos garantidos. Peça agora!", "cupom": ""}),
    ("ignora o clima", False, {"titulo": "Bora de feijoada?", "corpo": "Sábado é dia de feijoada completa. Peça a sua!", "cupom": ""}),
    ("categoria errada", False, {"titulo": "Café fresquinho pra você", "corpo": "Comece a tarde com um café quentinho e pão de queijo.", "cupom": ""}),
    ("inglês", False, {"titulo": "Hot day? Get ice cream!", "corpo": "It is 42 degrees. Order your favorite ice cream now.", "cupom": ""}),
]


def main() -> None:
    cfg = carregar_config()
    ctx = decidir("zona_sul", 16, 42, 0, cfg)
    acertos, saida = 0, []
    for rotulo, deve, push in CASOS:
        r = juiz.avaliar(push, ctx, cfg)
        v = r["veredito"]
        ok = v["aprovado"] == deve
        acertos += ok
        saida.append({"caso": rotulo, "deveria_aprovar": deve, "veredito": v, "acertou": ok})
        print(f"{'OK  ' if ok else 'ERRO'} {rotulo:20s} tom={v['nota_tom']} adeq={v['nota_adequacao']} "
              f"alucinacao={v['alucinacao']} aprovado={v['aprovado']}")
    print(f"\nO juiz acertou {acertos}/{len(CASOS)} casos.")
    (RAIZ / "dados" / "teste_juiz.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
