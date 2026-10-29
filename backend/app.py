import os
from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Carregar variáveis do arquivo .env antes de tudo
load_dotenv()

from database import init_db
from controllers.client_controller import client_bp
from controllers.order_controller import order_bp
from controllers.calendar_controller import calendar_bp
from controllers.dashboard_controller import dashboard_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), 'frontend')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Habilitar CORS para permitir chamadas de qualquer porta/origem local
CORS(app, resources={r"/*": {"origins": "*"}})

# Registrar Blueprints das Rotas
app.register_blueprint(client_bp)
app.register_blueprint(order_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(dashboard_bp)

# Servir arquivos estáticos do Frontend
@app.route('/')
def serve_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)

# Servir uploads de fotos de Antes / Depois
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Recurso não encontrado"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Erro interno no servidor"}), 500

def create_app():
    init_db()
    return app

if __name__ == '__main__':
    print("==================================================================")
    print("  👟 SNEAKER CLEAN - SISTEMA DE GESTÃO DE LIMPEZA DE TÊNIS 👟")
    print("==================================================================")
    print("  Inicializando banco de dados SQLite...")
    init_db()
    print("  Banco de dados pronto!")
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"  Servidor iniciado em: http://{host}:{port}")
    print("  Pressione Ctrl+C para encerrar o servidor.")
    print("==================================================================")
    app.run(host=host, port=port, debug=debug)
