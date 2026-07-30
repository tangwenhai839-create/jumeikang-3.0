import sys, os, base64, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from models import (
    init_db, get_all_users, get_user, add_user, update_user, delete_user,
    save_face_feature, get_face_feature, delete_face_feature,
    save_coach_face_feature, get_coach_face_feature, delete_coach_face_feature, get_all_coach_face_features,
    save_weight, get_user_weights, get_today_weight, get_today_weighed_users,
    get_rankings, export_ranking_excel,
    get_setting, set_setting,
    add_coach, get_all_coaches, update_coach, delete_coach,
)
from sdk.arcface_engine import FaceEngine
from excel_template import export_all_students, export_extra_training
from config import LIVENESS_ENABLED

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
# session 密钥：优先读取环境变量，否则使用固定兜底密钥（部署时应设置环境变量）
app.secret_key = os.environ.get('ADMIN_SECRET_KEY', 'weight-system-admin-secret-key-2026')
face_engine = FaceEngine()


def _is_liveness_enabled():
    """读取活体开关（优先数据库 settings，其次配置文件默认值）"""
    val = get_setting('liveness_enabled', None)
    if val is None:
        return LIVENESS_ENABLED
    return str(val).strip() in ('1', 'true', 'True', 'TRUE', 'on', 'ON')


# 管理员账号/密码在数据库中的 settings key
ADMIN_USERNAME_KEY = 'admin_username'
ADMIN_PASSWORD_HASH_KEY = 'admin_password_hash'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'

@app.before_request
def _init():
    if not hasattr(app, '_initialized'):
        init_db()
        app_id = os.environ.get('ARCFACE_APP_ID', '') or get_setting('arcface_app_id', '')
        sdk_key = os.environ.get('ARCFACE_SDK_KEY', '') or get_setting('arcface_sdk_key', '')
        face_engine.initialize()
        _ensure_default_admin()
        app._initialized = True


def _ensure_default_admin():
    """首次启动时写入默认管理员账号密码（仅当数据库中不存在时）。"""
    existing_user = get_setting(ADMIN_USERNAME_KEY)
    existing_hash = get_setting(ADMIN_PASSWORD_HASH_KEY)
    if not existing_user or not existing_hash:
        set_setting(ADMIN_USERNAME_KEY, DEFAULT_ADMIN_USERNAME)
        set_setting(ADMIN_PASSWORD_HASH_KEY, generate_password_hash(DEFAULT_ADMIN_PASSWORD))
        print(f'[AdminAuth] 已创建默认管理员账号: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}')
        print('[AdminAuth] 请在登录后尽快到“设置”中修改密码')


def _get_admin_username():
    return get_setting(ADMIN_USERNAME_KEY) or DEFAULT_ADMIN_USERNAME


def _get_admin_password_hash():
    return get_setting(ADMIN_PASSWORD_HASH_KEY) or ''


