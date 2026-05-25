# DTN P2P Simulator

Simulador de **Rede Tolerante a Atrasos (DTN)** com arquitetura **P2P descentralizada**, roteamento epidêmico e extensão PROPHET.

> Trabalho Prático — Disciplina de Sistemas Distribuídos  
> Implementado em Python 3.8+ · Interface CLI e Interface Web (Flask)

---

## Sumário

- [O que é o sistema](#o-que-é-o-sistema)
- [Arquitetura](#arquitetura)
- [Requisitos e Instalação](#requisitos-e-instalação)
- [Como Inicializar](#como-inicializar)
  - [Interface Web](#interface-web-recomendado)
  - [Interface CLI](#interface-cli)
- [Cenários de Teste](#cenários-de-teste)
- [Formato dos Arquivos de Entrada](#formato-dos-arquivos-de-entrada)
- [Algoritmos de Roteamento](#algoritmos-de-roteamento)
- [Métricas Geradas](#métricas-geradas)
- [Comparação Epidêmico vs PROPHET](#comparação-epidêmico-vs-prophet)

---

## O que é o sistema

Em redes **DTN (Delay-Tolerant Network)** — como comunicação em zonas rurais, regiões de desastre ou redes interplanetárias — não há conectividade fim-a-fim garantida. Cada nó atua como um **message ferry**: armazena mensagens no seu buffer e as repassa quando encontra outro nó (**store-and-forward**).

Este simulador implementa esse modelo com **eventos discretos**: você define quando os nós se encontram (`contacts.txt`) e quais mensagens enviar (`messages.txt`), e o sistema replica o comportamento da rede.

### Conceitos implementados

| Conceito | Onde aparece |
|---|---|
| P2P descentralizado | Comunicação direta entre nós, sem servidor central |
| Store-and-forward | `buffer` persistente por nó (`node.py`) |
| Roteamento epidêmico | Troca de buffers a cada contato (`simulator.py`) |
| DTN | Conectividade intermitente controlada por `contacts.txt` |
| Relógio lógico / timestamp | `created_at` + tempo de simulação em cada evento |
| Deduplicação | Conjunto `seen` por nó evita loops e duplicatas |
| TTL (max hops) | Decrementado a cada salto; mensagem descartada ao chegar a 0 |
| Métricas de desempenho | Taxa de entrega, latência, overhead (`metrics.py`) |
| PROPHET (extensão) | Roteamento por probabilidade de encontros históricos |

---

## Arquitetura

```
tp3_distribuidos/
│
├── dtp2p.py            ← Ponto de entrada CLI (argparse)
├── web_app.py          ← Interface Web (Flask)
├── simulator.py        ← Motor de simulação de eventos discretos (heapq)
├── contact_manager.py  ← Lê contacts.txt e agenda encontros no simulador
├── node.py             ← Nó DTN: buffer, seen, delivered
├── message.py          ← Estrutura de mensagem (ID, TTL, hop_count)
├── metrics.py          ← Coleta e exibe relatório de desempenho
│
├── contacts.txt        ← Contatos de exemplo (3 nós)
│
├── scenarios/
│   ├── contacts_chain.txt   ← Cadeia 1↔2↔3↔4
│   ├── contacts_dense.txt   ← Cenário denso (5 nós)
│   ├── contacts_sparse.txt  ← Cenário esparso (5 nós)
│   ├── messages_chain.txt
│   ├── messages_dense.txt
│   └── messages_sparse.txt
│
└── templates/
    └── index.html      ← Frontend da interface web
```

### Fluxo de execução

```
contacts.txt ──► ContactManager ──► agenda eventos "contact"
messages.txt ──► load_messages  ──► agenda eventos "send"
                                          │
                                    sim.run() — fila ordenada por tempo
                                          │
                        ┌─────────────────┴─────────────────┐
                    evento "send"                    evento "contact"
                        │                                    │
               cria Message no nó de origem       nós A e B trocam buffers
                                                  (epidemic ou PROPHET)
                                                       │
                                          destino == nó receptor?
                                            ├── Sim → entrega ✓
                                            └── Não → armazena (TTL-1)
                                                          │
                                                   Relatório de métricas
```

### Como cada nó funciona

| Atributo | Tipo | Descrição |
|---|---|---|
| `node_id` | `int` | Identificador único |
| `buffer` | `dict[msg_id, Message]` | Mensagens aguardando retransmissão |
| `seen` | `set[msg_id]` | IDs já processados (evita loops) |
| `delivered` | `dict[msg_id, Message]` | Mensagens cujo destino é este nó |

---

## Requisitos e Instalação

### Requisitos

| Modo | Requisito |
|---|---|
| CLI (terminal) | Python **3.8+** — sem dependências externas |
| Interface Web | Python **3.8+** + **Flask** |

### Passo a passo

**1. Verifique a versão do Python:**

```bash
python --version
# ou
python3 --version
```

Deve ser `>= 3.8`.

**2. (Apenas para interface web) Instale o Flask:**

```bash
pip install flask
```

Ou, se usar Python 3 explicitamente:

```bash
pip3 install flask
```

**3. Acesse a pasta do projeto:**

```bash
cd tp3_distribuidos
```

Não há mais nenhuma dependência para instalar.

---

## Como Inicializar

### Interface Web (recomendado)

```bash
python web_app.py
```

Acesse no navegador: **http://localhost:5000**

A interface permite:
- Selecionar cenários pré-definidos (dense, sparse, chain)
- Escolher o algoritmo (Epidêmico ou PROPHET)
- Editar os arquivos de contatos e mensagens diretamente
- Visualizar logs, relatório de métricas e tabela PROPHET

---

### Interface CLI

#### Simulação básica com arquivo de contatos

```bash
python dtp2p.py --contacts contacts.txt
```

#### Com arquivo de mensagens personalizado e TTL

```bash
python dtp2p.py --contacts contacts.txt --messages messages.txt --ttl 8
```

#### Exemplo do enunciado — enviar mensagem do nó 1 para o nó 4

```bash
python dtp2p.py --scenario chain --send --from 1 --to 4 --msg "olá" --verbose
```

Saída esperada:
```
[1] Mensagem criada em t=0.0 → destino 4 | TTL=10
[1] Contato com 2 em t=0.0
  [1]→[2] dst=4 TTL=9 salto=1
[2] Contato com 3 em t=5.1
  [2]→[3] dst=4 TTL=8 salto=2
[3] Contato com 4 em t=10.1
[4] ✓ Mensagem ENTREGUE em t=10.1 (latência=10.1s, 3 salto(s))
```

#### Parâmetros disponíveis (CLI)

| Parâmetro | Descrição | Exemplo |
|---|---|---|
| `--contacts` | Arquivo de contatos | `--contacts contacts.txt` |
| `--messages` | Arquivo de mensagens | `--messages messages.txt` |
| `--scenario` | Cenário pré-definido | `--scenario chain` |
| `--routing` | Algoritmo de roteamento | `--routing prophet` |
| `--ttl` | TTL padrão (saltos) | `--ttl 5` |
| `--send` | Injetar mensagem avulsa | `--send --from 1 --to 4 --msg "olá"` |
| `--output` | Salvar relatório em arquivo | `--output relatorio.txt` |
| `--verbose` | Exibir detalhes de cada transmissão | `--verbose` |
| `--id` / `--port` | Compatibilidade com enunciado (ignorados) | `--id 1 --port 5001` |

---

## Cenários de Teste

### Cenário 1 — Dense (denso)

- **5 nós**, 10 contatos em sequência rápida
- Alta conectividade → múltiplos caminhos disponíveis
- **Expectativa:** taxa de entrega ≈ 100%, overhead alto, latência baixa

```bash
python dtp2p.py --scenario dense
python dtp2p.py --scenario dense --routing prophet
```

### Cenário 2 — Sparse (esparso)

- **5 nós**, apenas 4 contatos com grandes intervalos entre eles
- Baixa conectividade → alguns pares podem nunca se comunicar
- **Expectativa:** taxa de entrega reduzida, latência alta

```bash
python dtp2p.py --scenario sparse
python dtp2p.py --scenario sparse --routing prophet
```

### Cenário 3 — Chain (cadeia)

- **4 nós** em cadeia: `1 ↔ 2 ↔ 3 ↔ 4` (contatos sequenciais sem sobreposição)
- Mensagem precisa percorrer todos os saltos
- **Expectativa:** entrega garantida se TTL ≥ 3; latência = soma dos intervalos

```bash
python dtp2p.py --scenario chain
python dtp2p.py --scenario chain --routing prophet
```

### Salvar e comparar resultados

```bash
python dtp2p.py --scenario dense --routing epidemic --output relatorio_ep.txt
python dtp2p.py --scenario dense --routing prophet  --output relatorio_pr.txt
```

---

## Formato dos Arquivos de Entrada

### contacts.txt

Define **quando** dois nós estão em contato:

```
# tempo_inicio, tempo_fim, noA, noB
0.0, 5.0, 1, 2
5.1, 8.0, 2, 3
8.2, 12.0, 3, 1
```

### messages.txt

Define **quais mensagens** enviar e quando:

```
# tempo, src, dst, ttl, conteudo
0.0, 1, 4, 10, Mensagem de teste
2.5, 2, 3,  5, Alerta urgente
```

> Se `--messages` for omitido, o simulador injeta mensagens padrão automaticamente (nó menor → nó maior e vice-versa).

---

## Algoritmos de Roteamento

### Epidêmico (padrão — `--routing epidemic`)

Quando dois nós se encontram, **cada um repassa ao outro todas as mensagens que o outro ainda não viu**. Funciona como uma inundação controlada por TTL.

- **Vantagem:** alta taxa de entrega
- **Desvantagem:** overhead elevado (muitas cópias circulam)

### PROPHET (`--routing prophet`)

Mantém uma tabela de **probabilidades de entrega** `P(i → j)`:
- Sobe quando os nós `i` e `j` se encontram diretamente
- Propaga por transitividade: se A encontra B e B costuma encontrar C, A aprende sobre C
- Só encaminha se `P(receptor, destino) > P(remetente, destino)`

- **Vantagem:** menor overhead, mais seletivo
- **Desvantagem:** pode perder entregas em redes muito esparsas

---

## Métricas Geradas

Ao final de toda simulação é exibido automaticamente um relatório:

| Métrica | Descrição | Fórmula |
|---|---|---|
| Taxa de entrega | % de mensagens que chegaram ao destino | `entregues / total_enviadas` |
| Latência média | Tempo médio entre criação e entrega | `mean(delivered_at − created_at)` |
| Latência mín/máx | Melhor e pior caso | — |
| Total de transmissões | Soma de todos os repasses hop-a-hop | — |
| Overhead | Custo por entrega bem-sucedida | `total_transmissões / entregas_únicas` |

Exemplo de saída:
```
=======================================================
  RELATÓRIO DE MÉTRICAS DTN
=======================================================
  Mensagens enviadas       : 5
  Mensagens entregues      : 4
  Mensagens não entregues  : 1
  Taxa de entrega          : 80.0%
  Latência média           : 8.85s
  Latência mínima          : 5.10s
  Latência máxima          : 10.10s
  Total de transmissões    : 12
  Overhead (tx/entrega)    : 3.00
=======================================================
```

---

## Comparação Epidêmico vs PROPHET

| Métrica | Epidêmico | PROPHET |
|---|---|---|
| Taxa de entrega | Alta (inundação) | Moderada/Alta |
| Overhead | Alto | Baixo |
| Latência | Baixa | Pode ser maior |
| Complexidade por contato | O(1) | O(n) |
| Melhor cenário | Qualquer topologia | Redes com padrões de contato repetidos |
