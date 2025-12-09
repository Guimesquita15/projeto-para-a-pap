from flask import Flask, jsonify, request
from flask_cors import CORS 
import sqlite3 # Reintroduzido para o fallback (opcional)
import time
import json # NOVO: Necessário para ler o array JSON de nomes de produtos
from geopy.geocoders import Nominatim
import os

# --- NOVAS DEPENDÊNCIAS FIREBASE ---
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from firebase_admin import storage # NOVO: Para lidar com o armazenamento de ficheiros

# --- 1. CONFIGURAÇÃO GLOBAL ---
app = Flask(__name__)
CORS(app) 

# Configurações de BD (usadas para fallback ou se o Firebase falhar)
DB_NAME = 'estufa_v2.db' 
FIREBASE_CREDENTIALS_FILE = 'firebase_credentials.json' 
COLLECTION_NAME = 'produtores' 

# CONFIGURAÇÃO DO STORAGE: SUBSTITUA PELO SEU BUCKET ID REAL! (Ex: "nome-do-seu-projeto.appspot.com")
FIREBASE_STORAGE_BUCKET = 'project-id.appspot.com' 

# Variável para saber qual BD está a ser usada
DB_MODE = 'SQLITE'
geolocator = Nominatim(user_agent="greenhouse_project_pap_guilherme") 

# Variável global para a conexão (Firestore client ou None)
db_client = None 

# --- FUNÇÕES DE BD (setup_database, get_db_connection, initialize_database) ---
# ... (MANTÊM-SE IGUAIS - Não foram alteradas nesta atualização) ...

def setup_database():
    """Cria a tabela Produtores e insere dados de teste, se o ficheiro DB não existir."""
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
    cursor.execute("SELECT COUNT(*) FROM produtores")
    if cursor.fetchone()[0] == 0:
        test_data = [
            ("Quinta da Boa Esperança", 40.1265, -7.5015, "Cerejas, Pêssegos, Maçãs", "Rua do Pomar, Fundão", "911222333"),
            ("Horta Urbana de Benfica", 38.7480, -9.1820, "Alfaces, Rúcula, Tomilho, Salsa", "Rua do Jardim, 15, Lisboa", "934567890"),
        ]
        cursor.executemany("INSERT INTO produtores (nome_produtor, latitude, longitude, produtos_venda, morada, telefone) VALUES (?, ?, ?, ?, ?, ?)", test_data)
        
    conn.commit()
    conn.close()

