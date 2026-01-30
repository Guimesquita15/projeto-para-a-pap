from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
import os

app = Flask(__name__)
CORS(app) # Importante: Permite a ligação entre o HTML e o Python

# Inicialização do Firebase
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_credentials.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Servidor e Firebase Ativos!")
except Exception as e:
    print(f"❌ Erro Firebase: {e}")

@app.route('/')
def home():
    return "Servidor Flask a funcionar!"

@app.route('/api/produtores/login', methods=['POST'])
def login():
    print("--- Tentativa de Login Recebida ---")
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        # Procura na coleção 'produtores'
        docs = db.collection('produtores').where('email', '==', email).get()
        
        for doc in docs:
            user = doc.to_dict()
            if str(user.get('password')) == str(password):
                print(f"✅ Login com sucesso para: {email}")
                return jsonify({"status": "sucesso", "id": doc.id}), 200
        
        print(f"❌ Falha no login para: {email}")
        return jsonify({"status": "erro", "mensagem": "Incorretos"}), 401
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/produtores/meus_dados/<id>', methods=['GET'])
def meus_dados(id):
    doc = db.collection('produtores').document(id).get()
    return jsonify(doc.to_dict()) if doc.exists else (jsonify({"erro": "404"}), 404)

@app.route('/api/produtores/atualizar_perfil', methods=['POST'])
def atualizar():
    data = request.json
    db.collection('produtores').document(data.get('id')).update({
        "nome": data.get('nome'),
        "telefone": data.get('telefone'),
        "produtos": data.get('produtos', []),
        "disponivel": data.get('disponivel', True)
    })
    return jsonify({"status": "sucesso"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)