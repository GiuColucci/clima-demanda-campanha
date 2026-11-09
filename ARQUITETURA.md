# ARQUITETURA (documento vivo)

Cresce a cada etapa. Objetivo: você conseguir explicar cada peça em entrevista.

## Visão geral

clima (Open-Meteo) → gatilho (calor / frio / chuva) → categoria a destacar → push (LLM) → regras + juiz → aprovação humana → envio simulado

Em dia normal (nenhum gatilho), o sistema não faz nada.

## Etapa 1: clima e zonas (feita)

**O que existe**
- `config.yaml`: 5 zonas do Rio (com coordenadas, distância do mar e altitude aproximadas), limiares dos gatilhos e parâmetros da coleta. Todas as premissas ficam aqui.
- `src/clima/coleta.py`: baixa o clima por hora de cada zona na API histórica da Open-Meteo e grava `dados/clima.csv`.

**Decisões e porquês**
- *Zonas fixas em vez de clusters estatísticos:* 5 zonas são fáceis de explicar, e k-means em 5 pontos não agregaria informação.
- *Sensação térmica (`apparent_temperature`) em vez de temperatura:* é o que a pessoa sente, e o seu exemplo de campanha ("sorvete pra esse calor") parte dela.
- *Config em YAML:* limiares são premissas, ficam visíveis e editáveis sem mexer no código.
- *Fim da coleta = hoje − 7 dias:* a API histórica tem atraso. A previsão (próximas 48h) vem de outra API e entra mais adiante.

**Perguntas de entrevista que você deve conseguir responder**
- Por que sensação térmica e não temperatura?
- Por que 5 zonas fixas?
- De onde vêm os dados de clima e quanto histórico você tem?
- Onde ficam os limiares dos gatilhos e por que são premissas?

## Resultado da coleta (2024-01-01 a 2026-11-02)

124.440 linhas (5 zonas × 24.888 horas), sem valores faltantes.

Quanto do tempo cada gatilho dispararia com os limiares atuais:

| Gatilho | Regra | Horas |
|---|---|---|
| Calor | sensação ≥ 38 °C | 2,0% |
| Frio | sensação ≤ 17 °C | 2,2% |
| Chuva | ≥ 2 mm/h | 1,46% |

Decisão: o limiar de chuva começou em 5 mm/h, que disparava em só 0,27% das horas (chuva muito forte, rara). Foi baixado para 2 mm/h (chuva moderada a forte), que dispara em 1,46%.

## Etapa 2: demanda sintética e modelo de uplift (feita)

**O que existe**
- `config.yaml` (seção `demanda`): pedidos-base por período e categoria, volume e sensibilidade de cada zona, efeito do dia da semana e os **fatores de clima "verdadeiros"** (as premissas validadas no protótipo).
- `src/demanda/simulacao.py`: para cada hora, zona e categoria sorteia os pedidos de uma distribuição de Poisson cuja média é `base × volume da zona × dia da semana × fator de clima`. Semente fixa (42), então o resultado se repete. Saída: `dados/demanda.csv` (622.200 linhas).
- `src/demanda/modelo.py`: uma regressão de Poisson por categoria, com zona, período, dia da semana e as flags calor/frio/chuva. `exp(coeficiente)` é o fator de uplift estimado. Saída: `dados/metricas_modelo.csv` e `dados/fatores_estimados.csv`.

**Decisões e porquês**
- *Poisson:* pedidos são contagens (0, 1, 2…), e Poisson é a distribuição natural para isso.
- *Fatores multiplicam quando dois gatilhos ocorrem:* é a regra mais simples, validada no protótipo.
- *Validação temporal:* treino até 31/12/2025 e teste em 2026, porque na vida real prevemos o futuro, não um embaralhado do passado.
- *Baseline = o mesmo modelo sem as flags de clima:* assim a única diferença entre os dois é o clima.

**Resultado (teste em 2026)**

| | Baseline (sem clima) | Modelo (com clima) |
|---|---|---|
| MAE geral | 3,56 | 3,35 |
| RMSE geral | 4,98 | 4,50 |
| MAE só nas horas com gatilho | 7,52 | 3,69 |

