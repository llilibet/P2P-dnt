"""
simulator.py — Motor de Simulação de Eventos Discretos para DTN

Gerencia uma fila de eventos ordenada por tempo e processa:
  - 'send'    : criação de mensagem em um nó de origem
  - 'contact' : encontro entre dois nós → troca epidêmica (ou PROPHET)

Algoritmos de roteamento suportados:
  epidemic — inunda cópias para todos os nós encontrados (store-and-forward puro)
  prophet  — encaminha apenas quando o receptor tem maior probabilidade de
             entregar ao destino (baseado em encontros históricos)
"""

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from message import Message
from node import DTNNode
from metrics import MetricsCollector


# ─── Evento de simulação ────────────────────────────────────────────────────

@dataclass(order=True)
class SimEvent:
    time: float
    priority: int                   # 0 = send (primeiro), 1 = contact (depois)
    seq: int                        # desempate determinístico
    event_type: str = field(compare=False)
    data: dict = field(compare=False)


# ─── Simulador principal ─────────────────────────────────────────────────────

class DTNSimulator:
    """Simulador de eventos discretos para DTN P2P."""

    # Constantes PROPHET
    PROPHET_PINIT = 0.75
    PROPHET_BETA  = 0.25
    PROPHET_GAMMA = 0.98   # aging (não aplicado nesta versão discreta)

    def __init__(self, routing: str = "epidemic", verbose: bool = False):
        self.nodes: Dict[int, DTNNode] = {}
        self._queue: List[SimEvent] = []
        self._seq: int = 0
        self.current_time: float = 0.0
        self.routing = routing
        self.verbose = verbose

        self.metrics = MetricsCollector()
        self.all_messages: Dict[str, Message] = {}
        self.contact_events: List[Tuple[float, float, int, int]] = []

        # PROPHET: probabilidades de entrega predita
        # _dp[node_i][node_j] = P(i entregará mensagens para j)
        self._dp: Dict[int, Dict[int, float]] = {}

    # ── Fila de eventos ──────────────────────────────────────────────────────

    def _push(self, time: float, etype: str, data: dict):
        # "send" (priority=0) sempre antes de "contact" (priority=1) no mesmo instante,
        # garantindo que mensagens estejam nos buffers quando os contatos ocorrem.
        priority = 0 if etype == "send" else 1
        self._seq += 1
        heapq.heappush(self._queue, SimEvent(time, priority, self._seq, etype, data))

    # ── Gerência de nós ──────────────────────────────────────────────────────

    def add_node(self, node_id: int):
        if node_id not in self.nodes:
            self.nodes[node_id] = DTNNode(node_id)
            self._dp[node_id] = {}

    # ── API de agendamento ───────────────────────────────────────────────────

    def schedule_contact(self, start: float, end: float, node_a: int, node_b: int):
        """Agenda um contato entre dois nós em t=start."""
        self.add_node(node_a)
        self.add_node(node_b)
        self.contact_events.append((start, end, node_a, node_b))
        self._push(start, "contact", {"a": node_a, "b": node_b})

    def schedule_send(self, time: float, src: int, dst: int, content: str, ttl: int):
        """Agenda a criação de uma mensagem em t=time."""
        self.add_node(src)
        self.add_node(dst)
        self._push(time, "send", {
            "src": src, "dst": dst, "content": content, "ttl": ttl
        })

    def send_message(self, src: int, dst: int, content: str, ttl: int = 10):
        """Injeta uma mensagem imediatamente (no tempo atual)."""
        self.schedule_send(self.current_time, src, dst, content, ttl)

    # ── Loop principal ───────────────────────────────────────────────────────

    def run(self):
        """Executa todos os eventos em ordem cronológica."""
        while self._queue:
            ev = heapq.heappop(self._queue)
            self.current_time = ev.time
            if ev.event_type == "contact":
                self._on_contact(ev.data)
            elif ev.event_type == "send":
                self._on_send(ev.data)

    # ── Handlers de eventos ──────────────────────────────────────────────────

    def _on_send(self, d: dict):
        """Cria e armazena uma mensagem no nó de origem."""
        src, dst = d["src"], d["dst"]
        msg = Message(
            source=src,
            destination=dst,
            content=d["content"],
            created_at=self.current_time,
            ttl=d["ttl"],
        )
        self.all_messages[msg.msg_id] = msg

        if src == dst:
            # Auto-entrega trivial
            msg.delivered = True
            msg.delivered_at = self.current_time
            self.metrics.record_delivery(msg.msg_id, msg.created_at, self.current_time)
            print(f"[{src}] Mensagem {msg.msg_id} auto-entregue em t={self.current_time:.1f}")
            return

        self.nodes[src].store(msg)
        print(
            f"[{src}] Mensagem {msg.msg_id} criada em t={self.current_time:.1f} "
            f"→ destino {dst} | TTL={msg.ttl}"
        )

    def _on_contact(self, d: dict):
        """
        Processa um encontro entre nós A e B:
          1. Troca simultânea de resumos (IDs de mensagens)
          2. Transferência das mensagens que o outro não possui
        """
        a_id, b_id = d["a"], d["b"]
        if a_id not in self.nodes or b_id not in self.nodes:
            return

        print(f"[{a_id}] Contato com {b_id} em t={self.current_time:.1f}")

        # Atualiza probabilidades PROPHET antes da seleção
        if self.routing == "prophet":
            self._prophet_update(a_id, b_id)

        node_a = self.nodes[a_id]
        node_b = self.nodes[b_id]

        # Instantâneo simultâneo dos buffers (evita auto-feedback)
        buf_a = dict(node_a.buffer)
        buf_b = dict(node_b.buffer)

        if self.routing == "epidemic":
            to_b = [m for mid, m in buf_a.items() if mid not in node_b.seen]
            to_a = [m for mid, m in buf_b.items() if mid not in node_a.seen]
        else:  # prophet
            to_b = self._prophet_select(a_id, b_id, buf_a, node_b.seen)
            to_a = self._prophet_select(b_id, a_id, buf_b, node_a.seen)

        # Transferências A → B
        for msg in to_b:
            self._transfer(msg, a_id, b_id, node_b)

        # Transferências B → A
        for msg in to_a:
            self._transfer(msg, b_id, a_id, node_a)

    # ── Transferência de mensagem ─────────────────────────────────────────────

    def _transfer(self, msg: Message, from_id: int, to_id: int, to_node: DTNNode):
        """
        Encaminha uma cópia de msg de from_id para to_node.
        - Se to_id é o destino → entrega.
        - Se TTL da cópia > 0  → armazena no buffer de to_node.
        - Se TTL da cópia = 0  → descarta sem poluir o conjunto 'seen'.
        """
        if not msg.can_forward():
            return  # TTL esgotado, não encaminha

        fwd = msg.forward_copy()  # ttl = msg.ttl - 1
        self.metrics.record_transmission(msg.msg_id, from_id, to_id, self.current_time)

        if fwd.destination == to_id:
            # ── Entrega ──────────────────────────────────────────────────────
            to_node.seen.add(fwd.msg_id)
            to_node.delivered[fwd.msg_id] = fwd
            orig = self.all_messages.get(fwd.msg_id)
            if orig and not orig.delivered:
                orig.delivered = True
                orig.delivered_at = self.current_time
                latency = self.current_time - orig.created_at
                self.metrics.record_delivery(
                    fwd.msg_id, orig.created_at, self.current_time
                )
                print(
                    f"[{to_id}] ✓ Mensagem {fwd.msg_id} ENTREGUE "
                    f"em t={self.current_time:.1f} "
                    f"(latência={latency:.1f}s, {fwd.hop_count} salto(s))"
                )

        elif fwd.ttl > 0:
            # ── Armazena para retransmissão ───────────────────────────────────
            added = to_node.store(fwd)
            if added:
                print(
                    f"  [{from_id}]→[{to_id}] {fwd.msg_id} "
                    f"dst={fwd.destination} TTL={fwd.ttl} salto={fwd.hop_count}"
                )
        # else: TTL=0 em nó intermediário → descarta silenciosamente

    # ── PROPHET ──────────────────────────────────────────────────────────────

    def _prophet_update(self, a: int, b: int):
        """
        Atualiza as probabilidades de entrega predita ao encontrar nós A e B.
        Implementa: encontro direto + transitividade (Lindgren et al.).
        """
        p_ab_old = self._dp[a].get(b, 0.0)
        p_ba_old = self._dp[b].get(a, 0.0)

        # Encontro direto
        p_ab_new = p_ab_old + (1 - p_ab_old) * self.PROPHET_PINIT
        p_ba_new = p_ba_old + (1 - p_ba_old) * self.PROPHET_PINIT

        # Instantâneo das probabilidades antigas para transitividade
        old_a = dict(self._dp[a])
        old_b = dict(self._dp[b])

        # Transitividade: A aprende sobre C através de B e vice-versa
        for c in list(self.nodes.keys()):
            if c in (a, b):
                continue
            p_bc = old_b.get(c, 0.0)
            p_ac = old_a.get(c, 0.0)
            self._dp[a][c] = p_ac + (1 - p_ac) * p_ab_new * p_bc * self.PROPHET_BETA
            self._dp[b][c] = p_bc + (1 - p_bc) * p_ba_new * p_ac * self.PROPHET_BETA

        self._dp[a][b] = p_ab_new
        self._dp[b][a] = p_ba_new

        if self.verbose:
            print(
                f"  [PROPHET] P({a},{b})={p_ab_new:.3f}  "
                f"P({b},{a})={p_ba_new:.3f}"
            )

    def _prophet_select(
        self,
        sender_id: int,
        receiver_id: int,
        sender_buf: dict,
        receiver_seen: set,
    ) -> List[Message]:
        """
        Seleciona mensagens a encaminhar conforme PROPHET:
          - Sempre encaminha se o receptor É o destino.
          - Encaminha se P(receptor, destino) > P(remetente, destino).
        """
        selected = []
        for mid, msg in sender_buf.items():
            if mid in receiver_seen:
                continue
            dst = msg.destination
            if dst == receiver_id:
                selected.append(msg)
            else:
                p_sender = self._dp[sender_id].get(dst, 0.0)
                p_receiver = self._dp[receiver_id].get(dst, 0.0)
                if p_receiver > p_sender:
                    selected.append(msg)
        return selected

    # ── Utilitários ───────────────────────────────────────────────────────────

    def prophet_table(self) -> str:
        """Retorna tabela formatada de probabilidades PROPHET."""
        nodes = sorted(self.nodes.keys())
        lines = ["Tabela PROPHET (probabilidades de entrega):"]
        header = "      " + "".join(f"  N{n:<3}" for n in nodes)
        lines.append(header)
        for a in nodes:
            row = f"  N{a:<3} "
            for b in nodes:
                if a == b:
                    row += "  --- "
                else:
                    p = self._dp[a].get(b, 0.0)
                    row += f" {p:.2f} "
            lines.append(row)
        return "\n".join(lines)
