from flask import Flask, jsonify, request
from flask_cors import CORS 
import sqlite3
from geopy.geocoders import Nominatim
import time
import os
# from datetime import datetime # Não é mais necessário

# --- 1. CONFIGURAÇÃO GLOBAL ---
app = Flask(__name__)
CORS(app) 

# Se usou este nome para contornar o erro anterior, mantenha-o. Caso contrário, use 'estufa.db'
DB_NAME = 'estufa_v2.db' 
geolocator = Nominatim(user_agent="greenhouse_project_pap_guilherme") 

def get_db_connection():
    """Função de conveniência para ligar à Base de Dados SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def setup_database():
    """Cria a tabela Produtores e insere dados de teste, se o ficheiro DB não existir."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Criação APENAS da tabela 'produtores'
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
    # A tabela 'leituras_sensores' foi removida.

    # Inserção de dados de teste (apenas se a tabela estiver vazia)
    cursor.execute("SELECT COUNT(*) FROM produtores")
    if cursor.fetchone()[0] == 0:
        test_data = [
            ("Quinta da Boa Esperança", 40.1265, -7.5015, "Cerejas, Pêssegos, Maçãs", "Rua do Pomar, Fundão", "911222333"),
            ("Horta Urbana de Benfica", 38.7480, -9.1820, "Alfaces, Rúcula, Tomilho, Salsa", "Rua do Jardim, 15, Lisboa", "934567890"),
            ("Fazenda Ribeira", 41.1400, -8.6110, "Vinhos, Queijos, Azeite", "Largo da Alfândega, 1, Porto", "225556667"),
            ("Viveiro da Cidade", 40.2100, -8.4200, "Flores, Plantas Aromáticas", "Avenida Fernão de Magalhães, Coimbra", "960123456")
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
        print(f"Dados recebidos do Frontend: {data}")
        
        nome = data.get('nome')
        morada = data.get('morada')
        telefone = data.get('telefone')
        produtos_list = data.get('produtos', []) 
        
        if not nome or not morada or not telefone:
            return jsonify({"status": "erro", "mensagem": "Faltam campos obrigatórios."}), 400

        try:
            time.sleep(1) 
            location = geolocator.geocode(morada + ", Portugal", timeout=10)
            
            if not location:
                return jsonify({"status": "erro", "mensagem": "Morada não encontrada. Tente um endereço mais específico e inclua a localidade."}), 400
                
            latitude = location.latitude
            longitude = location.longitude
            
        except Exception as e:
            print(f"Erro de Geocodificação: {e}")
            return jsonify({"status": "erro", "mensagem": "Erro no serviço de mapas (Geocodificação). Tente mais tarde."}), 500

        conn = get_db_connection()
        cursor = conn.cursor()
        
        produtos_str = ", ".join(produtos_list) if isinstance(produtos_list, list) else str(produtos_list)
        
        cursor.execute("""
            INSERT INTO produtores (nome_produtor, morada, telefone, produtos_venda, latitude, longitude) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nome, morada, telefone, produtos_str, latitude, longitude))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "sucesso", "mensagem": "Produtor registado e adicionado ao mapa!", "latitude": latitude, "longitude": longitude}), 201

    except Exception as e:
        print(f"Erro interno FATAL: {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno do servidor. Verifique o console do terminal Flask para o Traceback completo."}), 500


# --- 3. ENDPOINT PARA O MAPA (GET) ---
@app.route('/api/produtores/localizacao', methods=['GET'])
def get_produtores_localizacao():
    """Devolve a lista de produtores e localizações em formato JSON para o mapa."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT nome_produtor, latitude, longitude, produtos_venda, morada, telefone FROM produtores")
        produtores_raw = cursor.fetchall()
        conn.close()
        
        produtores_json = []
        for row in produtores_raw:
            produtos_raw_str = row['produtos_venda'] if row['produtos_venda'] else ""
            produtos_list = [p.strip() for p in produtos_raw_str.split(', ') if p.strip()]
            
            produtores_json.append({
                "nome": row['nome_produtor'],
                "lat": row['latitude'],
                "lng": row['longitude'],
                "produtos": produtos_list,
                "morada": row['morada'],
                "telefone": row['telefone']
            })
            
        return jsonify(produtores_json)

    except Exception as e:
        print(f"ERRO FATAL ao consultar produtores (Erro 500): {e}")
        return jsonify({"status": "erro", "mensagem": "Erro interno ao carregar produtores. Verifique o terminal Flask."}), 500

# As rotas de sensores e status foram removidas!

if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        setup_database() 
        print(f"Base de Dados '{DB_NAME}' criada e configurada com dados de teste.")
    
    print("Servidor Flask a iniciar...")
    app.run(host='0.0.0.0', port=5000, debug=True)