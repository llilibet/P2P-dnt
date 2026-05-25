#!/usr/bin/env python3
"""
dtp2p.py — Simulador DTN P2P com Roteamento Epidêmico / PROPHET

Uso básico:
    # Simulação com arquivos de contatos e mensagens
    python dtp2p.py --contacts contacts.txt
    python dtp2p.py --contacts contacts.txt --messages messages.txt --ttl 8

    # Cenários pré-definidos
    python dtp2p.py --scenario dense
    python dtp2p.py --scenario sparse
    python dtp2p.py --scenario chain

    # Injetar uma mensagem específica durante a simulação
    python dtp2p.py --send --from 1 --to 4 --msg "olá" --contacts contacts.txt

    # Algoritmo PROPHET (extensão)
    python dtp2p.py --scenario chain --routing prophet

    # Salvar relatório
    python dtp2p.py --scenario dense --output relatorio.txt

    # Interface de nó (compatibilidade — modo simulação)
    python dtp2p.py --id 1 --port 5001 --contacts contacts.txt
"""

import argparse
import os
import sys

from simulator import DTNSimulator
from contact_manager import ContactManager


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_messages_file(sim: DTNSimulator, filepath: str, default_ttl: int):
    """
    Carrega mensagens de arquivo.
    Formato: tempo, src, dst, ttl, conteúdo
    Linhas com '#' são comentários.
    """
    with open(filepath, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 4)]
            if len(parts) < 4:
                print(f"  [Messages] Aviso: linha {lineno} inválida: '{line}'")
                continue
            try:
                time    = float(parts[0])
                src     = int(parts[1])
                dst     = int(parts[2])
                ttl     = int(parts[3])
                content = parts[4] if len(parts) > 4 else f"msg-{src}->{dst}@t{time}"
                sim.schedule_send(time, src, dst, content, ttl)
            except ValueError as exc:
                print(f"  [Messages] Aviso: linha {lineno} — erro: {exc}")


def inject_default_messages(sim: DTNSimulator, default_ttl: int):
    """Injeta mensagens padrão quando nenhum arquivo de mensagens é fornecido."""
    nodes = sorted(sim.nodes.keys())
    if len(nodes) < 2:
        return
    first, last = nodes[0], nodes[-1]
    sim.schedule_send(
        0.0, first, last,
        f"Mensagem padrão: nó {first} → nó {last}",
        default_ttl,
    )
    if len(nodes) >= 3:
        sim.schedule_send(
            0.0, nodes[1], nodes[0],
            f"Mensagem padrão: nó {nodes[1]} → nó {nodes[0]}",
            default_ttl,
        )


# ─── Execução da simulação ────────────────────────────────────────────────────

def run_simulation(args: argparse.Namespace):
    sim = DTNSimulator(routing=args.routing, verbose=args.verbose)

    # Carrega contatos
    cm = ContactManager(args.contacts)
    n_contacts = cm.load_contacts(sim)

    # Carrega mensagens
    if args.messages and os.path.exists(args.messages):
        load_messages_file(sim, args.messages, args.ttl)
    elif args.messages:
        print(
            f"  Aviso: arquivo de mensagens '{args.messages}' não encontrado. "
            "Usando mensagens padrão."
        )
        inject_default_messages(sim, args.ttl)
    else:
        inject_default_messages(sim, args.ttl)

    # Mensagem específica via --send
    if args.send:
        if None in (args.src, args.dst) or not args.msg:
            print("Erro: --send requer --from, --to e --msg")
            sys.exit(1)
        sim.schedule_send(0.0, args.src, args.dst, args.msg, args.ttl)

    # Cabeçalho
    sep = "=" * 55
    print(f"\n{sep}")
    print(f"  Simulador DTN P2P  —  {args.routing.upper()}")
    print(sep)
    print(f"  Nós detectados   : {sorted(sim.nodes.keys())}")
    print(f"  Contatos         : {n_contacts}")
    print(f"  TTL padrão       : {args.ttl}")
    if args.contacts:
        print(f"  Arquivo contatos : {args.contacts}")
    if args.messages and os.path.exists(str(args.messages)):
        print(f"  Arquivo mensagens: {args.messages}")
    print(f"{sep}\n")

    # Executa simulação
    sim.run()

    # Relatório
    report = sim.metrics.generate_report(sim.all_messages)
    sim.metrics.print_report(report)

    # PROPHET: exibe tabela de probabilidades
    if args.routing == "prophet":
        print(f"\n{sim.prophet_table()}")

    # Salva relatório em arquivo
    if args.output:
        sim.metrics.save_report(report, args.output)
        print(f"\n  Relatório salvo em: {args.output}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="dtp2p.py",
        description="Simulador DTN P2P — Roteamento Epidêmico / PROPHET",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Arquivos de entrada
    parser.add_argument(
        "--contacts", "-c",
        help="Arquivo de contatos (tempo_ini, tempo_fim, noA, noB)",
    )
    parser.add_argument(
        "--messages", "-m",
        help="Arquivo de mensagens (tempo, src, dst, ttl, conteúdo)",
    )

    # Parâmetros de simulação
    parser.add_argument(
        "--ttl", type=int, default=10,
        help="TTL padrão das mensagens em número de saltos (padrão: 10)",
    )
    parser.add_argument(
        "--routing", choices=["epidemic", "prophet"], default="epidemic",
        help="Algoritmo de roteamento: epidemic (padrão) ou prophet",
    )
    parser.add_argument(
        "--scenario", choices=["dense", "sparse", "chain"],
        help="Executa um cenário pré-definido (pasta scenarios/)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Salva relatório de métricas em arquivo",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Exibe informações adicionais (ex: tabela PROPHET a cada encontro)",
    )

    # Modo envio de mensagem específica
    parser.add_argument(
        "--send", action="store_true",
        help="Injeta uma mensagem específica na simulação",
    )
    parser.add_argument("--from", dest="src", type=int, help="Nó de origem (--send)")
    parser.add_argument("--to",   dest="dst", type=int, help="Nó de destino (--send)")
    parser.add_argument("--msg",  help="Conteúdo da mensagem (--send)")

    # Compatibilidade com interface de nó
    parser.add_argument("--id",   type=int, help="(Compatibilidade) ID do nó local")
    parser.add_argument("--port", type=int, help="(Compatibilidade) Porta do nó local")

    args = parser.parse_args()

    # Resolve atalho de cenário
    if args.scenario:
        base_dir = os.path.join(os.path.dirname(__file__), "scenarios")
        if not args.contacts:
            args.contacts = os.path.join(base_dir, f"contacts_{args.scenario}.txt")
        if not args.messages:
            args.messages = os.path.join(base_dir, f"messages_{args.scenario}.txt")

    # Valida entrada mínima
    if not args.contacts:
        parser.print_help()
        print(
            "\nErro: forneça --contacts <arquivo> ou --scenario <nome>",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(args.contacts):
        print(
            f"Erro: arquivo de contatos não encontrado: '{args.contacts}'",
            file=sys.stderr,
        )
        sys.exit(1)

    run_simulation(args)


if __name__ == "__main__":
    main()
