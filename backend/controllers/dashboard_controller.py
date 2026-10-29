from flask import Blueprint, jsonify
from models.payment_model import PaymentModel
from models.order_model import OrderModel
from database import get_db_connection

dashboard_bp = Blueprint('dashboard_bp', __name__)

@dashboard_bp.route('/api/dashboard/metrics', methods=['GET'])
def get_metrics():
    """
    Retorna todas as métricas consolidadas para o Dashboard:
    - Faturamento do Dia
    - Faturamento da Semana
    - Faturamento do Mês
    - Pipeline de produção
    - Gráfico diário de faturamento
    - Estatísticas de tênis (Cores Branco vs Colorido, Marcas populares)
    """
    try:
        financial = PaymentModel.get_financial_metrics()
        pipeline = OrderModel.get_pipeline_counts()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Distribuição de cores de tênis
        cursor.execute("""
            SELECT color_type, COUNT(*) as count 
            FROM order_items 
            GROUP BY color_type;
        """)
        colors = [dict(r) for r in cursor.fetchall()]

        # Top 5 marcas mais lavadas
        cursor.execute("""
            SELECT brand, COUNT(*) as count 
            FROM order_items 
            GROUP BY brand 
            ORDER BY count DESC 
            LIMIT 5;
        """)
        top_brands = [dict(r) for r in cursor.fetchall()]

        # Últimos 5 pedidos para feed de atividades rápidas
        cursor.execute("""
            SELECT o.id, o.pair_count, o.total_price, o.status, o.payment_status, o.created_at,
                   c.name as client_name
            FROM orders o
            JOIN clients c ON o.client_id = c.id
            ORDER BY o.id DESC
            LIMIT 5;
        """)
        recent_orders = [dict(r) for r in cursor.fetchall()]

        conn.close()

        return jsonify({
            "financial": financial,
            "pipeline": pipeline,
            "sneaker_stats": {
                "colors": colors,
                "top_brands": top_brands
            },
            "recent_orders": recent_orders
        }), 200
    except Exception as e:
        return jsonify({"error": "Erro ao compilar métricas do dashboard: " + str(e)}), 500
