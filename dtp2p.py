import argparse
import json
import time
import socket
import threading
import sys

class DTNNode:
    def __init__(self, node_id, port, contacts_file, topology_file="topology.json"):
        self.node_id = str(node_id)
        self.port = int(port)
        self.contacts_file = contacts_file
        
        # 📦 Estruturas DTN exigidas pela atividade
        self.buffer = {}            # Armazena as mensagens: {msg_id: {to, msg, ttl, timestamp}}
        self.seen_messages = set()   # Lista de IDs vistos para evitar loops infinitos
        self.topology = {}
        
        # ⏱️ Controle de tempo da simulação (Relógio lógico relativo)
        self.start_time = time.time()
        
        # 📈 Contadores para Métricas do Relatório
        self.sent_count = 0          # Quantas mensagens ESSE nó gerou originalmente
        self.forward_count = 0       # Quantas vezes ele transmitiu algo para outro nó
        self.delivered_messages = {} # {msg_id: latência} (Apenas se o destino for ele mesmo)
        
        # Carrega o mapa de IPs e Portas
        self.load_topology(topology_file)
        
        # 🔌 Inicializa o Socket UDP real para escuta
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.port))
        
    def load_topology(self, filename):
        try:
            with open(filename, 'r') as f:
                self.topology = json.load(f)
            print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Topologia carregada com sucesso.")
        except FileNotFoundError:
            print(f"[Erro] Arquivo de topologia {filename} não encontrado!")
            sys.exit(1)

    def get_current_sim_time(self):
        # Retorna os segundos decorridos desde que o nó iniciou (ex: 14.2)
        return round(time.time() - self.start_time, 1)

    def get_timestamp_str(self):
        # Formata o tempo para o log exigido no enunciado: t=14.2
        return f"t={self.get_current_sim_time()}"

    def get_active_contacts(self):
        """Varre o arquivo contacts.txt e descobre quem está no alcance agora"""
        current_t = self.get_current_sim_time()
        active = []
        try:
            with open(self.contacts_file, 'r') as f:
                for line in f:
                    if not line.strip(): continue
                    t_start, t_end, noA, noB = line.strip().split(',')
                    noA, noB = noA.strip(), noB.strip()
                    
                    if float(t_start) <= current_t <= float(t_end):
                        if self.node_id == noA and noB not in active:
                            active.append(noB)
                        elif self.node_id == noB and noA not in active:
                            active.append(noA)
        except Exception as e:
            print(f"Erro ao ler contatos: {e}")
        return active

    def send_udp_packet(self, dest_id, packet):
        """Envia um pacote JSON real via rede para um nó específico"""
        if dest_id not in self.topology: return
        dest_info = self.topology[dest_id]
        try:
            data = json.dumps(packet).encode('utf-8')
            self.sock.sendto(data, (dest_info["ip"], dest_info["port"]))
        except Exception as e:
            pass

    def receive_handler(self):
        """Thread que fica escutando a rede e processando pacotes em segundo plano"""
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                packet = json.loads(data.decode('utf-8'))
                p_type = packet.get("type")
                sender = packet.get("from")
                
                # 1. Comando de injeção manual (--send)
                if p_type == "INJECT":
                    msg_id = f"m_{int(time.time()*1000)}"
                    self.buffer[msg_id] = {
                        "to": str(packet["to"]),
                        "msg": packet["msg"],
                        "ttl": 4,
                        "timestamp": self.get_current_sim_time()
                    }
                    self.seen_messages.add(msg_id)
                    self.sent_count += 1  # Conta que criamos uma nova mensagem
                    print(f"\n[{self.get_timestamp_str()}] [Nó {self.node_id}] Nova mensagem na rede para o destino {packet['to']}: '{packet['msg']}'")
                
                # 2. Requisição de Vetor de Resumo (Epidemic Routing)
                elif p_type == "SUMMARY_REQ":
                    response = {
                        "type": "SUMMARY_RESP",
                        "from": self.node_id,
                        "vector": list(self.buffer.keys())
                    }
                    self.send_udp_packet(sender, response)

                # 3. Resposta do Vetor de Resumo (Comparação de Buffers)
                elif p_type == "SUMMARY_RESP":
                    peer_vector = packet.get("vector", [])
                    for msg_id, msg_data in self.buffer.items():
                        # Se eu tenho a mensagem e o vizinho não tem (e o TTL está vivo)
                        if msg_id not in peer_vector and msg_data["ttl"] > 0:
                            data_packet = {
                                "type": "DATA_TRANSFER",
                                "from": self.node_id,
                                "msg_id": msg_id,
                                "msg_data": msg_data
                            }
                            self.send_udp_packet(sender, data_packet)
                            self.forward_count += 1  # Registra que fizemos uma transmissão de dados
                            print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Enviando mensagem {msg_id} (destino {msg_data['to']}) para {sender}")

                # 4. Recebimento real de uma mensagem de dados
                elif p_type == "DATA_TRANSFER":
                    msg_id = packet["msg_id"]
                    msg_data = packet["msg_data"]
                    
                    if msg_id not in self.seen_messages:
                        self.seen_messages.add(msg_id)
                        
                        # Se a mensagem for para mim mesmo
                        if msg_data["to"] == self.node_id:
                            latency = round(self.get_current_sim_time() - msg_data["timestamp"], 2)
                            self.delivered_messages[msg_id] = latency
                            print(f"\n🎉 [{self.get_timestamp_str()}] [Nó {self.node_id}] MENSAGEM ENTREGUE COM SUCESSO: '{msg_data['msg']}' (Latência: {latency}s)")
                        else:
                            # Caso contrário, guarda no buffer para repassar no futuro (Store-and-Forward)
                            new_ttl = msg_data["ttl"] - 1
                            if new_ttl > 0:
                                self.buffer[msg_id] = {
                                    "to": msg_data["to"],
                                    "msg": msg_data["msg"],
                                    "ttl": new_ttl,
                                    "timestamp": msg_data["timestamp"]
                                }
                                print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Mensagem {msg_id} recebida, armazenada no buffer, TTL={new_ttl}")
                
            except Exception as e:
                pass

    def discovery_loop(self):
        """Thread periódica que checa contatos e inicia a troca P2P a cada 2 segundos"""
        while True:
            time.sleep(2.0)
            active_peers = self.get_active_contacts()
            
            for peer in active_peers:
                print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Contato ativo detectado com Nó {peer}")
                
                req_packet = {
                    "type": "SUMMARY_REQ",
                    "from": self.node_id
                }
                self.send_udp_packet(peer, req_packet)

    def save_metrics(self):
        """Salva as estatísticas locais do nó antes de fechar"""
        metrics = {
            "node_id": self.node_id,
            "messages_created": self.sent_count,
            "transmissions_made": self.forward_count,
            "deliveries": self.delivered_messages
        }
        with open(f"metrics_node_{self.node_id}.json", "w") as f:
            json.dump(metrics, f, indent=4)
        print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Métricas salvas localmente.")

    def start(self):
        t_recv = threading.Thread(target=self.receive_handler, daemon=True)
        t_recv.start()
        
        t_disc = threading.Thread(target=self.discovery_loop, daemon=True)
        t_disc.start()
        
        print(f"[{self.get_timestamp_str()}] [Nó {self.node_id}] Rodando na porta {self.port}...")
        print("Aguardando conexões e contatos. Pressione Ctrl+C para encerrar.\n")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{self.get_timestamp_str()}] [Nó {self.node_id}] Encerrando o nó de forma limpa.")
            self.save_metrics()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DTN P2P Network Simulation")
    
    # Modo Nó
    parser.add_argument("--id", help="ID do nó")
    parser.add_argument("--port", type=int, help="Porta local do socket")
    parser.add_argument("--contacts", help="Arquivo contacts.txt")
    
    # Modo Comando (--send)
    parser.add_argument("--send", action="store_true", help="Ativa o modo de envio")
    parser.add_argument("--from", dest="from_node", help="Origem")
    parser.add_argument("--to", dest="to_node", help="Destino final")
    parser.add_argument("--msg", help="Mensagem")
    
    args = parser.parse_args()
    
    if args.send:
        try:
            with open("topology.json", "r") as f:
                topology = json.load(f)
            node_info = topology[str(args.from_node)]
            
            packet = {
                "type": "INJECT",
                "to": str(args.to_node),
                "msg": args.msg
            }
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(json.dumps(packet).encode('utf-8'), (node_info["ip"], node_info["port"]))
            print("[Comando] Mensagem injetada com sucesso no buffer.")
        except Exception as e:
            print(f"[Erro no comando]: {e}")
    else:
        if not args.id or not args.port or not args.contacts:
            print("[Erro] Parâmetros insuficientes. Use --id, --port e --contacts")
        else:
            node = DTNNode(node_id=args.id, port=args.port, contacts_file=args.contacts)
            node.start()