def get_db_connection():
    """Função de conveniência para ligar à Base de Dados SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def initialize_database():
    """Tenta inicializar o Firebase. Se falhar, usa SQLite."""
    global db_client, DB_MODE

    if os.path.exists(FIREBASE_CREDENTIALS_FILE):
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_FILE)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred, {'storageBucket': FIREBASE_STORAGE_BUCKET}) # Adiciona a configuração do Storage
            
            db_client = firestore.client() 
            DB_MODE = 'FIREBASE'
            print("Base de Dados: Conectado ao GOOGLE FIRESTORE.")
            return

        except Exception as e:
            print(f"AVISO: ERRO ao ligar ao Firebase. Motivo: {e}")
            print("A reverter para a Base de Dados local (SQLite).")
    else:
        print(f"AVISO: Ficheiro de credenciais '{FIREBASE_CREDENTIALS_FILE}' não encontrado.")
        print("A reverter para a Base de Dados local (SQLite).")

    DB_MODE = 'SQLITE'
    if not os.path.exists(DB_NAME):
        setup_database()
        print(f"Base de Dados: Ficheiro local '{DB_NAME}' criado e configurado.")
    else:
        print(f"Base de Dados: A usar ficheiro local '{DB_NAME}'.")

# --- 2. ENDPOINT PARA INSERIR PRODUTORES (POST) ---
@app.route('/api/produtores/registar', methods=['POST'])
def registar_produtor():
    """Recebe dados do produtor e MÚLTIPLAS IMAGENS/PRODUTOS."""
    try:
        # 1. Obter Dados Base (AGORA VÊM DE request.form e request.files)
        nome_produtor = request.form.get('nome')
        morada = request.form.get('morada')
        telefone = request.form.get('telefone')
        
        # Obter a lista de Nomes de Produtos (String JSON)
        nomes_produtos_json = request.form.get('nomes_produtos', '[]')
        nomes_produtos = json.loads(nomes_produtos_json)

        if not nome_produtor or not morada or not telefone or not nomes_produtos:
            return jsonify({"status": "erro", "mensagem": "Faltam campos obrigatórios ou produtos."}), 400

        # 2. GEOCODIFICAÇÃO (Comum a ambas as BDs)
        try:
            time.sleep(1) 
            location = geolocator.geocode(morada + ", Portugal", timeout=10)
            if not location:
                return jsonify({"status": "erro", "mensagem": "Morada não encontrada."}), 400
            latitude = location.latitude
            longitude = location.longitude
        except Exception:
            return jsonify({"status": "erro", "mensagem": "Erro no serviço de mapas (Geocodificação)."}), 500

        # 3. PROCESSAMENTO DE PRODUTOS E IMAGENS
        produtos_com_url = []
        produtos_str_sqlite = "" # Apenas para o fallback SQLite

        if DB_MODE == 'FIREBASE':
            bucket = storage.bucket(FIREBASE_STORAGE_BUCKET)
            
            # Itera sobre a lista de nomes e usa o índice para encontrar o ficheiro
            for index, nome_produto in enumerate(nomes_produtos):
                # O frontend envia os ficheiros com o nome 'file_0', 'file_1', etc.
                file = request.files.get(f'file_{index}')
                
                if file and file.filename:
                    # Cria um nome de ficheiro único para o Storage
                    ext = file.filename.split('.')[-1]
                    unique_filename = f"{nome_produtor.replace(' ', '_')}_{nome_produto.replace(' ', '_')}_{int(time.time())}.{ext}"
                    blob = bucket.blob(f'produtos/{unique_filename}')
                    
                    # Upload
                    blob.upload_from_file(file, content_type=file.content_type)
                    blob.make_public()
                    image_url = blob.public_url

                    # Guardar o objeto Produto para o Firestore
                    produtos_com_url.append({
                        "nome": nome_produto,
                        "foto_url": image_url, # URL da imagem associada
                    })
                else:
                    # Se não houver ficheiro (o que não deve acontecer)
                    produtos_com_url.append({"nome": nome_produto, "foto_url": ""})
            
            # 4. INSERÇÃO NO FIRESTORE
            produtor_data = {
                "nome_produtor": nome_produtor,
                "morada": morada,
                "telefone": telefone,
                "produtos_venda": produtos_com_url, # LISTA DE OBJETOS
                "latitude": latitude,
                "longitude": longitude
            }
            db_client.collection(COLLECTION_NAME).add(produtor_data)
            return jsonify({"status": "sucesso", "mensagem": f"Produtor e {len(produtos_com_url)} produtos registados no Firebase!", "latitude": latitude, "longitude": longitude}), 201
            
        else: # SQLITE: O SQLITE NÃO SUPORTA A ESTRUTURA DE MÚLTIPLAS IMAGENS/OBJETOS
            # Para o SQLite, reverte para a estrutura antiga (lista simples de nomes)
            produtos_str_sqlite = ", ".join(nomes_produtos)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO produtores (nome_produtor, morada, telefone, produtos_venda, latitude, longitude) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nome_produtor, morada, telefone, produtos_str_sqlite, latitude, longitude))
            conn.commit()
            conn.close()
            return jsonify({"status": "sucesso", "mensagem": "Produtor registado no SQLite (sem fotos associadas)!", "latitude": latitude, "longitude": longitude}), 201

    except Exception as e:
        print(f"Erro FATAL no registo de produtor: {e}")
        return jsonify({"status": "erro", "mensagem": f"Erro interno do servidor: {e}"}), 500


# --- 3. ENDPOINT PARA O MAPA (GET) ---
@app.route('/api/produtores/localizacao', methods=['GET'])
def get_produtores_localizacao():
    """Devolve a lista de produtores e localizações da BD ativa."""
    try:
        produtores_json = []

        if DB_MODE == 'FIREBASE':
            docs = db_client.collection(COLLECTION_NAME).stream()
            for doc in docs:
                data = doc.to_dict()
                # O campo 'produtos_venda' AGORA é uma lista de objetos: [{nome: 'Maçãs', foto_url: '...'}]
                produtos_list = data.get('produtos_venda', []) 
                
                produtores_json.append({
                    "nome": data.get('nome_produtor'), "lat": data.get('latitude'), "lng": data.get('longitude'),
                    "produtos": produtos_list, "morada": data.get('morada'), "telefone": data.get('telefone')
                })
                
        else: # SQLITE (Mantém a leitura da lista simples de strings)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT nome_produtor, latitude, longitude, produtos_venda, morada, telefone FROM produtores")
            produtores_raw = cursor.fetchall()
            conn.close()
            
            for row in produtores_raw:
                produtos_raw_str = row['produtos_venda'] if row['produtos_venda'] else ""
                # Converter de string (SQLite) para lista de strings (JSON)
                produtos_list = [p.strip() for p in produtos_raw_str.split(', ') if p.strip()] 
                
                # Formato final para o frontend (SQLite não tem as URLs de foto)
                produtos_finais = [{"nome": p, "foto_url": ""} for p in produtos_list] 
                
                produtores_json.append({
                    "nome": row['nome_produtor'], "lat": row['latitude'], "lng": row['longitude'],
                    "produtos": produtos_finais, "morada": row['morada'], "telefone": row['telefone']
                })
            
        return jsonify(produtores_json)

    except Exception as e:
        print(f"ERRO FATAL ao consultar produtores na {DB_MODE}: {e}")
        return jsonify({"status": "erro", "mensagem": f"Erro interno ao carregar produtores: {e}"}), 500


if __name__ == '__main__':
    initialize_database() 
    print(f"Modo Ativo: {DB_MODE}")
    app.run(host='0.0.0.0', port=5000, debug=True)