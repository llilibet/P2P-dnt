"""
metrics.py — Coleta e relata métricas de desempenho da simulação DTN

Métricas calculadas:
  - Taxa de entrega  : mensagens entregues / total enviadas
  - Latência média   : tempo médio entre criação e entrega
  - Overhead         : total de transmissões / entregas únicas
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DeliveryRecord:
    msg_id: str
    created_at: float
    delivered_at: float
    latency: float = field(init=False)

    def __post_init__(self):
        self.latency = self.delivered_at - self.created_at


@dataclass
class TransmissionRecord:
    msg_id: str
    from_node: int
    to_node: int
    time: float


class MetricsCollector:
    def __init__(self):
        self.deliveries: Dict[str, DeliveryRecord] = {}
        self.transmissions: List[TransmissionRecord] = []

    def record_delivery(self, msg_id: str, created_at: float, delivered_at: float):
        """Registra a primeira entrega de uma mensagem."""
        if msg_id not in self.deliveries:
            self.deliveries[msg_id] = DeliveryRecord(msg_id, created_at, delivered_at)

    def record_transmission(self, msg_id: str, from_node: int, to_node: int, time: float):
        """Registra cada transmissão hop-a-hop."""
        self.transmissions.append(
            TransmissionRecord(msg_id, from_node, to_node, time)
        )

    def generate_report(self, all_messages: dict) -> dict:
        """
        Gera dicionário com todas as métricas calculadas.

        Parâmetros
        ----------
        all_messages : dict[msg_id, Message]
            Todas as mensagens injetadas na simulação.
        """
        total = len(all_messages)
        delivered = len(self.deliveries)
        delivery_rate = delivered / total if total > 0 else 0.0

        latencies = [r.latency for r in self.deliveries.values()]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        min_latency = min(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        total_tx = len(self.transmissions)
        overhead = total_tx / delivered if delivered > 0 else float("inf")

        # Transmissões por mensagem
        tx_per_msg: Dict[str, int] = {}
        for tx in self.transmissions:
            tx_per_msg[tx.msg_id] = tx_per_msg.get(tx.msg_id, 0) + 1

        return {
            "total_messages": total,
            "delivered": delivered,
            "not_delivered": total - delivered,
            "delivery_rate": delivery_rate,
            "avg_latency": avg_latency,
            "min_latency": min_latency,
            "max_latency": max_latency,
            "total_transmissions": total_tx,
            "overhead_ratio": overhead,
            "tx_per_msg": tx_per_msg,
            "delivery_details": {
                mid: {"latency": r.latency, "delivered_at": r.delivered_at}
                for mid, r in self.deliveries.items()
            },
        }

    def print_report(self, report: Optional[dict] = None):
        """Exibe o relatório formatado no terminal."""
        if report is None:
            return
        sep = "=" * 55
        print(f"\n{sep}")
        print("  RELATÓRIO DE MÉTRICAS DTN")
        print(sep)
        print(f"  Mensagens enviadas       : {report['total_messages']}")
        print(f"  Mensagens entregues      : {report['delivered']}")
        print(f"  Mensagens não entregues  : {report['not_delivered']}")
        print(f"  Taxa de entrega          : {report['delivery_rate']:.1%}")
        print(f"  Latência média           : {report['avg_latency']:.2f}s")
        print(f"  Latência mínima          : {report['min_latency']:.2f}s")
        print(f"  Latência máxima          : {report['max_latency']:.2f}s")
        print(f"  Total de transmissões    : {report['total_transmissions']}")
        print(f"  Overhead (tx/entrega)    : {report['overhead_ratio']:.2f}")

        if report["delivery_details"]:
            print(f"\n  Detalhes por mensagem:")
            for mid, d in report["delivery_details"].items():
                ntx = report["tx_per_msg"].get(mid, 0)
                print(
                    f"    {mid}  latência={d['latency']:.2f}s  "
                    f"entregue em t={d['delivered_at']:.2f}  tx={ntx}"
                )
        print(sep)

    def save_report(self, report: dict, filepath: str):
        """Salva o relatório em arquivo texto."""
        sep = "=" * 55
        lines = [
            sep,
            "  RELATÓRIO DE MÉTRICAS DTN",
            sep,
            f"  Mensagens enviadas       : {report['total_messages']}",
            f"  Mensagens entregues      : {report['delivered']}",
            f"  Mensagens não entregues  : {report['not_delivered']}",
            f"  Taxa de entrega          : {report['delivery_rate']:.4f} "
            f"({report['delivery_rate']:.1%})",
            f"  Latência média           : {report['avg_latency']:.4f}s",
            f"  Latência mínima          : {report['min_latency']:.4f}s",
            f"  Latência máxima          : {report['max_latency']:.4f}s",
            f"  Total de transmissões    : {report['total_transmissions']}",
            f"  Overhead (tx/entrega)    : {report['overhead_ratio']:.4f}",
            "",
            "  Detalhes por mensagem:",
        ]
        for mid, d in report["delivery_details"].items():
            ntx = report["tx_per_msg"].get(mid, 0)
            lines.append(
                f"    {mid}  latência={d['latency']:.4f}s  "
                f"entregue em t={d['delivered_at']:.4f}  tx={ntx}"
            )
        lines.append(sep)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
