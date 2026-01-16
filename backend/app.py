from flask import Flask, jsonify, request
from flask_cors import CORS 
import os
import time
from geopy.geocoders import Nominatim
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app) 

# Configurações - Garante que o ficheiro .json está na mesma pasta
FIREBASE_CREDENTIALS_FILE = 'firebase_credentials.json' 
COLLECTION_NAME = 'produtores' 

def initialize_database():
    if os.path.exists(FIREBASE_CREDENTIALS_FILE):
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS_FILE)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred) 
            return firestore.client()
        except Exception as e:
            print(f"Erro Firebase: {e}")
            return None
    return None

db_client = initialize_database()
geolocator = Nominatim(user_agent="mercado_frescos_portugal_v1")

@app.route('/')
def home(): return "Servidor Online!"

# Rota para o Mapa (Público)
@app.route('/api/produtores/localizacao', methods=['GET'])
def get_mapa():
    docs = db_client.collection(COLLECTION_NAME).stream()
    return jsonify([{**d.to_dict(), "id": d.id} for d in docs])

# Rota de Login
@app.route('/api/produtores/login', methods=['POST'])
def login():
    data = request.json
    docs = db_client.collection(COLLECTION_NAME).where("email", "==", data.get('email')).where("password", "==", data.get('password')).get()
    for doc in docs:
        return jsonify({"status": "sucesso", "id": doc.id, "nome": doc.to_dict().get('nome')})
    return jsonify({"status": "erro"}), 401

# Rota para obter dados de 1 produtor
@app.route('/api/produtores/meus_dados/<id>', methods=['GET'])
def meus_dados(id):
    doc = db_client.collection(COLLECTION_NAME).document(id).get()
    return jsonify(doc.to_dict()) if doc.exists else jsonify({"erro": "n/a"}), 404

# Rota para salvar alterações (incluindo Foto Base64)
@app.route('/api/produtores/atualizar_perfil', methods=['POST'])
def atualizar():
    data = request.json
    db_client.collection(COLLECTION_NAME).document(data.get('id')).update({
        "nome": data.get('nome'),
        "telefone": data.get('telefone'),
        "produtos": data.get('produtos', []),
        "disponivel": data.get('disponivel'),
        "foto": data.get('foto') 
    })
    return jsonify({"status": "sucesso"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)