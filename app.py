import sys
import os

# 确保项目目录在模块搜索路径中
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

"""体重管理系统 - Flask 后端

运行方式:
    python app.py
    浏览器访问 http://localhost:5000
"""

import os
import io
import base64
import json
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for
)

from config import SERVER_HOST, SERVER_PORT, DEBUG, LIVENESS_ENABLED, FACE_RECOGNITION_THRESHOLD
from models import (
    init_db, get_all_users, get_user, add_user, update_user, delete_user,
    save_face_feature, get_face_feature, delete_face_feature, get_all_face_features,
    save_weight, get_user_weights, get_today_weight, get_today_weighed_users,
    get_rankings, export_ranking_excel,
    get_setting, set_setting,
)
from sdk.arcface_engine import FaceEngine


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 初始化人脸引擎
face_engine = FaceEngine()


def _is_liveness_enabled():
    """读取活体开关（优先数据库 settings，其次配置文件默认值）"""
    val = get_setting('liveness_enabled', None)
    if val is None:
        return LIVENESS_ENABLED
    return str(val).strip() in ('1', 'true', 'True', 'TRUE', 'on', 'ON')


# ─── 初始化 ──────────────────────────────────────────

@app.before_request
def _init_once():
    """首次请求时初始化数据库和人脸引擎"""
    if not hasattr(app, '_initialized'):
        init_db()
        # ArcFace 授权凭证 (优先从环境变量读取，其次从数据库配置，最后为空)
        import os
        app_id = os.environ.get('ARCFACE_APP_ID', '') or get_setting('arcface_app_id', '')
        sdk_key = os.environ.get('ARCFACE_SDK_KEY', '') or get_setting('arcface_sdk_key', '')
        face_engine.initialize()
        app._initialized = True


# ─── 页面路由 ────────────────────────────────────────

@app.route('/')
def index():
    """称重主页"""
    return render_template('index.html',
        demo_mode=face_engine.is_demo_mode())


@app.route('/dashboard')
def dashboard():
    """后台看板"""
    return render_template('dashboard.html',
        demo_mode=face_engine.is_demo_mode())


@app.route('/leaderboard')
def leaderboard():
    """大屏排名"""
    return render_template('leaderboard.html')


# ─── API: 人脸识别 ─────────────────────────────────

@app.route('/api/recognize', methods=['POST'])
def api_recognize():
    """人脸识别: 接收图片, 一次完成检测+活体+识别（合并 detect）"""
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': '缺少图片数据'}), 400

    try:
        image_data = base64.b64decode(data['image'].split(',')[-1])
    except Exception:
        return jsonify({'error': '图片解码失败'}), 400

    liveness_enabled = _is_liveness_enabled()

    # 一次检测完成活体+特征提取（SDK只检测1次）
    feature, liveness_result = face_engine.extract_feature_with_liveness(image_data)

    face_detected = feature is not None
    liveness_score = None
    liveness_ok = True

    if liveness_result:
        liveness_score = liveness_result[0].get('score')
        liveness_ok = liveness_result[0].get('is_live', False)

    if liveness_enabled and face_engine.is_liveness_available():
        if not liveness_ok:
            return jsonify({
                'recognized': False,
                'face_detected': face_detected,
                'liveness_enabled': True,
                'liveness_failed': True,
                'liveness_score': liveness_score,
                'message': '活体验证失败，请使用真实人脸并面对摄像头'
            })
    elif liveness_enabled and not face_engine.is_liveness_available():
        print('[app] Liveness enabled in config but engine support not available, bypassing')

    if not feature:
        return jsonify({
            'recognized': False,
            'face_detected': False,
            'liveness_enabled': liveness_enabled,
            'liveness_failed': False,
            'message': '未检测到有效人脸，请调整位置后重试'
        })

    enrolled = face_engine.get_cached_features()

    if not enrolled:
        return jsonify({
            'recognized': False,
            'face_detected': True,
            'liveness_enabled': liveness_enabled,
            'message': '底库为空, 请先在后台录入学员人脸'
        })

    result = face_engine.search(feature, enrolled)
    if result:
        user_id, similarity = result
        user = get_user(user_id)
        if user:
            return jsonify({
                'recognized': True,
                'face_detected': True,
                'liveness_enabled': liveness_enabled,
                'liveness_failed': False,
                'liveness_score': liveness_score,
                'user': {
                    'id': user['id'],
                    'name': user['name'],
                    'initial_weight': user['initial_weight'],
                    'face_image': user.get('face_image', ''),
                },
                'similarity': round(similarity, 4),
            })

    return jsonify({
        'recognized': False,
        'face_detected': True,
        'liveness_enabled': liveness_enabled,
        'liveness_failed': False,
        'liveness_score': liveness_score,
        'message': '未识别到匹配的学员'
    })


