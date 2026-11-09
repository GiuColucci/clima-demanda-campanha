# Clima → Demanda → Campanha

> Sistema que prevê como o clima muda a demanda por delivery no Rio de Janeiro e gera, com um LLM, campanhas de push personalizadas, avaliadas antes do envio.

**Status:** em construção. Este README descreve o plano; os resultados serão preenchidos conforme cada etapa for concluída.

## O problema

Dias muito frios, chuvosos ou muito quentes mudam o que e quanto as pessoas pedem. Times de CRM costumam montar campanhas por clima na mão, de forma genérica e sem medir o efeito. A ideia é automatizar o ciclo inteiro: prever a demanda, decidir quando e onde disparar e escrever a mensagem certa.

## Como funciona

```text
Clima (Open-Meteo / INMET)  ─┐
Clusters de bairros do Rio   ├─► Modelo de uplift de demanda ─► Gatilho de campanha
Demanda (simulada/calibrada) ┘                                         │
                                                                       ▼
                         LLM gera push e cupom (clima + horário + cluster + categoria)
                                                                       │
                                                                       ▼
                     Avaliação: regras + LLM-as-judge ─► aprovação humana ─► envio simulado
```

1. **Clima:** histórico e previsão por bairro/região (Open-Meteo, com INMET como alternativa).
2. **Segmentação:** clusters de bairros por vulnerabilidade ao calor, reaproveitados do projeto [`ilhas-de-calor-rio`](../ilhas-de-calor-rio).
3. **Modelo de demanda:** estima o *uplift* de pedidos por clima, cluster, horário e categoria (sopas e caldos no frio, açaí e bebidas no calor). Baseline simples comparado a gradient boosting.
4. **Geração de campanha:** um LLM escreve a mensagem a partir do contexto, com saída estruturada em JSON.
5. **Avaliação:** checagem por regras (sem promessa falsa, sem preço inventado, limite de tamanho, tom de voz) mais um LLM-as-judge. Mensagens reprovadas voltam para nova geração.
6. **Orquestração e demo:** fluxo no n8n e painel em Streamlit, com API em FastAPI expondo o modelo.

## Sobre os dados

Não existem dados públicos de pedidos do iFood. Por isso:

- **Clima:** dados reais.
- **Bairros:** dados reais do projeto `ilhas-de-calor-rio`.
- **Demanda:** **sintética**, gerada com efeitos de clima parametrizados e documentados. Os resultados mostram que o pipeline funciona, **não** que o efeito medido seja o do iFood.

## Métricas

- **Modelo:** erro de previsão (MAE/RMSE) contra o baseline.
- **Campanhas:** taxa de aprovação nas regras, nota média do juiz, taxa de alucinação.
- **Negócio (simulado):** conversão incremental contra grupo de controle, em um A/B simulado.
- **Operacional:** custo e latência por mensagem, comparando modelos pequenos e grandes.

## Estrutura planejada

```text
clima-demanda-campanha/
├── dados/            # clima, clusters, demanda sintética
├── src/
│   ├── clima/        # coleta e limpeza
│   ├── demanda/      # simulação e modelo de uplift
│   ├── campanha/     # geração com LLM e avaliação
│   └── api/          # FastAPI
├── app/              # painel Streamlit
├── n8n/              # fluxo exportado
├── notebooks/
├── requirements.txt
└── .env.example
```

## Tecnologias

Python · pandas · scikit-learn / LightGBM · LLM via API (Gemini ou Claude) · FastAPI · Streamlit · n8n · Open-Meteo

## Como rodar

```bash
git clone <url-do-repositorio>
cd clima-demanda-campanha
pip install -r requirements.txt
cp .env.example .env      # coloque sua chave de API do LLM
streamlit run app/main.py
```

## Roteiro

- [ ] Coleta de clima e junção com os clusters
- [ ] Simulação de demanda e baseline
- [ ] Modelo de uplift
- [ ] Geração de campanha com LLM
- [ ] Avaliação (regras + juiz) e métricas
- [ ] API e painel
- [ ] Fluxo no n8n
- [ ] Modelo publicado no Hugging Face e notebook no Kaggle
- [ ] Vídeo de demonstração de 2 minutos

## Limitações

- Demanda sintética: o efeito do clima é uma premissa, não uma medição.
- Correlação não é causalidade; o A/B é simulado.
- O envio das campanhas é simulado, sem usuários reais.

## Autora

Giulia Colucci · [GitHub](https://github.com/GiuColucci) · [LinkedIn](https://www.linkedin.com/in/giulia-colucci-433b30378/)
