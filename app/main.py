"""Painel: fila de campanhas disparadas pelo clima, com aprovação humana e envio simulado.

Rodar:  streamlit run app/main.py
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "dados"

COR = {"calor": "#E8590C", "frio": "#2F6FDB", "chuva": "#5E7384"}
ROTULO = {"calor": "Calor forte", "frio": "Frio", "chuva": "Chuva"}
PERIODO = {"manha": "manhã", "almoco": "almoço", "tarde": "tarde", "jantar": "jantar", "madrugada": "madrugada"}

st.set_page_config(page_title="Clima → Campanha", page_icon="🌦️", layout="wide")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Figtree:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root { --mare:#0E2A3B; --papel:#EEF3F4; --linha:#D3DEE2; --ok:#1F8A5B; --no:#B3261E; }
html, body, [class*="css"], .stApp { font-family:'Figtree',system-ui,sans-serif; color:var(--mare); }
.stApp { background:var(--papel); }
h1,h2,h3,.titulo { font-family:'Bricolage Grotesque','Figtree',sans-serif; letter-spacing:-0.02em; }
header[data-testid="stHeader"] { background:transparent; }
.block-container { padding-top:2rem; max-width:1180px; }
.topo { display:flex; align-items:baseline; gap:14px; margin-bottom:4px; }
.titulo-app { font-family:'Bricolage Grotesque',sans-serif; font-size:38px; font-weight:700; letter-spacing:-0.02em; line-height:1.1; }
.topo span { color:#4C6577; font-size:15px; }
.faixa { border-radius:10px; padding:16px 20px; color:#fff; margin-bottom:16px; }
.faixa .quando { font-size:14px; opacity:.85; }
.faixa .frase { font-family:'Bricolage Grotesque',sans-serif; font-size:26px; font-weight:700; line-height:1.2; margin-top:2px; }
.fato { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid var(--linha); font-size:15px; }
.fato:last-child { border-bottom:none; }
.fato b { font-weight:600; }
.celular { background:#fff; border-radius:26px; padding:18px 14px 20px; border:1px solid var(--linha); box-shadow:0 14px 30px -18px rgba(14,42,59,.45); max-width:340px; }
.celular .hora { text-align:center; color:#7C8F9B; font-size:13px; margin-bottom:12px; }
.push { background:#F6F8F9; border-radius:16px; padding:12px 14px 13px; border-left:6px solid var(--cor); }
.push .app { font-size:12px; color:#7C8F9B; margin-bottom:3px; }
.push .t { font-weight:600; font-size:16px; line-height:1.25; margin-bottom:3px; }
.push .c { font-size:14.5px; line-height:1.4; }
.push .cupom { display:inline-block; margin-top:8px; font-size:12.5px; font-weight:600; padding:2px 9px; border:1px dashed var(--cor); border-radius:99px; color:var(--cor); }
.nota { display:flex; align-items:center; gap:10px; margin:6px 0; font-size:15px; }
.nota .barra { flex:1; height:8px; background:var(--linha); border-radius:99px; overflow:hidden; }
.nota .barra i { display:block; height:100%; background:var(--mare); }
.sel { font-weight:700; }
.status-ok { color:var(--ok); font-weight:600; }
.status-no { color:var(--no); font-weight:600; }
div[data-testid="stButton"] > button { border-radius:8px; border:1px solid var(--linha); background:#fff; text-align:left; justify-content:flex-start; font-family:'Figtree',sans-serif; }
div[data-testid="stButton"] > button[kind="primary"] { background:var(--ok); border-color:var(--ok); color:#fff; justify-content:center; text-align:center; }
.kpi { background:#fff; border:1px solid var(--linha); border-radius:10px; padding:14px 16px; }
.kpi .n { font-family:'Bricolage Grotesque',sans-serif; font-size:30px; font-weight:700; line-height:1.1; }
.kpi .l { font-size:14px; color:#4C6577; }
.topo h1 { font-size:36px !important; font-family:'Bricolage Grotesque',sans-serif !important; font-weight:700 !important; padding:0 !important; color:var(--mare) !important; }
button[data-baseweb="tab"] p { color:var(--mare) !important; font-weight:600; font-size:16px; }
button[data-baseweb="tab"][aria-selected="false"] p { opacity:.6; }
div[data-testid="stButton"] > button:not([kind="primary"]) > div { justify-content:flex-start; width:100%; }
div[data-testid="stButton"] > button:not([kind="primary"]) p { text-align:left; width:100%; color:var(--mare); }
div[data-testid="stButton"] > button[kind="primary"] p { color:#fff; }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }
</style>
""", unsafe_allow_html=True)


