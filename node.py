"""
node.py — Nó DTN (Delay-Tolerant Network)

Cada nó possui:
  - node_id  : identificador único
  - buffer   : mensagens armazenadas para retransmissão (store-and-forward)
  - seen     : IDs de todas as mensagens já processadas (evita loops/duplicatas)
  - delivered: mensagens entregues neste nó (ele é o destino)
"""

from typing import Dict, Set
from message import Message


class DTNNode:
    def __init__(self, node_id: int):
        self.node_id: int = node_id
        self.buffer: Dict[str, Message] = {}    # msg_id → Message (para retransmitir)
        self.seen: Set[str] = set()              # IDs já vistos (deduplicação)
        self.delivered: Dict[str, Message] = {} # msg_id → Message (entregues aqui)

    def store(self, msg: Message) -> bool:
        """
        Armazena a mensagem no buffer para retransmissão futura.
        Retorna True se a mensagem é nova (não vista antes).
        O chamador deve garantir que msg.ttl > 0 antes de chamar este método.
        """
        if msg.msg_id in self.seen:
            return False
        self.seen.add(msg.msg_id)
        self.buffer[msg.msg_id] = msg
        return True

    def remove_from_buffer(self, msg_id: str):
        """Remove mensagem do buffer (ex: após entrega confirmada com ACK)."""
        self.buffer.pop(msg_id, None)

    def __repr__(self) -> str:
        return (
            f"DTNNode(id={self.node_id}, "
            f"buffer={len(self.buffer)}, "
            f"delivered={len(self.delivered)})"
        )
