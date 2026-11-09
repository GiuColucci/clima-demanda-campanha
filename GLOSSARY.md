# Clima → Demanda → Campanha

Sistema que, quando o clima de uma zona do Rio de Janeiro dispara um gatilho, escolhe a categoria de comida a destacar, escreve um push, avalia o texto e o entrega a uma pessoa para decidir. Projeto de portfólio: o clima é real, a demanda é simulada.

## Language

**Zona**:
Uma das 5 áreas fixas do Rio (Zona Sul, Centro, Zona Norte, Barra da Tijuca, Zona Oeste), cada uma representada por um ponto de coordenadas.
_Avoid_: Bairro, cluster, região

**Sensação térmica**:
A temperatura que a pessoa sente (`apparent_temperature`), usada no lugar da temperatura do ar para decidir os gatilhos de calor e frio.
_Avoid_: Temperatura (sem qualificar)

**Gatilho**:
Uma condição de clima que justifica uma campanha: calor forte, frio ou chuva. Cada um tem um limiar em `config.yaml`. Sem gatilho ativo, o sistema não faz nada.
_Avoid_: Alerta, evento

**Premissa**:
Um valor assumido por nós (limiar de gatilho, fator de clima, pedidos-base), e não medido. Toda premissa fica em `config.yaml`.
_Avoid_: Parâmetro, dado

**Demanda sintética**:
Pedidos inventados pela simulação, com o efeito do clima embutido por nós. Mostra que o pipeline funciona, não que o efeito é o do iFood real.
_Avoid_: Dados de pedidos, demanda real
