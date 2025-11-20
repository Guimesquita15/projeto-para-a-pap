from flask import Flask, jsonify, request
from flask_cors import CORS 
import sqlite3
from geopy.geocoders import Nominatim
import time
import os

# --- 1. CONFIGURAÇÃO GLOBAL ---
app = Flask(__name__)
CORS(app) 

DB_NAME = 'estufa.db'
geolocator = Nominatim(user_agent="greenhouse_project_pap_guilherme") 

def get_db_connection():
    """Função de conveniência para ligar à Base de Dados SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def setup_database():
    """Cria as tabelas necessárias e insere dados de teste, se o ficheiro DB não existir."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtores (
            id_produtor INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_produtor TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            produtos_venda TEXT,
            morada TEXT NOT NULL,
            telefone TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leituras_sensores (
            id_leitura INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            temperatura_ar REAL,
            humidade_ar REAL,
            humidade_solo REAL
        );
    """)

    # Inserção de dados de teste (apenas se a tabela estiver vazia)
    cursor.execute("SELECT COUNT(*) FROM produtores")
    if cursor.fetchone()[0] == 0:
        test_data = [
           
        ]
        cursor.executemany("""
            INSERT INTO produtores (nome_produtor, latitude, longitude, produtos_venda, morada, telefone) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, test_data)

    conn.commit()
    conn.close()

# --- 2. ENDPOINT PARA INSERIR PRODUTORES (POST) ---
@app.route('/api/produtores/registar', methods=['POST'])
def registar_produtor():
    """Recebe os dados do formulário, faz geocodificação e insere na BD."""
    try:
        data = request.json
        print(f"Dados recebidos do Frontend: {data}") # <--- LOG PARA DEBUGGING
        
        nome = data.get('nome')
        morada = data.get('morada')
        telefone = data.get('telefone')
        # O Frontend envia 'produtos' como uma lista (array) de strings.
        produtos_list = data.get('produtos', []) 
        
        # 1. VALIDAÇÃO MÍNIMA
        if not nome or not morada or not telefone:
            return jsonify({"status": "erro", "mensagem": "Faltam campos obrigatórios."}), 400

        # 2. GEOCODIFICAÇÃO: Converte Morada -> (Latitude, Longitude)
        try:
            time.sleep(1) 
            location = geolocator.geocode(morada + ", Portugal", timeout=10)
            
            if not location:
                return jsonify({"status": "erro", "mensagem": "Morada não encontrada. Tente um endereço mais específico e inclua a localidade."}), 400
                
            latitude = location.latitude
            longitude = location.longitude
            
        except Exception as e:
            # Captura erros de rede ou timeout da API de geocodificação
            print(f"Erro de Geocodificação: {e}")
            return jsonify({"status": "erro", "mensagem": "Erro no serviço de mapas (Geocodificação). Tente mais tarde."}), 500

        # 3. INSERÇÃO NA BASE DE DADOS
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Converte a lista de produtos numa string separada por vírgulas para a BD
        produtos_str = ", ".join(produtos_list) if isinstance(produtos_list, list) else str(produtos_list)
        
        cursor.execute("""
            INSERT INTO produtores (nome_produtor, morada, telefone, produtos_venda, latitude, longitude) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome, morada, telefone, produtos_str, latitude, longitude))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "sucesso", "mensagem": "Produtor registado e adicionado ao mapa!", "latitude": latitude, "longitude": longitude}), 201

    except Exception as e:
        # Este 'except' captura qualquer outro erro Python. É aqui que o 500 acontece.
        print(f"Erro interno FATAL: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno do servidor. Verifique o console do terminal Flask para o Traceback completo."}), 500


# --- 3. ENDPOINT PARA O MAPA (GET) ---
@app.route('/api/produtores/localizacao', methods=['GET'])
def get_produtores_localizacao():
    """Devolve a lista de produtores e localizações em formato JSON para o mapa."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT nome_produtor, latitude, longitude, produtos_venda, morada, telefone FROM produtores")
    produtores_raw = cursor.fetchall()
    conn.close()
    
    produtores_json = []
    for row in produtores_raw:
        produtos_str = row['produtos_venda'] if row['produtos_venda'] else ""
        produtores_json.append({
            "nome": row['nome_produtor'],
            "lat": row['latitude'],
            "lng": row['longitude'],
            "produtos": produtos_str.split(', '),
            "morada": row['morada'],
            "telefone": row['telefone']
        })
        
    return jsonify(produtores_json)

# --- 4. ENDPOINT DE STATUS DA ESTUFA (EXEMPLO) ---
@app.route('/api/estufa/status', methods=['GET'])
def get_estufa_status():
    """Endpoint para devolver o estado atual dos parâmetros da estufa."""
    # Este é um placeholder, pode vir a usar a tabela 'leituras_sensores' aqui
    return jsonify({"temperatura": 25.5, "humidade": 60, "bomba_ligada": False})

if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        setup_database() 
        print(f"Base de Dados '{DB_NAME}' criada e configurada com dados de teste.")
    
    print("Servidor Flask a iniciar...")
    app.run(host='0.0.0.0', port=5000, debug=True)