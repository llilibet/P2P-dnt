"""
contact_manager.py — Lê e agenda contatos do arquivo contacts.txt

Formato do arquivo:
    tempo_inicio, tempo_fim, noA, noB

Linhas começando com '#' são comentários e são ignoradas.

Exemplo:
    0.0, 5.0, 1, 2
    5.1, 8.0, 2, 3
    8.2, 12.0, 3, 1
"""

from typing import List, Tuple


class ContactManager:
    """Parseia um arquivo de contatos e os injeta no simulador."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.contacts: List[Tuple[float, float, int, int]] = []
        self._parse()

    def _parse(self):
        """Lê o arquivo e preenche self.contacts."""
        with open(self.filepath, encoding="utf-8") as f:
            for lineno, raw in enumerate(f, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) != 4:
                    print(
                        f"  [ContactManager] Aviso: linha {lineno} inválida "
                        f"(esperado 4 campos): '{line}'"
                    )
                    continue
                try:
                    start = float(parts[0])
                    end   = float(parts[1])
                    a     = int(parts[2])
                    b     = int(parts[3])
                    if start > end:
                        print(
                            f"  [ContactManager] Aviso: linha {lineno} — "
                            f"tempo_inicio ({start}) > tempo_fim ({end}), ignorada."
                        )
                        continue
                    if a == b:
                        print(
                            f"  [ContactManager] Aviso: linha {lineno} — "
                            f"contato de nó consigo mesmo (noA == noB = {a}), ignorada."
                        )
                        continue
                    self.contacts.append((start, end, a, b))
                except ValueError as exc:
                    print(
                        f"  [ContactManager] Aviso: linha {lineno} — "
                        f"erro de conversão: {exc}"
                    )

    def load_contacts(self, simulator) -> int:
        """
        Agenda todos os contatos lidos no simulador.
        Retorna o número de contatos agendados.
        """
        for start, end, a, b in self.contacts:
            simulator.schedule_contact(start, end, a, b)
        return len(self.contacts)
