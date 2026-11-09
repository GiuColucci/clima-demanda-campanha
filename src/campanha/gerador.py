"""Gera o push com o LLM a partir do contexto de clima. Saída: JSON {titulo, corpo, cupom}."""
from src.campanha import llm

SISTEMA = """Você escreve notificações push de um app de delivery de comida no Rio de Janeiro.
Tom: informal, simpático, carioca sem exagero, direto. Português do Brasil.
Regras obrigatórias:
- titulo: até {titulo_max} caracteres. corpo: até {corpo_max} caracteres.
- No máximo {emojis} emojis no total.
- Mencione o clima de forma natural e destaque a categoria de comida indicada.
- NÃO invente preços, prazos, promoções ou frete grátis.
- Cupom: use exatamente "CLIMA10" (10% de desconto) ou deixe o campo vazio "".
  Se citar o cupom no texto, preencha o campo cupom.
Responda SOMENTE com um JSON: {{"titulo": "...", "corpo": "...", "cupom": "..."}}"""

SITUACAO = {
    "calor": "calor forte (sensação térmica de {sensacao:.0f} °C)",
    "frio": "frio (sensação térmica de {sensacao:.0f} °C)",
    "chuva": "chuva ({chuva_mm_h:.1f} mm/h)",
}


def montar_usuario(ctx: dict, erros_anteriores: list[str] | None) -> str:
    clima = " e ".join(SITUACAO[g].format(**ctx) for g in ctx["gatilhos"])
    partes = [
        f"Região: {ctx['nome_zona']}",
        f"Horário: {ctx['hora']:02d}h",
        f"Clima: {clima}",
        f"Categoria a destacar: {ctx['categoria_nome']}",
    ]
    if erros_anteriores:
        partes.append("A versão anterior foi reprovada pelos motivos abaixo. Corrija todos:\n- "
                      + "\n- ".join(erros_anteriores))
    return "\n".join(partes)


def gerar(ctx: dict, cfg: dict, modelo: str | None = None, erros_anteriores: list[str] | None = None) -> dict:
    r = cfg["campanha"]["regras"]
    sistema = SISTEMA.format(titulo_max=r["titulo_max_chars"], corpo_max=r["corpo_max_chars"],
                             emojis=r["max_emojis"])
    modelo = modelo or cfg["campanha"]["modelo_gerador"]
    res = llm.chamar(modelo, sistema, montar_usuario(ctx, erros_anteriores), cfg, temperatura=0.8, max_tokens=2000)
    res["push"] = res.pop("json")
    res["modelo"] = modelo
    return res
