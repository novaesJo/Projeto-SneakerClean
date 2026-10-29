from flask import Blueprint, request, jsonify
from datetime import datetime
from database import get_db_connection

calendar_bp = Blueprint('calendar_bp', __name__)

@calendar_bp.route('/api/calendar/events', methods=['GET'])
def get_calendar_events():
    """
    Retorna os eventos do mês agrupados por dia:
    - Pedidos iniciados (created_at)
    - Pedidos finalizados/prontos (completion_date)
    - Pedidos entregues (delivered_date)
    """
    now = datetime.now()
    year = int(request.args.get('year', now.year))
    month = int(request.args.get('month', now.month))

    month_str = f"{year:04d}-{month:02d}"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Buscar todos os pedidos com atividade relevante no mês solicitado
    query = """
        SELECT o.*, 
               c.name as client_name, 
               c.phone as client_phone
        FROM orders o
        JOIN clients c ON o.client_id = c.id
        WHERE strftime('%Y-%m', o.created_at) = ?
           OR strftime('%Y-%m', o.completion_date) = ?
           OR strftime('%Y-%m', o.delivered_date) = ?
        ORDER BY o.created_at ASC
    """
    cursor.execute(query, (month_str, month_str, month_str))
    rows = cursor.fetchall()

    days_data = {}

    for row in rows:
        order = dict(row)

        # Buscar itens
        cursor.execute("SELECT brand, color_type FROM order_items WHERE order_id = ?", (order['id'],))
        order['items_summary'] = [f"{it['brand']} ({it['color_type']})" for it in cursor.fetchall()]

        # 1. Evento de Início
        if order.get('created_at'):
            day_created = order['created_at'][:10]
            if day_created.startswith(month_str):
                if day_created not in days_data:
                    days_data[day_created] = {"started": [], "completed": [], "delivered": []}
                days_data[day_created]["started"].append({
                    "id": order['id'],
                    "client_name": order['client_name'],
                    "pair_count": order['pair_count'],
                    "status": order['status'],
                    "payment_status": order['payment_status'],
                    "items": order['items_summary']
                })

        # 2. Evento de Conclusão / Pronto
        if order.get('completion_date'):
            day_comp = order['completion_date'][:10]
            if day_comp.startswith(month_str):
                if day_comp not in days_data:
                    days_data[day_comp] = {"started": [], "completed": [], "delivered": []}
                days_data[day_comp]["completed"].append({
                    "id": order['id'],
                    "client_name": order['client_name'],
                    "pair_count": order['pair_count'],
                    "status": order['status'],
                    "payment_status": order['payment_status'],
                    "items": order['items_summary']
                })

        # 3. Evento de Entrega
        if order.get('delivered_date'):
            day_del = order['delivered_date'][:10]
            if day_del.startswith(month_str):
                if day_del not in days_data:
                    days_data[day_del] = {"started": [], "completed": [], "delivered": []}
                days_data[day_del]["delivered"].append({
                    "id": order['id'],
                    "client_name": order['client_name'],
                    "pair_count": order['pair_count'],
                    "status": order['status'],
                    "payment_status": order['payment_status'],
                    "items": order['items_summary']
                })

    conn.close()

    return jsonify({
        "year": year,
        "month": month,
        "events_by_day": days_data
    }), 200

@calendar_bp.route('/api/calendar/day', methods=['GET'])
def get_day_orders():
    """Retorna detalhes de todos os pedidos de um determinado dia."""
    target_date = request.args.get('date')
    if not target_date:
        return jsonify({"error": "Data é obrigatória (formato YYYY-MM-DD)"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT o.*, c.name as client_name, c.phone as client_phone
        FROM orders o
        JOIN clients c ON o.client_id = c.id
        WHERE DATE(o.created_at) = DATE(?)
           OR DATE(o.completion_date) = DATE(?)
           OR DATE(o.delivered_date) = DATE(?)
        ORDER BY o.id DESC
    """
    cursor.execute(query, (target_date, target_date, target_date))
    orders = [dict(r) for r in cursor.fetchall()]

    for o in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (o['id'],))
        o['items'] = [dict(it) for it in cursor.fetchall()]

    conn.close()
    return jsonify(orders), 200