def is_logged_in():
    return session.get('admin_logged_in') is True


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            # API 返回 401，页面跳转到登录页
            if request.path.startswith('/api/'):
                return jsonify({'error': '未登录，请先登录'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return wrapper


# ─── 登录/退出/改密 ─────────────────────────────────

@app.route('/login', methods=['GET'])
def login_page():
    """登录页面（已登录则跳转到首页）"""
    if is_logged_in():
        return redirect(url_for('admin_index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """登录接口"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': '请输入账号和密码'}), 400

    expected_username = _get_admin_username()
    expected_hash = _get_admin_password_hash()

    if username != expected_username:
        return jsonify({'error': '账号或密码错误'}), 401
    if not expected_hash or not check_password_hash(expected_hash, password):
        return jsonify({'error': '账号或密码错误'}), 401

    session['admin_logged_in'] = True
    session.permanent = True
    return jsonify({'success': True})


@app.route('/api/login/face', methods=['POST'])
def api_login_face():
    """教练人脸登录接口：只搜索教练人脸库"""
    data = request.get_json(silent=True) or {}
    image_b64 = data.get('image') or ''
    if not image_b64:
        return jsonify({'error': '缺少图片数据'}), 400

    try:
        image_data = base64.b64decode(image_b64.split(',')[-1])
    except Exception:
        return jsonify({'error': '图片解码失败'}), 400

    liveness_enabled = _is_liveness_enabled()
    liveness_score = None

    # 活体验证
    if liveness_enabled and face_engine.is_liveness_available():
        liveness_result = face_engine.detect_liveness(image_data)
        if liveness_result:
            liveness_score = liveness_result[0].get('score')
            if not liveness_result[0].get('is_live', False):
                return jsonify({'error': '活体验证失败，请使用真实人脸并面对摄像头'}), 400
        else:
            return jsonify({'error': '活体验证失败，未检测到活体人脸'}), 400

    feature = face_engine.extract_feature(image_data)
    if not feature:
        return jsonify({'error': '未检测到人脸，请重新拍照'}), 400

    enrolled = get_all_coach_face_features()
    if not enrolled:
        return jsonify({'error': '暂无教练人脸底库，请先录入'}), 401

    result = face_engine.search(feature, enrolled)
    if not result:
        return jsonify({'error': '未识别到匹配的教练人脸'}), 401

    coach_id, similarity = result
    coaches = get_all_coaches()
    coach = next((c for c in coaches if c['id'] == coach_id), None)
    if not coach:
        return jsonify({'error': '识别失败'}), 401

    session['admin_logged_in'] = True
    session['coach_id'] = coach_id
    session.permanent = True
    return jsonify({
        'success': True,
        'liveness_enabled': liveness_enabled,
        'liveness_score': liveness_score,
        'coach': {'id': coach['id'], 'name': coach['name']},
        'similarity': round(similarity, 4)
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """退出接口"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/change-password', methods=['POST'])
@require_auth
def api_change_password():
    """修改管理员密码"""
    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not old_password or not new_password:
        return jsonify({'error': '请填写旧密码和新密码'}), 400
    if new_password != confirm_password:
        return jsonify({'error': '两次输入的新密码不一致'}), 400
    if len(new_password) < 6:
        return jsonify({'error': '新密码长度不能少于 6 位'}), 400

    expected_hash = _get_admin_password_hash()
    if not expected_hash or not check_password_hash(expected_hash, old_password):
        return jsonify({'error': '旧密码错误'}), 401

    set_setting(ADMIN_PASSWORD_HASH_KEY, generate_password_hash(new_password))
    return jsonify({'success': True})


@app.route('/api/face/detect', methods=['POST'])
def api_detect_face():
    """检测图片中是否有人脸（登录页用）"""
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


@app.route('/')
@require_auth
def admin_index():
    return render_template('admin.html', demo_mode=face_engine.is_demo_mode())

@app.route('/settings')
@require_auth
def settings_page():
    return render_template('settings.html')


@app.route('/exports')
@require_auth
def exports_page():
    return render_template('exports.html', demo_mode=face_engine.is_demo_mode())

# ─── API: 学员管理 ───────────────────────────
@app.route('/api/users', methods=['GET'])
@require_auth
def api_get_users():
    users = get_all_users()
    coaches = get_all_coaches()
    return jsonify({'users': users, 'coaches': coaches})

@app.route('/api/users', methods=['POST'])
@require_auth
def api_add_user():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '缺少姓名'}), 400
    user_id = add_user(data['name'], float(data.get('initial_weight', 0)), data.get('phone', ''), data.get('note', ''), float(data.get('tice_weight', 0)))
    face_error = None
    if data.get('face_image'):
        try:
            img = base64.b64decode(data['face_image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(img):
                face_error = '活体验证失败，请使用真实人脸'
            else:
                feat = face_engine.extract_feature(img)
                if feat:
                    save_face_feature(user_id, feat, data['face_image'])
                else:
                    face_error = '未检测到有效人脸'
        except Exception as e:
            face_error = f'人脸处理失败: {str(e)}'

    resp = {'success': True, 'user_id': user_id}
    if face_error:
        resp['face_warning'] = face_error
    return jsonify(resp), 201

@app.route('/api/users/<int:user_id>', methods=['PUT', 'DELETE'])
@require_auth
def api_user(user_id):
    if request.method == 'DELETE':
        delete_user(user_id)
        return jsonify({'success': True})
    data = request.get_json()
    face_error = None
    if data:
        update_user(user_id, name=data.get('name'), phone=data.get('phone'),
                    initial_weight=data.get('initial_weight'), note=data.get('note'),
                    tice_weight=data.get('tice_weight'), coach_id=data.get('coach_id'))
        if data.get('face_image'):
            try:
                img = base64.b64decode(data['face_image'].split(',')[-1])
                liveness_enabled = _is_liveness_enabled()
                if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(img):
                    face_error = '活体验证失败，请使用真实人脸'
                else:
                    feat = face_engine.extract_feature(img)
                    if feat:
                        save_face_feature(user_id, feat, data['face_image'])
                    else:
                        face_error = '未检测到有效人脸'
            except Exception as e:
                face_error = f'人脸处理失败: {str(e)}'

    resp = {'success': True}
    if face_error:
        resp['face_warning'] = face_error
    return jsonify(resp)

@app.route('/api/users/<int:user_id>/face', methods=['POST', 'DELETE'])
@require_auth
def api_user_face(user_id):
    if request.method == 'DELETE':
        delete_face_feature(user_id)
        return jsonify({'success': True})
    data = request.get_json()
    if data and 'image' in data:
        try:
            img = base64.b64decode(data['image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(img):
                return jsonify({'error': '活体验证失败，请确保是真实人脸'}), 400
            feat = face_engine.extract_feature(img)
            if not feat:
                return jsonify({'error': '未检测到有效人脸'}), 400
            save_face_feature(user_id, feat, data['image'])
            return jsonify({'success': True, 'liveness_enabled': liveness_enabled})
        except Exception as e:
            return jsonify({'error': f'失败: {str(e)}'}), 500
    return jsonify({'error': '缺图片'}), 400

@app.route('/api/users/<int:user_id>/face/status')
@require_auth
def api_face_status(user_id):
    feat = get_face_feature(user_id)
    return jsonify({'enrolled': feat and feat.get('feature') is not None, 'face_image': feat['face_image'] if feat else ''})

@app.route('/api/users/<int:user_id>/weights')
@require_auth
def api_user_weights(user_id):
    return jsonify({'weights': get_user_weights(user_id)})

# ─── API: 排名/导出 ──────────────────────────
@app.route('/api/rankings/<period_type>')
@require_auth
def api_rankings(period_type):
    if period_type not in ('week', 'month'):
        return jsonify({'error': '无效周期'}), 400
    return jsonify({'rankings': get_rankings(period_type, request.args.get('ref_date'))})

@app.route('/api/rankings/<period_type>/export')
@require_auth
def api_export(period_type):
    if period_type not in ('week', 'month'):
        return jsonify({'error': '无效周期'}), 400
    fp = export_ranking_excel(period_type, request.args.get('ref_date'))
    if not fp or not os.path.exists(fp):
        return jsonify({'error': '无数据'}), 404
    return send_file(fp, as_attachment=True, download_name=os.path.basename(fp),
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── API: 系统 ───────────────────────────────
@app.route('/api/settings', methods=['GET', 'POST'])
@require_auth
def api_settings():
    if request.method == 'POST':
        data = request.get_json()
        if data and 'settings' in data:
            for k, v in data['settings'].items(): set_setting(k, str(v))
            return jsonify({'success': True})
        return jsonify({'error': '无数据'}), 400
    from models import get_db
    with get_db() as db:
        rows = db.execute('SELECT * FROM settings').fetchall()
    return jsonify({'settings': {r['key']: r['value'] for r in rows}})

@app.route('/api/system/info')
@require_auth
def api_system_info():
    import platform
    return jsonify({
        'demo_mode': face_engine.is_demo_mode(),
        'liveness_available': face_engine.is_liveness_available(),
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'db_path': os.path.abspath(os.path.join(os.path.dirname(__file__), 'db', 'weight.db')),
    })


# ─── 导出学员详细体重记录 ─────────────────────

# ─── API: 教练管理 ───────────────────────────
@app.route('/api/coaches', methods=['GET'])
@require_auth
def api_get_coaches():
    return jsonify({'coaches': get_all_coaches()})

@app.route('/api/coaches', methods=['POST'])
@require_auth
def api_add_coach():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '缺少姓名'}), 400
    coach_id = add_coach(data['name'], data.get('phone', ''))
    return jsonify({'success': True, 'coach_id': coach_id}), 201

@app.route('/api/coaches/<int:coach_id>', methods=['PUT', 'DELETE'])
@require_auth
def api_coach(coach_id):
    if request.method == 'DELETE':
        delete_coach(coach_id)
        return jsonify({'success': True})
    data = request.get_json()
    if data:
        update_coach(coach_id, name=data.get('name'), phone=data.get('phone'))
    return jsonify({'success': True})


@app.route('/api/coaches/<int:coach_id>/face', methods=['POST', 'DELETE'])
@require_auth
def api_coach_face(coach_id):
    """录入/删除教练人脸"""
    if request.method == 'DELETE':
        delete_coach_face_feature(coach_id)
        return jsonify({'success': True})
    data = request.get_json()
    if data and 'image' in data:
        try:
            img = base64.b64decode(data['image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(img):
                return jsonify({'error': '活体验证失败，请确保是真实人脸'}), 400
            feat = face_engine.extract_feature(img)
            if feat:
                save_coach_face_feature(coach_id, feat, data['image'])
                return jsonify({'success': True, 'liveness_enabled': liveness_enabled})
            return jsonify({'error': '人脸提取失败'}), 400
        except Exception:
            return jsonify({'error': '处理失败'}), 500
    return jsonify({'error': '缺图片'}), 400


@app.route('/api/coaches/<int:coach_id>/face/status')
@require_auth
def api_coach_face_status(coach_id):
    """查询教练人脸录入状态"""
    feat = get_coach_face_feature(coach_id)
    return jsonify({
        'enrolled': feat is not None and feat.get('feature') is not None,
        'has_image': bool(feat and feat.get('face_image')),
        'face_image': feat['face_image'] if feat else ''
    })


@app.route('/api/export/all')
@require_auth
def api_export_all():
    users = get_all_users()
    result = []
    for u in users:
        weights = get_user_weights(u['id'])
        result.append((u, weights))
    fp = export_all_students(result)
    if fp and os.path.exists(fp):
        return send_file(fp, as_attachment=True, download_name=os.path.basename(fp),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return jsonify({'error': '无学员数据'}), 500

@app.route('/api/export/extra-training')
@require_auth
def api_export_extra_training():
    """导出加练人员名单：今日未称重 + 今日掉秤<0.2斤"""
    from models import get_db
    from datetime import date, timedelta

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    not_weighed = []
    low_loss = []

    with get_db() as db:
        # 1. 今日未称重：所有学员中没有今日体重记录的
        rows = db.execute('''
            SELECT u.id, u.name, u.phone, u.initial_weight, u.tice_weight,
                   c.name as coach_name
            FROM users u
            LEFT JOIN coaches c ON c.id = u.coach_id
            WHERE u.id NOT IN (
                SELECT DISTINCT user_id FROM weights WHERE weigh_date = ?
            )
            ORDER BY u.name
        ''', (today,)).fetchall()
        for r in rows:
            not_weighed.append(dict(r))

        # 2. 今日掉秤<0.2斤：有今日体重且有昨日体重的学员，差值<0.2
        rows2 = db.execute('''
            SELECT u.id, u.name, u.phone, u.initial_weight, u.tice_weight,
                   c.name as coach_name,
                   w_today.weight as today_weight,
                   w_yest.weight as yesterday_weight,
                   (w_yest.weight - w_today.weight) as loss
            FROM users u
            LEFT JOIN coaches c ON c.id = u.coach_id
            JOIN weights w_today ON w_today.user_id = u.id AND w_today.weigh_date = ?
            JOIN weights w_yest ON w_yest.user_id = u.id AND w_yest.weigh_date = ?
            WHERE (w_yest.weight - w_today.weight) < 0.2
            ORDER BY u.name
        ''', (today, yesterday)).fetchall()
        for r in rows2:
            low_loss.append(dict(r))

        # 3. 超过8:01称重：今日体重记录时间超过8:01的学员
        late_weighed = []
        rows3 = db.execute(
            'SELECT u.id, u.name, u.phone, u.initial_weight, u.tice_weight, '
            'c.name as coach_name, w.weight as today_weight, w.recorded_at '
            'FROM users u '
            'LEFT JOIN coaches c ON c.id = u.coach_id '
            'JOIN weights w ON w.user_id = u.id AND w.weigh_date = ? '
            "WHERE w.recorded_at > ? || ' 08:01:00'" 
            'ORDER BY u.name',
            (today, today)
        ).fetchall()
        for r in rows3:
            late_weighed.append(dict(r))

    fp = export_extra_training(not_weighed, low_loss, late_weighed)
    if fp and os.path.exists(fp):
        return send_file(fp, as_attachment=True, download_name=os.path.basename(fp),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return jsonify({'error': '生成失败'}), 500

@app.route('/api/export/student/<int:user_id>/preview')
@require_auth
def api_export_preview(user_id):
    u = get_user(user_id)
    weights = get_user_weights(user_id)
    if not u:
        return jsonify({'error': '不存在'}), 404
    weights_sorted = sorted(weights, key=lambda w: w['weigh_date'])
    return jsonify({
        'user': {'name': u['name'], 'initial_weight': u.get('initial_weight', 0)},
        'weight_count': len(weights_sorted),
        'first_date': weights_sorted[0]['weigh_date'] if weights_sorted else None,
        'last_date': weights_sorted[-1]['weigh_date'] if weights_sorted else None,
    })



if __name__ == '__main__':
    print('=' * 50)
    print('  体重管理后台 (管理端)')
    print(f'  ArcFace: {"Demo" if face_engine.is_demo_mode() else "Real"}')
    print('  URL: http://localhost:5001')
    print('  首次启动默认账号: admin / admin123')
    print('  登录后请到“设置”修改密码')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)
