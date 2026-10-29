from flask import Blueprint, request, jsonify
from models.client_model import ClientModel

client_bp = Blueprint('client_bp', __name__)

@client_bp.route('/api/clients', methods=['GET'])
def list_clients():
    """Lista todos os clientes com suporte a filtro de pesquisa."""
    search = request.args.get('search', None)
    clients = ClientModel.get_all(search)
    return jsonify(clients), 200

@client_bp.route('/api/clients', methods=['POST'])
def create_client():
    """Cadastra um novo cliente."""
    data = request.get_json() or {}
    name = data.get('name')
    phone = data.get('phone')

    try:
        new_client = ClientModel.create(name, phone)
        return jsonify(new_client), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro interno ao cadastrar cliente: " + str(e)}), 500

@client_bp.route('/api/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """Busca detalhes e histórico de pedidos do cliente."""
    client = ClientModel.get_by_id(client_id)
    if not client:
        return jsonify({"error": "Cliente não encontrado"}), 404
    return jsonify(client), 200

@client_bp.route('/api/clients/<int:client_id>', methods=['PUT'])
def update_client(client_id):
    """Atualiza dados do cliente."""
    data = request.get_json() or {}
    name = data.get('name')
    phone = data.get('phone')

    try:
        updated = ClientModel.update(client_id, name, phone)
        if not updated:
            return jsonify({"error": "Cliente não encontrado"}), 404
        return jsonify(updated), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao atualizar cliente: " + str(e)}), 500

@client_bp.route('/api/clients/<int:client_id>', methods=['DELETE'])
def delete_client(client_id):
    """Exclui cliente."""
    success = ClientModel.delete(client_id)
    if not success:
        return jsonify({"error": "Cliente não encontrado"}), 404
    return jsonify({"message": "Cliente e seus pedidos excluídos com sucesso"}), 200
