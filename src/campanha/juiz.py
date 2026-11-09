"""LLM-as-judge: avalia tom e adequação do push. Usa um modelo de OUTRA família que o gerador."""
from src.campanha import llm

SISTEMA = """Você é um revisor de comunicação de um app de delivery no Brasil.
Avalie a notificação push abaixo, dado o contexto de clima. Seja rigoroso e honesto.
Critérios (nota de 1 a 5, 5 = excelente):
- nota_tom: informal, simpático, natural em português do Brasil, sem soar robótico ou exagerado.
- nota_adequacao: coerente com o clima, a hora e a categoria destacada; chamativa e clara.
- alucinacao: true se o texto afirma algo que não está no contexto (preço, prazo, promoção, frete grátis, desconto diferente de 10%).
Responda SOMENTE com um JSON:
{"nota_tom": 1-5, "nota_adequacao": 1-5, "alucinacao": true|false, "motivo": "uma frase curta"}"""


def avaliar(push: dict, ctx: dict, cfg: dict) -> dict:
    usuario = (
        f"Contexto: {ctx['nome_zona']}, {ctx['hora']:02d}h, gatilhos: {', '.join(ctx['gatilhos'])}, "
        f"sensação térmica {ctx['sensacao']:.0f} °C, chuva {ctx['chuva_mm_h']:.1f} mm/h, "
        f"categoria destacada: {ctx['categoria_nome']}.\n"
        f"Push:\n- título: {push['titulo']}\n- corpo: {push['corpo']}\n- cupom: {push['cupom'] or '(nenhum)'}"
    )
    modelo = cfg["campanha"]["modelo_juiz"]
    res = llm.chamar(modelo, SISTEMA, usuario, cfg, temperatura=0.0, max_tokens=3000)
    veredito = res.pop("json")
    minima = cfg["campanha"]["nota_minima_juiz"]
    veredito["aprovado"] = (
        veredito["nota_tom"] >= minima and veredito["nota_adequacao"] >= minima
        and not veredito["alucinacao"]
    )
    res["veredito"] = veredito
    res["modelo"] = modelo
    return res
