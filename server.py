"""
印刷跟单工作台 - 后端服务
Flask + SQLite，支持手机和电脑多端同步
"""

import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'orders.db')

# ====================== 数据库初始化 ======================

import sqlite3

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_no TEXT NOT NULL,
            customer TEXT NOT NULL,
            designer TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_designer ON orders(designer)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)')

    # 种子数据
    count = conn.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
    if count == 0:
        seed_data(conn)
    conn.commit()
    conn.close()

def seed_data(conn):
    designers = ['张设计', '李设计', '王设计', '赵设计']
    customers = [
        '华彩文化传播有限公司', '瑞丰印务集团', '明日之星教育', '绿叶有机食品',
        '金鼎地产', '阳光百货', '蓝图广告', '星辰科技', '远航物流', '锦绣纺织',
        '鼎丰商贸', '美佳家居'
    ]
    notes = [
        '企业画册24P，A4精装', '产品包装盒设计，3款方案', '品牌VI手册更新',
        '宣传折页三折页', '名片+信封+信纸套装', '海报设计80×120cm',
        '产品目录48P', '展会背景板设计', '手提袋设计', '台历设计2026款',
        '邀请函设计', '会员卡设计'
    ]
    statuses = ['pending','pending','pending','pending','pending',
                'confirmed','confirmed','printing','done','done','cancelled','pending']

    import time
    for i in range(12):
        days_ago = (i * 3 + 1) % 28 + 1
        dt = datetime(2026, 7, 30) if days_ago == 1 else datetime.now()
        from datetime import timedelta
        dt = dt - timedelta(days=days_ago)
        order_id = f"ORD-{int(time.time()*1000)}-{i}"
        conn.execute('''
            INSERT INTO orders (id, order_no, customer, designer, status, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id,
            f'PRT-2026-{i+1:03d}',
            customers[i],
            designers[i % len(designers)],
            statuses[i],
            notes[i],
            dt.strftime('%Y-%m-%d'),
            dt.strftime('%Y-%m-%d %H:%M:%S')
        ))
        time.sleep(0.01)

# ====================== API 路由 ======================

@app.route('/api/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    orders = [dict(r) for r in rows]
    conn.close()
    return jsonify({'code': 0, 'data': orders})

@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    if not data.get('orderNo') or not data.get('customer') or not data.get('designer'):
        return jsonify({'code': 1, 'msg': '单号、客户、设计师不能为空'}), 400

    import time
    import random
    order_id = f"ORD-{int(time.time()*1000)}-{random.randint(1000,9999)}"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')

    conn = get_db()
    conn.execute('''
        INSERT INTO orders (id, order_no, customer, designer, status, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_id,
        data['orderNo'],
        data['customer'],
        data['designer'],
        data.get('status', 'pending'),
        data.get('note', ''),
        today,
        now
    ))
    conn.commit()

    row = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    conn.close()
    return jsonify({'code': 0, 'data': dict(row)})

@app.route('/api/orders/<order_id>', methods=['PUT'])
def update_order(order_id):
    data = request.json
    conn = get_db()
    row = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'code': 1, 'msg': '订单不存在'}), 404

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        UPDATE orders SET
            order_no = ?,
            customer = ?,
            designer = ?,
            status = ?,
            note = ?,
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('orderNo', row['order_no']),
        data.get('customer', row['customer']),
        data.get('designer', row['designer']),
        data.get('status', row['status']),
        data.get('note', row['note']),
        now,
        order_id
    ))
    conn.commit()

    updated = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    conn.close()
    return jsonify({'code': 0, 'data': dict(updated)})

@app.route('/api/orders/<order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    data = request.json
    new_status = data.get('status')
    if new_status not in ('pending', 'confirmed', 'printing', 'done', 'cancelled'):
        return jsonify({'code': 1, 'msg': '无效状态'}), 400

    conn = get_db()
    row = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'code': 1, 'msg': '订单不存在'}), 404

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('UPDATE orders SET status = ?, updated_at = ? WHERE id = ?', (new_status, now, order_id))
    conn.commit()

    updated = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    conn.close()
    return jsonify({'code': 0, 'data': dict(updated)})

@app.route('/api/orders/<order_id>', methods=['DELETE'])
def delete_order(order_id):
    conn = get_db()
    conn.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'code': 0, 'msg': '已删除'})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
    pending = conn.execute("SELECT COUNT(*) as c FROM orders WHERE status = 'pending'").fetchone()['c']

    from datetime import timedelta
    urgent_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    urgent = conn.execute(
        "SELECT COUNT(*) as c FROM orders WHERE status = 'pending' AND created_at <= ?", (urgent_date,)
    ).fetchone()['c']

    designers = conn.execute('SELECT DISTINCT designer FROM orders ORDER BY designer').fetchall()
    conn.close()

    return jsonify({
        'code': 0,
        'data': {
            'total': total,
            'pending': pending,
            'urgent': urgent,
            'designers': [d['designer'] for d in designers]
        }
    })

@app.route('/api/export', methods=['GET'])
def export_csv():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()

    status_labels = {
        'pending': '待定稿', 'confirmed': '已定稿', 'printing': '印刷中',
        'done': '已完结', 'cancelled': '已取消'
    }

    from io import StringIO
    output = StringIO()
    output.write('\uFEFF单号,客户,设计师,录入日期,状态,已过天数,备注\n')

    for r in rows:
        days = (datetime.now().date() - datetime.strptime(r['created_at'], '%Y-%m-%d').date()).days
        row = [
            r['order_no'],
            f'"{r["customer"]}"',
            f'"{r["designer"]}"',
            r['created_at'],
            status_labels.get(r['status'], r['status']),
            f'{days}天',
            f'"{r["note"]}"'
        ]
        output.write(','.join(row) + '\n')

    from flask import Response
    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv;charset=utf-8',
        headers={'Content-Disposition': f'attachment;filename=印刷跟单_{datetime.now().strftime("%Y%m%d")}.csv'}
    )

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# ====================== 启动 ======================

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f'📋 印刷跟单工作台启动！')
    print(f'   数据库: {DB_PATH}')
    print(f'   访问: http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=False)
