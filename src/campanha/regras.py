"""Regras determinísticas que um push precisa cumprir antes de ir ao juiz LLM.

validar() devolve uma lista de motivos de reprovação. Lista vazia = passou.
"""
import re

CAMPOS = ["titulo", "corpo", "cupom"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def validar(push: dict, contexto: dict, cfg: dict) -> list[str]:
    r = cfg["campanha"]["regras"]
    erros = []

    for campo in CAMPOS:
        if not isinstance(push.get(campo), str) or push.get(campo) is None:
            erros.append(f"campo '{campo}' ausente ou não é texto")
    if erros:
        return erros

    titulo, corpo, cupom = push["titulo"], push["corpo"], push["cupom"].strip()
    texto = f"{titulo} {corpo}"
    baixo = texto.lower()

    if len(titulo) > r["titulo_max_chars"]:
        erros.append(f"título com {len(titulo)} caracteres (máximo {r['titulo_max_chars']})")
    if len(corpo) > r["corpo_max_chars"]:
        erros.append(f"corpo com {len(corpo)} caracteres (máximo {r['corpo_max_chars']})")
    if len(EMOJI.findall(texto)) > r["max_emojis"]:
        erros.append(f"mais de {r['max_emojis']} emojis")

    for termo in r["termos_proibidos"]:
        if termo.lower() in baixo:
            erros.append(f"termo proibido: '{termo}'")

    # percentuais mencionados precisam estar na lista permitida (sem desconto inventado)
    for n in re.findall(r"(\d+)\s*%", texto):
        if int(n) not in r["percentuais_permitidos"]:
            erros.append(f"percentual inventado: {n}%")

    # cupom: vazio é permitido; se existir, precisa ser um dos válidos
    if cupom and cupom.upper() not in [c.upper() for c in r["cupons_validos"]]:
        erros.append(f"cupom inválido: '{cupom}'")
    if "cupom" in baixo and not cupom:
        erros.append("o texto cita cupom, mas o campo cupom está vazio")

    # coerência com o clima
    for gatilho in contexto["gatilhos"]:
        for palavra in r["incoerentes"].get(gatilho, []):
            if palavra.lower() in baixo:
                erros.append(f"palavra incoerente com {gatilho}: '{palavra}'")

    return erros