@app.route('/api/verify', methods=['POST'])
def api_verify():
    """1:1人脸验证：只与指定用户比对，不做活体（登录时已做活体）"""
    data = request.get_json()
    if not data or 'image' not in data or 'user_id' not in data:
        return jsonify({'error': '缺少参数'}), 400

    user_id = int(data['user_id'])

    try:
        image_data = base64.b64decode(data['image'].split(',')[-1])
    except Exception:
        return jsonify({'error': '图片解码失败'}), 400

    feature = face_engine.extract_feature(image_data)
    if not feature:
        return jsonify({'match': False, 'reason': 'no_face'})

    user_feature = face_engine.get_cached_user_feature(user_id)
    if not user_feature:
        return jsonify({'match': False, 'reason': 'no_enrollment'})

    similarity = face_engine.compare_feature(feature, user_feature)
    matched = similarity >= FACE_RECOGNITION_THRESHOLD
    return jsonify({
        'match': matched,
        'similarity': round(float(similarity), 4)
    })


@app.route('/api/face/detect', methods=['POST'])
def api_detect_face():
    """检测图片中是否有人脸"""
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': '缺少图片数据'}), 400

    try:
        image_data = base64.b64decode(data['image'].split(',')[-1])
    except Exception:
        return jsonify({'error': '图片解码失败'}), 400

    faces = face_engine.detect_faces(image_data)
    liveness_enabled = _is_liveness_enabled()
    liveness = []
    if faces and liveness_enabled and face_engine.is_liveness_available():
        liveness = face_engine.detect_liveness(image_data)
    return jsonify({
        'faces': faces,
        'count': len(faces),
        'liveness_enabled': liveness_enabled and face_engine.is_liveness_available(),
        'liveness': liveness
    })


# ─── API: 学员管理 ─────────────────────────────────

@app.route('/api/users', methods=['GET'])
def api_get_users():
    """获取所有学员"""
    users = get_all_users()
    # 移除敏感/二进制字段
    for u in users:
        u.pop('feature', None)
        # 保留 face_image 用于前端显示
    return jsonify({'users': users})


