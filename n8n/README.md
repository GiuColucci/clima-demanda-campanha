# Fluxo n8n: Clima → Campanha

Arquivo: [`fluxo.json`](./fluxo.json). O n8n é usado como **orquestrador**: ele não tem lógica de negócio, só encadeia as etapas e chama a API do projeto.

## O que o fluxo faz

1. **Todo dia às 7h** (ou manualmente, pelo botão "Rodar agora") começa o fluxo.
2. **Config:** guarda o endereço da API (`http://127.0.0.1:8000`). É o único lugar para mudar se a porta for outra.
3. **Ler zonas e limiares:** `GET /api/zonas` devolve as 5 zonas do Rio e os limiares dos gatilhos, lidos do `config.yaml`.
4. **Previsão do tempo:** para cada zona, busca na Open-Meteo a previsão das próximas 48 h.
5. **Achar a hora crítica:** olha as próximas 24 h e escolhe, por zona, a hora que mais ultrapassa algum limiar. **Se nenhuma hora passa, a zona não gera nada** (dia normal = silêncio, sem gasto de LLM).
6. **Gerar proposta (LLM):** `POST /api/propostas` gera o push, aplica as regras e o juiz, e coloca na fila se o pipeline liberar.
7. **Resumo:** quantas propostas, quantas liberadas, custo total e os títulos.

As propostas liberadas aparecem na página (http://127.0.0.1:8000), esperando a decisão humana.

## Como rodar (n8n local, gratuito)

1. Suba a API: `uvicorn src.api.main:app --port 8000` (deixe o terminal aberto).
2. Em **outro** terminal: `npx n8n` (baixa o n8n na primeira vez). Abra http://localhost:5678 e crie a conta local que ele pedir (fica só no seu computador).
3. No n8n: menu **⋯ → Import from file** e escolha `n8n/fluxo.json`.
4. Clique em **Execute workflow**.

Use `127.0.0.1` e não `localhost`: o Node resolve `localhost` para IPv6 e o `uvicorn` escuta em IPv4.

## O que foi verificado

- Importação e execução no n8n 2.46 (via linha de comando).
- Ramo sem gatilho: com a previsão real de 09/11/2026 nenhuma zona passou dos limiares, e o fluxo terminou em silêncio.
- Ramo com gatilho: uma hora crítica (42 °C na Zona Sul) gerou uma proposta liberada, por ~US$ 0,004.
- Lógica do nó "Achar a hora crítica" testada à parte, com uma previsão inventada (3 zonas com gatilho, 1 sem).
