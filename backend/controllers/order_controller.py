import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from models.order_model import OrderModel
from models.payment_model import PaymentModel
from models.client_model import ClientModel

order_bp = Blueprint('order_bp', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@order_bp.route('/api/orders', methods=['GET'])
def list_orders():
    """Lista pedidos com suporte a múltiplos filtros."""
    status = request.args.get('status')
    payment_status = request.args.get('payment_status')
    client_id = request.args.get('client_id')
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    orders = OrderModel.get_all(
        status=status,
        payment_status=payment_status,
        client_id=client_id,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify(orders), 200

@order_bp.route('/api/orders', methods=['POST'])
def create_order():
    """Cria um novo pedido com os tênis da produção."""
    data = request.get_json() or {}
    client_id = data.get('client_id')
    client_name = data.get('client_name')
    client_phone = data.get('client_phone')

    # Se client_id não foi informado, mas temos nome e telefone de novo cliente
    if not client_id and client_name and client_phone:
        try:
            # Verificar se já existe com esse telefone
            clean_p = ClientModel._clean_phone(client_phone)
            existing = ClientModel.get_all(search=clean_p)
            if existing and len(existing) > 0:
                client_id = existing[0]['id']
            else:
                new_c = ClientModel.create(client_name, client_phone)
                client_id = new_c['id']
        except Exception as e:
            return jsonify({"error": f"Erro ao cadastrar novo cliente do pedido: {str(e)}"}), 400

    if not client_id:
        return jsonify({"error": "Por favor, selecione um cliente existente ou informe o Nome e Telefone do novo cliente."}), 400

    items = data.get('items', [])
    payment_method = data.get('payment_method', 'PIX')
    payment_status = data.get('payment_status', 'Pendente')
    notes = data.get('notes', '')
    created_at = data.get('created_at', None)

    try:
        new_order = OrderModel.create(
            client_id=client_id,
            items=items,
            payment_method=payment_method,
            payment_status=payment_status,
            notes=notes,
            created_at=created_at
        )
        return jsonify(new_order), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao criar pedido: " + str(e)}), 500

@order_bp.route('/api/orders/pipeline', methods=['GET'])
def get_pipeline():
    """Retorna a contagem de pedidos em cada etapa da produção."""
    counts = OrderModel.get_pipeline_counts()
    return jsonify(counts), 200

@order_bp.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Retorna os dados completos do pedido, itens e histórico."""
    order = OrderModel.get_by_id(order_id)
    if not order:
        return jsonify({"error": "Pedido não encontrado"}), 404
    return jsonify(order), 200

@order_bp.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
def update_status(order_id):
    """
    Atualiza o status da linha de produção.
    A entrega do tênis está estritamente condicionada ao status 'Pago'.
    """
    data = request.get_json() or {}
    new_status = data.get('status')
    if not new_status:
        return jsonify({"error": "O campo 'status' é obrigatório."}), 400

    try:
        result = OrderModel.update_status(order_id, new_status)
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao atualizar status: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>/payment', methods=['PATCH'])
def update_payment(order_id):
    """Atualiza a forma e o status de pagamento (Pendente ou Pago)."""
    data = request.get_json() or {}
    payment_status = data.get('payment_status')
    payment_method = data.get('payment_method')

    if not payment_status:
        return jsonify({"error": "O campo 'payment_status' é obrigatório."}), 400

    try:
        PaymentModel.register_payment(order_id, payment_method, payment_status)
        updated_order = OrderModel.get_by_id(order_id)
        return jsonify(updated_order), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao registrar pagamento: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>/audit', methods=['PUT'])
def update_order_audit(order_id):
    """Permite alterar histórico e campos do pedido para correção e auditoria."""
    data = request.get_json() or {}
    try:
        updated = OrderModel.update_audit_full(order_id, data)
        return jsonify(updated), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao auditar/atualizar pedido: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>/whatsapp', methods=['GET'])
def get_whatsapp(order_id):
    """Gera o link de notificação wa.me com a mensagem padronizada."""
    try:
        wa_data = PaymentModel.generate_whatsapp_info(order_id)
        return jsonify(wa_data), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao gerar notificação WhatsApp: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>/items/<int:item_id>/upload', methods=['POST'])
def upload_item_images(order_id, item_id):
    """
    Upload de fotos de 'Antes' e 'Depois' para um par de tênis específico do pedido.
    """
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    before_file = request.files.get('before_image')
    after_file = request.files.get('after_image')

    before_path = None
    after_path = None

    if before_file and before_file.filename and allowed_file(before_file.filename):
        ext = before_file.filename.rsplit('.', 1)[1].lower()
        filename = f"before_order{order_id}_item{item_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        before_file.save(filepath)
        before_path = f"/uploads/{filename}"

    if after_file and after_file.filename and allowed_file(after_file.filename):
        ext = after_file.filename.rsplit('.', 1)[1].lower()
        filename = f"after_order{order_id}_item{item_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(upload_folder, filename)
        after_file.save(filepath)
        after_path = f"/uploads/{filename}"

    if not before_path and not after_path:
        return jsonify({"error": "Nenhum arquivo de imagem válido foi enviado."}), 400

    try:
        saved = OrderModel.save_item_images(item_id, before_image=before_path, after_image=after_path)
        full_order = OrderModel.get_by_id(order_id)
        return jsonify({"item": saved, "order": full_order}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao salvar imagens: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>/items/<int:item_id>/photos/<string:photo_type>', methods=['DELETE'])
def remove_item_photo(order_id, item_id, photo_type):
    """Remove a foto ('before' ou 'after') de um item do pedido."""
    try:
        result = OrderModel.remove_item_photo(item_id, photo_type)

        # Remove o arquivo físico da pasta uploads se existir
        old_photo = result.get('old_photo')
        if old_photo and old_photo.startswith('/uploads/'):
            filename = old_photo.replace('/uploads/', '')
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

        full_order = OrderModel.get_by_id(order_id)
        return jsonify({"result": result, "order": full_order}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Erro ao remover foto: " + str(e)}), 500

@order_bp.route('/api/orders/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    """Exclui um pedido."""
    success = OrderModel.delete(order_id)
    if not success:
        return jsonify({"error": "Pedido não encontrado"}), 404
    return jsonify({"message": "Pedido excluído com sucesso."}), 200
