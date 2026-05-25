#!/usr/bin/env python3
"""
web_app.py — Interface Web para o Simulador DTN P2P

Uso:
    pip install flask
    python web_app.py
    Acesse: http://localhost:5000
"""

import os
import sys
import io
import json
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.dirname(__file__))

from simulator import DTNSimulator
from contact_manager import ContactManager

app = Flask(__name__)

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


# ─── Helpers duplicados do dtp2p.py ──────────────────────────────────────────

def _load_messages_file(sim: DTNSimulator, filepath: str, default_ttl: int):
    with open(filepath, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",", 4)]
            if len(parts) < 4:
                continue
            try:
                time    = float(parts[0])
                src     = int(parts[1])
                dst     = int(parts[2])
                ttl     = int(parts[3])
                content = parts[4] if len(parts) > 4 else f"msg-{src}->{dst}@t{time}"
                sim.schedule_send(time, src, dst, content, ttl)
            except ValueError:
                pass


def _inject_default_messages(sim: DTNSimulator, default_ttl: int):
    nodes = sorted(sim.nodes.keys())
    if len(nodes) < 2:
        return
    first, last = nodes[0], nodes[-1]
    sim.schedule_send(
        0.0, first, last,
        f"Mensagem padrão: nó {first} → nó {last}", default_ttl,
    )
    if len(nodes) >= 3:
        sim.schedule_send(
            0.0, nodes[1], nodes[0],
            f"Mensagem padrão: nó {nodes[1]} → nó {nodes[0]}", default_ttl,
        )


# ─── Rotas ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scenarios")
def list_scenarios():
    scenarios = []
    for name in ["dense", "sparse", "chain"]:
        contacts_file = SCENARIOS_DIR / f"contacts_{name}.txt"
        messages_file = SCENARIOS_DIR / f"messages_{name}.txt"
        if contacts_file.exists():
            scenarios.append({
                "name": name,
                "has_messages": messages_file.exists(),
            })
    return jsonify(scenarios)


@app.route("/api/scenario/<name>")
def get_scenario(name):
    if name not in ("dense", "sparse", "chain"):
        return jsonify({"error": "Cenário inválido"}), 400
    result = {}
    contacts_file = SCENARIOS_DIR / f"contacts_{name}.txt"
    messages_file = SCENARIOS_DIR / f"messages_{name}.txt"
    if contacts_file.exists():
        result["contacts"] = contacts_file.read_text(encoding="utf-8")
    if messages_file.exists():
        result["messages"] = messages_file.read_text(encoding="utf-8")
    return jsonify(result)


@app.route("/api/simulate", methods=["POST"])
def simulate():
    data = request.get_json(force=True)

    routing        = data.get("routing", "epidemic")
    ttl            = int(data.get("ttl", 10))
    contacts_text  = data.get("contacts", "").strip()
    messages_text  = data.get("messages", "").strip()
    extra_messages = data.get("extra_messages", [])

    if routing not in ("epidemic", "prophet"):
        return jsonify({"error": "Algoritmo inválido. Use 'epidemic' ou 'prophet'."}), 400

    if not contacts_text:
        return jsonify({"error": "O arquivo de contatos não pode estar vazio."}), 400

    contacts_path = None
    messages_path = None
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    try:
        # Escreve arquivos temporários
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as cf:
            cf.write(contacts_text)
            contacts_path = cf.name

        if messages_text:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as mf:
                mf.write(messages_text)
                messages_path = mf.name

        sim = DTNSimulator(routing=routing, verbose=True)
        cm  = ContactManager(contacts_path)
        n_contacts = cm.load_contacts(sim)

        if messages_path:
            _load_messages_file(sim, messages_path, ttl)
        else:
            _inject_default_messages(sim, ttl)

        # Mensagens extras injetadas manualmente
        for em in extra_messages:
            try:
                src     = int(em["from"])
                dst     = int(em["to"])
                content = str(em.get("content", f"extra {src}→{dst}"))
                sim.schedule_send(0.0, src, dst, content, ttl)
            except (KeyError, ValueError):
                pass

        sim.run()
        report = sim.metrics.generate_report(sim.all_messages)

    except Exception as exc:
        sys.stdout = old_stdout
        return jsonify({"error": str(exc)}), 500

    finally:
        sys.stdout = old_stdout
        for p in (contacts_path, messages_path):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    logs = captured.getvalue()

    nodes_list = [
        {
            "id": nid,
            "buffer_size": len(node.buffer),
            "delivered_count": len(node.delivered),
            "delivered_msgs": list(node.delivered.keys()),
        }
        for nid, node in sorted(sim.nodes.items())
    ]

    contacts_list = [
        {"start": s, "end": e, "a": a, "b": b}
        for s, e, a, b in sim.contact_events
    ]

    transmissions_list = [
        {
            "msg_id": tx.msg_id,
            "from": tx.from_node,
            "to": tx.to_node,
            "time": tx.time,
        }
        for tx in sim.metrics.transmissions
    ]

    messages_list = [
        {
            "msg_id": mid,
            "source": msg.source,
            "destination": msg.destination,
            "content": msg.content,
            "created_at": msg.created_at,
            "ttl": msg.ttl,
            "delivered": msg.delivered,
            "delivered_at": msg.delivered_at,
        }
        for mid, msg in sim.all_messages.items()
    ]

    prophet_table = sim.prophet_table() if routing == "prophet" else None

    # Sanitiza valores não suportados por JSON (Infinity, NaN)
    import math
    def _sanitize(obj):
        if isinstance(obj, float):
            if math.isinf(obj) or math.isnan(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(i) for i in obj]
        return obj

    report        = _sanitize(report)
    prophet_table = _sanitize(prophet_table)

    return jsonify({
        "report":         report,
        "nodes":          nodes_list,
        "contacts":       contacts_list,
        "transmissions":  transmissions_list,
        "messages":       messages_list,
        "logs":           logs,
        "prophet_table":  prophet_table,
        "n_contacts":     n_contacts,
        "routing":        routing,
    })


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  DTN P2P Simulator — Interface Web")
    print("  http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, port=5000)