O ganho aparece nas horas em que algum gatilho está ativo (erro cai ~51%). No geral ele é pequeno (~6%), porque só ~5% das horas têm gatilho.

**O que o modelo recuperou:** os fatores estimados ficam muito próximos dos configurados (exemplo: sorvete no calor 1,87 contra 1,80; sopas no frio 1,75 contra 1,70). Isso mostra que o pipeline funciona. **Não** mostra nada sobre o comportamento real do iFood, porque o efeito foi embutido por nós. A estimativa fica um pouco acima porque a sensibilidade das zonas (k) varia entre 0,9 e 1,2, e o modelo estima uma média única.

**Perguntas de entrevista**
- Por que Poisson e não regressão linear?
- Por que treino e teste separados por data?
- O que o baseline representa e por que o ganho geral é pequeno?
- Como você sabe que o modelo "acertou" se os dados são sintéticos?
- Qual é a limitação principal? (O efeito do clima é premissa.)

## Etapa 3: geração, regras e juiz (código pronto; falta rodar com a chave)

**Fluxo de uma campanha** (`src/campanha/pipeline.py`):
`decidir` → `gerar` (LLM) → `validar` (regras) → `avaliar` (juiz LLM) → se reprovar, volta ao gerador com o motivo (até 2 vezes)

**Arquivos**
- `decisao.py`: decide se há gatilho e qual categoria destacar (maior ganho = pedidos-base × (fator − 1)). Sem IA.
- `regras.py`: checagens determinísticas: tamanho, emojis, termos proibidos (frete grátis, R$), percentual e cupom inventados, palavras incoerentes com o clima (sopa no calor).
- `gerador.py`: prompt do gerador. Pede JSON `{titulo, corpo, cupom}` em português informal.
- `juiz.py`: prompt do juiz. Notas de 1 a 5 para tom e adequação, mais um alerta de alucinação.
- `llm.py`: chamada à OpenRouter, com medição de tempo e custo e **teto de gasto** (`dados/gasto_llm.json`). Para quando passa de US$ 2.
- `pipeline.py`: encadeia tudo, sorteia momentos reais do histórico em que algum gatilho disparou e grava `dados/campanhas.jsonl`.

**Modelos (preços da OpenRouter em 09/11/2026, por milhão de tokens)**
- Gerador: `anthropic/claude-haiku-5.5` (US$ 0,10 entrada / 0,50 saída).
- Comparação "grande": `anthropic/claude-sonnet-5.5` (US$ 2 / 10), só para medir custo e latência.
- Juiz: `google/gemini-3.6-flash` (US$ 0,75 / 3,75). É de outra família que o gerador, para ele não elogiar o próprio estilo.

**Decisões e porquês**
- *Regras antes do juiz:* barato, previsível e pega erros objetivos. O juiz (que custa dinheiro) só vê o que passou.
- *Regeneração com o motivo da reprovação:* o gerador sabe o que corrigir, em vez de tentar às cegas.
- *Cupom e percentual de uma lista fechada:* o LLM não pode inventar desconto.
- *Teto de gasto no código:* um erro em loop não esvazia o crédito.

**Primeira rodada real (3 campanhas, 09/11/2026):** as 3 foram aprovadas na primeira tentativa, em ~9 s cada e ~US$ 0,003 por campanha. O juiz deu nota 5 em tudo, o que é desconfortável: um juiz que nunca reprova não prova nada. Falta testá-lo com pushes ruins de propósito.
**Bug encontrado e corrigido:** o juiz (Gemini) gastava parte de `max_tokens` "pensando" e a resposta saía cortada no meio do JSON. Solução: limite maior para o juiz (3000) e erro explícito quando `finish_reason` é `length`.

**Teste do juiz (`src/campanha/teste_juiz.py`):** 2 pushes bons e 7 ruins de propósito (tom robótico, exagerado, desconto inventado, promessa de prazo, ignora o clima, categoria errada, em inglês). O juiz acertou **9/9**: aprovou os 2 bons e reprovou os 7 ruins. Limites: são casos fáceis e a amostra é pequena (n=9), então isso mostra que o juiz distingue o óbvio, não que seja calibrado nos casos de fronteira. Um detalhe: ele marcou `alucinacao=True` no texto robótico, que não inventa nada; o critério de alucinação do prompt pode ser mais preciso.

