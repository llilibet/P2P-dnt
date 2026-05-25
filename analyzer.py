import os
import json

def generate_report():
    total_created = 0
    total_transmissions = 0
    unique_deliveries = {}
    
    # Varre a pasta procurando os arquivos de métricas gerados pelos nós
    for filename in os.listdir('.'):
        if filename.startswith('metrics_node_') and filename.endswith('.json'):
            with open(filename, 'r') as f:
                data = json.load(f)
                total_created += data["messages_created"]
                total_transmissions += data["transmissions_made"]
                # Consolida as entregas únicas
                for msg_id, latency in data["deliveries"].items():
                    unique_deliveries[msg_id] = latency

    delivered_count = len(unique_deliveries)
    
    # 🧮 Cálculos das Métricas solicitadas
    delivery_rate = (delivered_count / total_created * 100) if total_created > 0 else 0.0
    avg_latency = (sum(unique_deliveries.values()) / delivered_count) if delivered_count > 0 else 0.0
    overhead = (total_transmissions / delivered_count) if delivered_count > 0 else 0.0

    print("\n=============================================")
    print("      📊 RELATÓRIO DE MÉTRICAS - DTN P2P      ")
    print("=============================================")
    print(f"• Total de Mensagens Injetadas na Rede: {total_created}")
    print(f"• Total de Mensagens Entregues com Sucesso: {delivered_count}")
    print(f"• Taxa de Entrega: {delivery_rate:.2f}%")
    print(f"• Latência Média de Entrega: {avg_latency:.2f} segundos")
    print(f"• Overhead de Roteamento: {overhead:.2f}")
    print("=============================================\n")

if __name__ == "__main__":
    generate_report()