@app.route('/api/users', methods=['POST'])
def api_add_user():
    """添加学员"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '缺少学员姓名'}), 400

    user_id = add_user(
        name=data['name'],
        initial_weight=float(data.get('initial_weight', 0)),
        phone=data.get('phone', ''),
        note=data.get('note', ''),
        tice_weight=float(data.get('tice_weight', 0)),
    )

    # 如果有提供人脸图片, 保存人脸特征
    face_error = None
    if data.get('face_image'):
        try:
            image_data = base64.b64decode(data['face_image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(image_data):
                face_error = '活体验证失败，请使用真实人脸'
            else:
                feature = face_engine.extract_feature(image_data)
                if feature:
                    save_face_feature(user_id, feature, data['face_image'])
                    face_engine.invalidate_cache()
                else:
                    face_error = '未检测到有效人脸'
        except Exception as e:
            face_error = f'人脸处理失败: {str(e)}'

    resp = {'success': True, 'user_id': user_id}
    if face_error:
        resp['face_warning'] = face_error
    return jsonify(resp), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def api_update_user(user_id):
    """更新学员"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '无数据'}), 400

    update_user(
        user_id,
        name=data.get('name'),
        phone=data.get('phone'),
        initial_weight=data.get('initial_weight'),
        note=data.get('note'),
        tice_weight=data.get('tice_weight'),
        coach_id=data.get('coach_id'),
    )

    # 更新人脸特征
    face_error = None
    if data.get('face_image'):
        try:
            image_data = base64.b64decode(data['face_image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(image_data):
                face_error = '活体验证失败，请使用真实人脸'
            else:
                feature = face_engine.extract_feature(image_data)
                if feature:
                    save_face_feature(user_id, feature, data['face_image'])
                    face_engine.invalidate_cache()
                else:
                    face_error = '未检测到有效人脸'
        except Exception as e:
            face_error = f'人脸处理失败: {str(e)}'

    resp = {'success': True}
    if face_error:
        resp['face_warning'] = face_error
    return jsonify(resp)


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    """删除学员"""
    delete_user(user_id)
    face_engine.invalidate_cache()
    return jsonify({'success': True})


# ─── API: 人脸特征管理 ─────────────────────────────

@app.route('/api/users/<int:user_id>/face', methods=['POST'])
def api_enroll_face(user_id):
    """录入/更新人脸"""
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({'error': '缺少图片'}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({'error': '学员不存在'}), 404

    try:
        image_data = base64.b64decode(data['image'].split(',')[-1])
        # 活体验证
        liveness_enabled = _is_liveness_enabled()
        if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(image_data):
            return jsonify({'error': '活体验证失败，请确保是真实人脸'}), 400
        feature = face_engine.extract_feature(image_data)
        if not feature:
            return jsonify({'error': '未检测到有效人脸'}), 400
        save_face_feature(user_id, feature, data['image'])
        face_engine.invalidate_cache()
        return jsonify({'success': True, 'liveness_enabled': _is_liveness_enabled()})
    except Exception as e:
        return jsonify({'error': f'人脸录入失败: {str(e)}'}), 500


@app.route('/api/users/<int:user_id>/face', methods=['DELETE'])
def api_delete_face(user_id):
    """删除人脸特征"""
    delete_face_feature(user_id)
    face_engine.invalidate_cache()
    return jsonify({'success': True})


@app.route('/api/users/<int:user_id>/face/status', methods=['GET'])
def api_face_status(user_id):
    """查询人脸录入状态"""
    feat = get_face_feature(user_id)
    return jsonify({
        'enrolled': feat is not None and feat.get('feature') is not None,
        'has_image': bool(feat and feat.get('face_image')),
        'face_image': feat['face_image'] if feat else '',
    })


# ─── API: 称重 ──────────────────────────────────────

@app.route('/api/weigh', methods=['POST'])
def api_weigh():
    """保存体重记录"""
    data = request.get_json()
    if not data or 'user_id' not in data or 'weight' not in data:
        return jsonify({'error': '缺少参数'}), 400

    user_id = int(data['user_id'])
    weight_val = float(data['weight'])
    weigh_date = data.get('weigh_date', date.today().isoformat())

    # 检查重复
    existing = None
    if weigh_date == date.today().isoformat():
        existing = get_today_weight(user_id)
    else:
        from models import get_db
        with get_db() as db:
            row = db.execute(
                'SELECT * FROM weights WHERE user_id=? AND weigh_date=?',
                (user_id, weigh_date)
            ).fetchone()
            if row:
                existing = dict(row)

    if existing:
        return jsonify({
            'exists': True,
            'existing_weight': existing['weight'],
            'message': f'该学员今日已称重 ({existing["weight"]} kg), 是否覆盖?',
        }), 409

    save_weight(user_id, weight_val, weigh_date)
    return jsonify({'success': True})


@app.route('/api/weigh', methods=['PUT'])
def api_weigh_overwrite():
    """覆盖体重记录 (支持任意日期)"""
    data = request.get_json()
    if not data or 'user_id' not in data or 'weight' not in data:
        return jsonify({'error': '缺少参数'}), 400

    weigh_date = data.get('weigh_date', date.today().isoformat())
    save_weight(int(data['user_id']), float(data['weight']), weigh_date)
    return jsonify({'success': True})


@app.route('/api/today', methods=['GET'])
def api_today():
    """获取今日已称重学员"""
    users = get_today_weighed_users()
    return jsonify({'users': users})


@app.route('/api/users/<int:user_id>/weights', methods=['GET'])
def api_user_weights(user_id):
    """获取学员体重历史"""
    weights = get_user_weights(user_id)
    return jsonify({'weights': weights})


# ─── API: 排名 ──────────────────────────────────────

@app.route('/api/rankings/<period_type>', methods=['GET'])
def api_rankings(period_type):
    """获取排名数据"""
    if period_type not in ('week', 'month'):
        return jsonify({'error': '无效的周期类型 (week/month)'}), 400

    ref_date = request.args.get('ref_date')
    rankings = get_rankings(period_type, ref_date)
    return jsonify({'rankings': rankings})


@app.route('/api/rankings/<period_type>/export', methods=['GET'])
def api_export_rankings(period_type):
    """导出排名 Excel"""
    if period_type not in ('week', 'month'):
        return jsonify({'error': '无效的周期类型'}), 400

    ref_date = request.args.get('ref_date')
    filepath = export_ranking_excel(period_type, ref_date)

    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': '无数据可导出'}), 404

    return send_file(
        filepath,
        as_attachment=True,
        download_name=os.path.basename(filepath),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# ─── API: 系统设置 ─────────────────────────────────

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """获取所有设置"""
    from models import get_db
    with get_db() as db:
        rows = db.execute('SELECT * FROM settings').fetchall()
    return jsonify({'settings': {r['key']: r['value'] for r in rows}})


@app.route('/api/settings', methods=['POST'])
def api_set_settings():
    """批量保存设置"""
    data = request.get_json()
    if not data or 'settings' not in data:
        return jsonify({'error': '缺少设置数据'}), 400

    for key, value in data['settings'].items():
        set_setting(key, str(value))
    return jsonify({'success': True})


@app.route('/api/system/info', methods=['GET'])
def api_system_info():
    """获取系统信息"""
    import platform
    import sqlite3
    return jsonify({
        'demo_mode': face_engine.is_demo_mode(),
        'liveness_available': face_engine.is_liveness_available(),
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'db_path': os.path.abspath(os.path.join(os.path.dirname(__file__), 'db', 'weight.db')),
    })


# ─── 启动 ────────────────────────────────────────────

if __name__ == '__main__':
    print('='*50)
    print('  体重管理系统 v1.0')
    print('  Face: ' + ('DEMO 模式 (无 ArcFace SDK)' if face_engine.is_demo_mode() else 'ArcFace 引擎'))
    print('  URL: http://localhost:5000')
    print('='*50)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG)