**Testado offline** (com um LLM de mentira): a regra reprovou o primeiro texto ("sopa quentinha pro calor, frete grátis"), o gerador regenerou com o motivo, e o segundo texto foi aprovado. **Ainda não rodou com o LLM real**: falta a chave no `.env`.

**Perguntas de entrevista**
- Por que regras antes do juiz?
- Por que o juiz é de outra família?
- Como você evita que o LLM invente desconto?
- O que acontece se o gerador sempre reprovar? (Depois de 2 regenerações a campanha fica `reprovado` e não é enviada.)
- Como você limita o gasto?

## Etapa 4: front web e API (feita)

O primeiro painel foi feito em Streamlit e foi substituído: o visual ficava limitado ao que o Streamlit permite, e a tela não era responsiva. Agora há uma **API FastAPI** e uma **página HTML própria**.

**Rodar:** `uvicorn src.api.main:app --port 8000` e abrir http://localhost:8000

**API** (`src/api/main.py`)
- `GET /api/campanhas`: lista as campanhas, com a decisão humana de cada uma.
- `POST /api/campanhas/{id}/decisao`: registra aprovar ou rejeitar em `dados/envios.jsonl` (o envio é só esse registro).
- `GET /api/resultados` e `POST /api/tempo`: números do pipeline e a medição de tempo manual.
- É a mesma API que o n8n vai chamar na etapa seguinte.

**Página** (`app/web/index.html`, um arquivo só, sem framework)
- Cores inspiradas no iFood (vermelho `#EA1D2C`, grafite, verde de aprovação), sem logo, e um aviso de projeto independente no rodapé.
- Desktop: fila à esquerda e detalhe à direita, com a prévia do push num celular.
- Celular (até 900 px): a fila vira uma tela, o detalhe abre por cima com "Voltar", e Aprovar/Rejeitar ficam fixos no rodapé.
- Aba **Resultados**: métricas do pipeline, modelo de uplift, teste do juiz e o campo de **tempo economizado**.

**Lote real (30 campanhas):** 30/30 aprovadas pelo pipeline, 1,10 tentativa por campanha, ~10 s e ~US$ 0,0033 cada.
**Ressalva:** 100% de aprovação com um juiz que acertou 9/9 em casos fáceis é um bom sinal, mas a aprovação final é humana.
**Bug corrigido:** o gerador (Haiku) também gastava tokens "pensando" e uma resposta saiu cortada. Limite subiu para 2000, e o lote registra o erro e continua.

**Perguntas de entrevista**
- Por que trocar o Streamlit por uma API + página própria?
- Como a página funciona no celular?
- O que a API faz quando o n8n chamar?

## Etapa 5: orquestração com n8n (feita)

**Arquivos:** `n8n/fluxo.json` (importável) e `n8n/README.md` (como rodar). O n8n usado é a versão **local e gratuita** (`npx n8n`); o n8n Cloud é pago após o período de teste.

**Fluxo:** agendamento diário → lê zonas e limiares da API → busca a previsão (Open-Meteo) de cada zona → escolhe a hora mais crítica nas próximas 24 h → chama `POST /api/propostas` → resumo. Se nenhuma hora dispara gatilho, o fluxo termina em silêncio, sem gastar LLM.

**Decisões e porquês**
- *O n8n não tem regra de negócio:* limiares e zonas vêm da API (`config.yaml` continua sendo a única fonte), e o pipeline roda no Python. O n8n só orquestra.
- *No máximo uma proposta por zona por dia:* limita o custo (≤ 5 chamadas de LLM por execução).
- *Só propostas liberadas entram na fila:* o que o pipeline barra não chega a uma pessoa.
- *`127.0.0.1` em vez de `localhost`:* o Node resolve `localhost` para IPv6 e o `uvicorn` escuta em IPv4. Foi o primeiro erro do teste.

**Perguntas de entrevista**
- Por que o n8n e não só um script agendado?
- Onde fica a lógica de negócio e por quê?
- O que acontece num dia sem gatilho? E quanto custa uma execução no pior caso?

## Próximas etapas
6. README, vídeo, medição de tempo
