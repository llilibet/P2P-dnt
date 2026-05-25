"""
message.py — Estrutura de mensagem DTN

Cada mensagem possui:
  - msg_id  : identificador único (UUID curto)
  - source  : nó de origem
  - destination : nó de destino
  - content : conteúdo textual
  - created_at  : timestamp de criação (tempo de simulação)
  - ttl     : saltos restantes permitidos (Time-To-Live em hops)
  - hop_count : quantos saltos a cópia percorreu
  - delivered / delivered_at : estado de entrega
"""

import uuid
import copy
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Message:
    source: int
    destination: int
    content: str
    created_at: float
    ttl: int = 10
    hop_count: int = 0
    msg_id: str = field(default_factory=lambda: "m" + str(uuid.uuid4())[:7])
    delivered: bool = False
    delivered_at: Optional[float] = None

    def can_forward(self) -> bool:
        """Retorna True se ainda há TTL para encaminhar."""
        return self.ttl > 0

    def forward_copy(self) -> "Message":
        """Cria uma cópia para encaminhamento com TTL decrementado."""
        c = copy.copy(self)
        c.ttl = self.ttl - 1
        c.hop_count = self.hop_count + 1
        return c

    def __repr__(self) -> str:
        return (
            f"Message(id={self.msg_id}, {self.source}→{self.destination}, "
            f"ttl={self.ttl}, hop={self.hop_count})"
        )