# ---------- dados ----------
def carregar_campanhas() -> list[dict]:
    arq = DADOS / "campanhas.jsonl"
    if not arq.exists():
        return []
    itens = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    for it in itens:
        c, p = it["contexto"], it["push_final"] or {}
        chave = f"{c['zona']}|{c['hora']}|{','.join(c['gatilhos'])}|{p.get('titulo')}|{p.get('corpo')}"
        it["id"] = hashlib.md5(chave.encode()).hexdigest()[:10]
    return itens


def carregar_envios() -> dict:
    arq = DADOS / "envios.jsonl"
    if not arq.exists():
        return {}
    saida = {}
    for l in arq.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            saida[r["id"]] = r
    return saida


def registrar(item: dict, decisao: str) -> None:
    reg = {"id": item["id"], "decisao": decisao, "quando": datetime.now().isoformat(timespec="seconds"),
           "push": item["push_final"], "contexto": item["contexto"]}
    with open(DADOS / "envios.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def gatilho_principal(c: dict) -> str:
    return c["gatilhos"][0]


def frase(c: dict) -> str:
    nomes = " e ".join(ROTULO[g].lower() for g in c["gatilhos"])
    return f"{nomes.capitalize()} em {c['nome_zona'].split(' (')[0]}: destacar {c['categoria_nome']}"


# ---------- cabeçalho ----------
st.markdown('<div class="topo"><div class="titulo-app">Clima → Campanha</div><span>Rio de Janeiro · demanda simulada, clima real</span></div>',
            unsafe_allow_html=True)

campanhas = carregar_campanhas()
envios = carregar_envios()
aba_fila, aba_metricas = st.tabs(["Campanhas para aprovar", "Resultados"])

# ---------- aba 1: fila + detalhe ----------
with aba_fila:
    if not campanhas:
        st.info("Ainda não há campanhas. Gere algumas com: python -m src.campanha.pipeline --n 30")
    else:
        if "sel" not in st.session_state:
            st.session_state.sel = campanhas[0]["id"]
        esq, dir_ = st.columns([0.34, 0.66], gap="large")

        with esq:
            pend = sum(1 for c in campanhas if c["id"] not in envios)
            st.markdown(f"**{pend} para decidir** de {len(campanhas)}")
            for c in campanhas:
                ctx = c["contexto"]
                marca = {"aprovado": "✅", "rejeitado": "⛔"}.get(envios.get(c["id"], {}).get("decisao"), "•")
                ponto = {"calor": "🟠", "frio": "🔵", "chuva": "⚪"}[gatilho_principal(ctx)]
                rotulo = f"{marca} {ponto} {ctx['nome_zona'].split(' (')[0]} · {ctx['hora']:02d}h · {'+'.join(ctx['gatilhos'])}"
                if st.button(rotulo, key="b" + c["id"], width="stretch"):
                    st.session_state.sel = c["id"]
                    st.rerun()

        with dir_:
            item = next((c for c in campanhas if c["id"] == st.session_state.sel), campanhas[0])
            ctx, push, juiz = item["contexto"], item["push_final"], item["juiz"]
            cor = COR[gatilho_principal(ctx)]

            st.markdown(f"""<div class="faixa" style="background:{cor}">
                <div class="quando">{ctx['hora']:02d}h · {PERIODO[ctx['periodo']]} · sensação {ctx['sensacao']:.0f} °C · chuva {ctx['chuva_mm_h']:.1f} mm/h</div>
                <div class="frase">{frase(ctx)}</div></div>""", unsafe_allow_html=True)

            c1, c2 = st.columns([0.5, 0.5], gap="large")
            with c1:
                st.markdown("**Por que essa campanha**")
                st.markdown(f"""
                <div class="fato"><span>Gatilho</span><b>{' + '.join(ROTULO[g] for g in ctx['gatilhos'])}</b></div>
                <div class="fato"><span>Categoria destacada</span><b>{ctx['categoria_nome']}</b></div>
                <div class="fato"><span>Ganho estimado</span><b>+{ctx['ganho_estimado']:.0f} pedidos/h (premissa)</b></div>
                """, unsafe_allow_html=True)

                st.markdown("<div style='height:14px'></div><b>Avaliação</b>", unsafe_allow_html=True)
                if juiz:
                    for nome, k in [("Tom", "nota_tom"), ("Adequação", "nota_adequacao")]:
                        v = juiz[k]
                        st.markdown(f'<div class="nota"><span style="width:84px">{nome}</span><div class="barra"><i style="width:{v*20}%"></i></div><b>{v}/5</b></div>',
                                    unsafe_allow_html=True)
                    st.caption(juiz["motivo"])
                st.markdown(f"Regras: <span class='status-ok'>passou</span> · {item['n_tentativas']} tentativa(s) · "
                            f"{item['tempo_total_s']:.0f} s · US$ {item['custo_usd']:.4f}", unsafe_allow_html=True)

                if item["n_tentativas"] > 1:
                    with st.expander("Ver versões reprovadas"):
                        for t in item["tentativas"][:-1]:
                            motivos = t["falhas_regras"] or [t.get("juiz", {}).get("motivo", "reprovado pelo juiz")]
                            st.markdown(f"**{t['push']['titulo']}**  \n{t['push']['corpo']}")
                            st.caption("Reprovada: " + "; ".join(motivos))

            with c2:
                cupom = f'<div class="cupom">Cupom {push["cupom"]}</div>' if push["cupom"] else ""
                st.markdown(f"""<div class="celular" style="--cor:{cor}">
                    <div class="hora">{ctx['hora']:02d}:00</div>
                    <div class="push"><div class="app">Notificação do app · agora</div>
                    <div class="t">{push['titulo']}</div><div class="c">{push['corpo']}</div>{cupom}</div></div>""",
                            unsafe_allow_html=True)

            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            decisao = envios.get(item["id"])
            if decisao:
                ok = decisao["decisao"] == "aprovado"
                txt = "Aprovada. Envio simulado registrado em dados/envios.jsonl." if ok else "Rejeitada. Nada foi enviado."
                st.markdown(f"<span class='{'status-ok' if ok else 'status-no'}'>{txt}</span> ({decisao['quando'].replace('T', ' ')})",
                            unsafe_allow_html=True)
            else:
                b1, b2, _ = st.columns([0.28, 0.28, 0.44])
                if b1.button("Aprovar envio", type="primary", width="stretch"):
                    registrar(item, "aprovado"); st.rerun()
                if b2.button("Rejeitar", width="stretch"):
                    registrar(item, "rejeitado"); st.rerun()

# ---------- aba 2: resultados ----------
with aba_metricas:
    if campanhas:
        df = pd.DataFrame([{
            "aprovada": c["status"] == "aprovado_pelo_pipeline", "tentativas": c["n_tentativas"],
            "tempo": c["tempo_total_s"], "custo": c["custo_usd"], "gatilho": gatilho_principal(c["contexto"]),
        } for c in campanhas])

        k = st.columns(4)
        for col, (n, l) in zip(k, [
            (f"{df['aprovada'].mean()*100:.0f}%", f"aprovadas pelo pipeline (n={len(df)})"),
            (f"{df['tentativas'].mean():.2f}", "tentativas por campanha"),
            (f"{df['tempo'].mean():.0f} s", "tempo médio por campanha"),
            (f"US$ {df['custo'].mean():.4f}", "custo médio por campanha"),
        ]):
            col.markdown(f'<div class="kpi"><div class="n">{n}</div><div class="l">{l}</div></div>', unsafe_allow_html=True)

        st.markdown("### Tempo economizado")
        st.write("Cronometre você mesma escrevendo 3 pushes do zero (sem IA) e informe os minutos. O painel compara com o pipeline.")
        arq_t = DADOS / "tempo_manual.json"
        padrao = json.loads(arq_t.read_text())["minutos"] if arq_t.exists() else [0.0, 0.0, 0.0]
        m = st.columns(3)
        minutos = [m[i].number_input(f"Push manual {i+1} (min)", min_value=0.0, value=float(padrao[i]), step=0.5, key=f"m{i}") for i in range(3)]
        if st.button("Salvar medição"):
            arq_t.write_text(json.dumps({"minutos": minutos}))
        media_min = sum(minutos) / 3
        if media_min > 0:
            auto_min = df["tempo"].mean() / 60
            st.markdown(f"Manual: **{media_min:.1f} min** por push (n=3, medido por você). Pipeline: **{auto_min:.2f} min** por push (n={len(df)}).")
            st.markdown(f"Para 100 campanhas: **{media_min*100/60:.1f} h** contra **{auto_min*100:.0f} min** "
                        f"(cálculo, não medição; o pipeline roda sem supervisão).")

        st.markdown("### Modelo de uplift (teste em 2026)")
        arq_m = DADOS / "metricas_modelo.csv"
        if arq_m.exists():
            mm = pd.read_csv(arq_m).groupby("modelo")[["MAE", "MAE_horas_com_gatilho"]].mean().round(2)
            mm.columns = ["Erro médio geral", "Erro médio nas horas com gatilho"]
            mm.index = mm.index.map({"baseline": "Sem clima (baseline)", "modelo": "Com clima"})
            st.dataframe(mm, width="stretch")
        st.caption("A demanda é sintética: o efeito do clima foi embutido por nós. O resultado mostra que o pipeline funciona, não o efeito real no iFood.")

        arq_j = DADOS / "teste_juiz.json"
        if arq_j.exists():
            tj = json.loads(arq_j.read_text(encoding="utf-8"))
            st.markdown(f"### Teste do juiz\nAcertou **{sum(t['acertou'] for t in tj)}/{len(tj)}** casos construídos de propósito (bons e ruins). Amostra pequena, casos fáceis.")
