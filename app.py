from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from geopy.geocoders import Nominatim

app = Flask(__name__)
CORS(app)

# Inicializar Geocoder
geolocator = Nominatim(user_agent="mercado_fresco_pap")

# Inicialização do Firebase
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_credentials.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Servidor e Firebase Ativos!")
except Exception as e:
    print(f"❌ Erro Crítico: {e}")

@app.route('/api/produtores/localizacao', methods=['GET'])
def obter_localizacoes():
    try:
        produtores_ref = db.collection('produtores').get()
        lista = []
        for p in produtores_ref:
            d = p.to_dict()
            if 'latitude' in d and 'longitude' in d:
                lista.append({
                    "id": p.id,
                    "nome": d.get('nome', 'Sem nome'),
                    "lat": d['latitude'],
                    "lng": d['longitude'],
                    "disponivel": d.get('disponivel', True),
                    "produtos": d.get('produtos', [])
                })
        return jsonify(lista), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/produtores/registar', methods=['POST'])
def registar():
    try:
        data = request.json
        morada = data.get('morada')
        location = geolocator.geocode(f"{morada}, Portugal")
        
        lat, lng = (location.latitude, location.longitude) if location else (39.5, -8.0)

        novo_produtor = {
            "nome": data.get('nome'),
            "email": data.get('email'),
            "password": str(data.get('password')),
            "telefone": data.get('telefone'),
            "produtos": data.get('produtos', []),
            "latitude": lat,
            "longitude": lng,
            "disponivel": True,
            "morada": morada
        }
        db.collection('produtores').add(novo_produtor)
        return jsonify({"status": "sucesso"}), 201
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

@app.route('/api/produtores/login', methods=['POST'])
def login():
    data = request.json
    docs = db.collection('produtores').where('email', '==', data.get('email')).get()
    for doc in docs:
        if str(doc.to_dict().get('password')) == str(data.get('password')):
            return jsonify({"status": "sucesso", "id": doc.id}), 200
    return jsonify({"status": "erro"}), 401

@app.route('/api/produtores/meus_dados/<id>', methods=['GET'])
def meus_dados(id):
    doc = db.collection('produtores').document(id).get()
    return jsonify(doc.to_dict()) if doc.exists else (jsonify({"erro": "404"}), 404)

@app.route('/api/produtores/atualizar_perfil', methods=['POST'])
def atualizar():
    try:
        data = request.json
        db.collection('produtores').document(data.get('id')).update({
            "nome": data.get('nome'),
            "telefone": data.get('telefone'),
            "produtos": data.get('produtos', []),
            "disponivel": data.get('disponivel')
        })
        return jsonify({"status": "sucesso"}), 200
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)