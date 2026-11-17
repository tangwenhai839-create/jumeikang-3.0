import sys, os, base64, json
from urllib import error as urlerror, parse as urlparse, request as urlrequest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, g
from werkzeug.security import generate_password_hash, check_password_hash
from models import (
    delete_weight,
    init_db, get_all_users, get_user, add_user, update_user, delete_user,
    exit_user, restore_user,
    get_user_periods, start_next_period, update_current_period_accommodation,
    save_face_feature, get_face_feature, delete_face_feature,
    save_coach_face_feature, get_coach_face_feature, delete_coach_face_feature, get_all_coach_face_features,
    save_weight, get_user_weights, get_today_weight, get_today_weighed_users,
    get_user_evening_weights,
    get_rankings, export_ranking_excel,
    get_setting, set_setting,
    add_coach, get_all_coaches, update_coach, delete_coach,
    ensure_coach_accounts, get_coach_account_by_username,
    get_coach_account_by_coach_id, get_coach_account,
    ensure_account_for_coach, update_coach_account, mark_account_login,
    add_operation_log, get_operation_logs,
)
from sdk.arcface_engine import FaceEngine
from excel_template import export_all_students, export_extra_training
from config import LIVENESS_ENABLED

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
# Require a deployment-specific signing key.
app.secret_key = os.environ['ADMIN_SECRET_KEY']
face_engine = FaceEngine()


@app.route('/manifest.webmanifest')
def pwa_manifest():
    response = send_file(
        os.path.join(app.static_folder, 'pwa', 'manifest.webmanifest'),
        mimetype='application/manifest+json',
    )
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response


@app.route('/service-worker.js')
def pwa_service_worker():
    response = send_file(
        os.path.join(app.static_folder, 'pwa', 'service-worker.js'),
        mimetype='application/javascript; charset=utf-8',
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

LODGING_API_BASE = os.environ.get('LODGING_API_BASE', 'http://127.0.0.1:3000/api').rstrip('/')
LODGING_ROOM_TYPES = {
    'SINGLE': '单人间',
    'DOUBLE': '双人间',
    'TRIPLE': '三人间',
    'QUAD': '四人间',
}


class LodgingServiceError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def _lodging_request(method, path, payload=None, timeout=8):
    """通过服务器内网调用住宿服务，避免绕过管理后台登录保护。"""
    body = None
    headers = {'Accept': 'application/json'}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urlrequest.Request(
        LODGING_API_BASE + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else None
    except urlerror.HTTPError as exc:
        message = '住宿服务请求失败'
        try:
            detail = json.loads(exc.read().decode('utf-8'))
            message = detail.get('message') or detail.get('error') or message
        except Exception:
            pass
        raise LodgingServiceError(str(message), exc.code) from exc
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LodgingServiceError('住宿服务暂时不可用，请稍后重试', 503) from exc


def _matching_lodging_rooms(room_type=None, has_air_conditioner=None, keyword=''):
    params = {}
    if room_type:
        params['roomType'] = room_type
    if isinstance(has_air_conditioner, bool):
        params['hasAirConditioner'] = 'true' if has_air_conditioner else 'false'
    if keyword:
        params['keyword'] = str(keyword).strip()
    query = urlparse.urlencode(params)
    rooms = _lodging_request('GET', '/rooms' + (('?' + query) if query else ''))
    if not isinstance(rooms, list):
        raise LodgingServiceError('住宿服务返回了无效的房间数据', 502)
    available = [
        room for room in rooms
        if int(room.get('availableCount') or 0) > 0 and room.get('status') != 'FULL'
    ]
    return sorted(available, key=lambda room: str(room.get('roomNumber') or ''))


def _lodging_assignment_payload(resident, fallback_room=None):
    resident = resident or {}
    room = resident.get('room') or fallback_room or {}
    room_type = room.get('roomType')
    return {
        'resident_id': resident.get('id'),
        'room_id': room.get('id') or resident.get('roomId'),
        'room_number': room.get('roomNumber'),
        'bed_number': resident.get('bedNumber'),
        'room_type': room_type,
        'room_type_label': LODGING_ROOM_TYPES.get(room_type, room_type or ''),
        'has_air_conditioner': bool(room.get('hasAirConditioner')),
        'exclusive_use': resident.get('exclusiveUse') is True,
        'contact_phone': resident.get('phone') or '',
        'capacity': room.get('capacity'),
        'occupied_count': room.get('occupiedCount'),
        'available_count': room.get('availableCount'),
        'status': room.get('status'),
    }


def _assign_lodging(candidates, user_id, name, contact_phone, exclusive_use=False):
    last_error = None
    for room in candidates:
        try:
            resident = _lodging_request('POST', '/rooms/{}/check-in'.format(int(room['id'])), {
                'name': name,
                'phone': contact_phone,
                'isStudent': True,
                'campUserId': int(user_id),
                'exclusiveUse': exclusive_use is True,
                'remark': '减重训练营入营同步，学员ID：{}'.format(user_id),
            })
            return _lodging_assignment_payload(resident, room)
        except LodgingServiceError as exc:
            last_error = exc
            # 提交后房间可能刚被其他人占满或删除；调用方只传入管理员所选房间。
            if exc.status in (400, 404, 409):
                continue
            raise
    if last_error:
        raise LodgingServiceError('所选房间刚刚被占用，请重新选择房间', 409)
    raise LodgingServiceError('所选房间没有空余床位', 409)


def _get_user_lodging(user_id):
    try:
        return _lodging_request('GET', '/rooms/camp-resident/{}'.format(int(user_id)))
    except LodgingServiceError as exc:
        if exc.status == 404:
            return None
        raise


def _change_user_lodging(user_id, name, accommodation, current=None):
    """新增、换房、切换独住或退宿；房间选择始终由管理员明确指定。"""
    if not isinstance(accommodation, dict) or accommodation.get('managed') is not True:
        return None
    if current is None:
        current = _get_user_lodging(user_id)
    if accommodation.get('enabled') is not True:
        if not current:
            return {'enabled': False, 'changed': False}
        _lodging_request(
            'POST',
            '/rooms/{}/check-out/{}'.format(int(current['roomId']), int(current['id'])),
        )
        return {'enabled': False, 'changed': True}

    try:
        room_id = int(accommodation.get('room_id') or 0)
    except (TypeError, ValueError):
        room_id = 0
    if room_id <= 0:
        raise LodgingServiceError('请选择具体入住房间', 400)
    exclusive_use = accommodation.get('exclusive_use') is True
    contact_phone = str(accommodation.get('contact_phone') or '').strip()
    if len(contact_phone) > 20:
        raise LodgingServiceError('住宿联系电话不能超过20个字符', 400)

    room = _lodging_request('GET', '/rooms/{}'.format(room_id))
    same_room = bool(current and int(current.get('roomId') or 0) == room_id)
    occupied_by_others = int(room.get('occupiedCount') or 0) - (1 if same_room else 0)
    if not same_room and (room.get('status') == 'FULL' or int(room.get('availableCount') or 0) <= 0):
        raise LodgingServiceError('所选房间已满，请重新选择', 409)
    if exclusive_use and occupied_by_others > 0:
        raise LodgingServiceError('整间独住只能选择没有其他人员入住的房间', 409)

    if current:
        resident = _lodging_request(
            'PATCH',
            '/rooms/resident/{}/stay'.format(int(current['id'])),
            {
                'roomId': room_id,
                'exclusiveUse': exclusive_use,
                'name': str(name).strip(),
                'phone': contact_phone,
            },
        )
        return {'enabled': True, 'changed': True, **_lodging_assignment_payload(resident, room)}

    assigned = _assign_lodging([room], user_id, str(name).strip(), contact_phone, exclusive_use)
    return {'enabled': True, 'changed': True, **assigned}


def _is_liveness_enabled():
    """读取活体开关（优先数据库 settings，其次配置文件默认值）"""
    val = get_setting('liveness_enabled', None)
    if val is None:
        return LIVENESS_ENABLED
    return str(val).strip() in ('1', 'true', 'True', 'TRUE', 'on', 'ON')


# 管理员账号/密码在数据库中的 settings key
ADMIN_USERNAME_KEY = 'admin_username'
ADMIN_PASSWORD_HASH_KEY = 'admin_password_hash'
DEFAULT_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_COACH_NAME = os.environ.get('ADMIN_COACH_NAME', '管理员')

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
    """Initialize the administrator on a new installation."""
    existing_user = get_setting(ADMIN_USERNAME_KEY)
    existing_hash = get_setting(ADMIN_PASSWORD_HASH_KEY)
    if not existing_user or not existing_hash:
        password = os.environ.get('ADMIN_INITIAL_PASSWORD', '')
        if len(password) < 12:
            raise RuntimeError('Set ADMIN_INITIAL_PASSWORD to at least 12 characters for first use.')
        if not any(coach['name'] == ADMIN_COACH_NAME for coach in get_all_coaches()):
            add_coach(ADMIN_COACH_NAME)
        set_setting(ADMIN_USERNAME_KEY, DEFAULT_ADMIN_USERNAME)
        set_setting(ADMIN_PASSWORD_HASH_KEY, generate_password_hash(password))
        existing_user = DEFAULT_ADMIN_USERNAME
        existing_hash = get_setting(ADMIN_PASSWORD_HASH_KEY)
    ensure_coach_accounts(
        ADMIN_COACH_NAME,
        existing_user or DEFAULT_ADMIN_USERNAME,
        existing_hash or '',
    )


def _get_admin_username():
    return get_setting(ADMIN_USERNAME_KEY) or DEFAULT_ADMIN_USERNAME


def _get_admin_password_hash():
    return get_setting(ADMIN_PASSWORD_HASH_KEY) or ''


def is_logged_in():
    return (
        session.get('admin_logged_in') is True
        and bool(session.get('account_id'))
        and bool(session.get('coach_id'))
    )


def is_admin():
    return is_logged_in() and session.get('role') == 'admin'


def _set_account_session(account):
    session.clear()
    session['admin_logged_in'] = True
    session['account_id'] = int(account['id'])
    session['coach_id'] = int(account['coach_id'])
    session['username'] = account['username']
    session['actor_name'] = account['coach_name']
    session['role'] = account['role']
    session.permanent = True


def _session_actor():
    return {
        'account_id': session.get('account_id'),
        'coach_id': session.get('coach_id'),
        'username': session.get('username', ''),
        'name': session.get('actor_name', ''),
        'role': session.get('role', ''),
    }


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


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            if request.path.startswith('/api/'):
                return jsonify({'error': '未登录，请先登录'}), 401
            return redirect(url_for('login_page'))
        if not is_admin():
            if request.path.startswith('/api/'):
                return jsonify({'error': '仅管理员可以执行此操作'}), 403
            return redirect(url_for('admin_index'))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_current_account():
    return {
        'current_account': _session_actor() if is_logged_in() else None,
        'current_is_admin': is_admin(),
    }


_AUDIT_ENDPOINTS = {
    'api_change_password': ('修改个人密码', '账号'),
    'api_add_user': ('添加学员', '学员'),
    'api_user': ('维护学员资料', '学员'),
    'api_camp_enter': ('办理学员入营', '学员'),
    'api_camp_exit': ('办理学员出营', '学员'),
    'api_camp_enter_next': ('办理下一期入营', '学员'),
    'api_camp_restore': ('恢复学员', '学员'),
    'api_user_face': ('维护学员人脸', '学员'),
    'api_settings': ('修改系统设置', '系统'),
    'api_add_coach': ('添加教练及账号', '教练'),
    'api_coach': ('维护教练资料', '教练'),
    'api_coach_face': ('维护教练人脸', '教练'),
    'api_update_coach_account': ('维护教练账号', '账号'),
    'api_export': ('导出排名报表', '报表'),
    'api_export_all': ('导出在营学员报表', '报表'),
    'api_export_extra_training': ('导出加练人员报表', '报表'),
    'api_export_preview': ('导出学员报表', '报表'),
    'api_save_weight': ('新增或修改称重记录', '称重'),
    'api_delete_weight': ('删除称重记录', '称重'),
    'api_logout': ('退出登录', '账号'),
}


def _audit_ip():
    return (
        request.headers.get('X-Real-IP')
        or (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        or request.remote_addr
        or ''
    )


@app.before_request
def _prepare_operation_audit():
    if not is_logged_in():
        return
    g.audit_actor = _session_actor()
    descriptor = _AUDIT_ENDPOINTS.get(request.endpoint)
    if not descriptor:
        return
    if request.endpoint == 'api_settings' and request.method != 'POST':
        return
    action, target_type = descriptor
    if request.endpoint == 'api_user':
        action = '删除学员' if request.method == 'DELETE' else '编辑学员资料'
    elif request.endpoint == 'api_coach':
        action = '删除教练' if request.method == 'DELETE' else '编辑教练资料'
    elif request.endpoint in ('api_user_face', 'api_coach_face'):
        action = ('删除' if request.method == 'DELETE' else '录入或更新') + target_type + '人脸'
    g.audit_action = action
    g.audit_target_type = target_type
    view_args = request.view_args or {}
    target_id = (
        view_args.get('user_id') or view_args.get('coach_id')
        or view_args.get('weigh_date') or view_args.get('period_type') or ''
    )
    g.audit_target_id = str(target_id)
    details = []
    data = request.get_json(silent=True) if request.is_json else None
    if isinstance(data, dict):
        if request.endpoint in ('api_add_user', 'api_camp_enter', 'api_add_coach') and data.get('name'):
            details.append('姓名：' + str(data.get('name'))[:80])
        if request.endpoint in ('api_save_weight',) and data.get('weigh_date'):
            details.append('日期：' + str(data.get('weigh_date'))[:20])
        if request.endpoint == 'api_settings' and isinstance(data.get('settings'), dict):
            details.append('设置项：' + '、'.join(sorted(data['settings'].keys())))
        if request.endpoint == 'api_update_coach_account' and data.get('username'):
            details.append('账号：' + str(data.get('username'))[:100])
    g.audit_detail = '；'.join(details)


@app.after_request
def _write_operation_audit(response):
    actor = getattr(g, 'audit_actor', None)
    action = getattr(g, 'audit_action', '')
    if not actor or not action:
        return response
    try:
        add_operation_log(
            account_id=actor.get('account_id'), coach_id=actor.get('coach_id'),
            actor_username=actor.get('username'), actor_name=actor.get('name'),
            actor_role=actor.get('role'), action=action,
            target_type=getattr(g, 'audit_target_type', ''),
            target_id=getattr(g, 'audit_target_id', ''),
            detail=getattr(g, 'audit_detail', ''), method=request.method,
            path=request.path, status_code=response.status_code, ip_address=_audit_ip(),
        )
    except Exception as exc:
        app.logger.warning('operation audit failed: %s', exc)
    return response


# ─── 登录/退出/改密 ─────────────────────────────────

@app.route('/login', methods=['GET'])
def login_page():
    """登录页面（已登录则跳转到首页）"""
    if is_logged_in():
        return redirect(url_for('admin_index'))
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """教练独立账号密码登录。"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': '请输入账号和密码'}), 400

    account = get_coach_account_by_username(username)
    if not account or not account.get('is_active'):
        return jsonify({'error': '账号或密码错误'}), 401
    expected_hash = account.get('password_hash') or ''
    if not expected_hash or not check_password_hash(expected_hash, password):
        return jsonify({'error': '账号或密码错误'}), 401

    _set_account_session(account)
    mark_account_login(account['id'])
    add_operation_log(
        account_id=account['id'], coach_id=account['coach_id'],
        actor_username=account['username'], actor_name=account['coach_name'],
        actor_role=account['role'], action='账号密码登录', target_type='账号',
        target_id=account['id'], method=request.method, path=request.path,
        status_code=200, ip_address=_audit_ip(),
    )
    return jsonify({
        'success': True,
        'account': {
            'username': account['username'], 'name': account['coach_name'],
            'role': account['role'],
        },
    })


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
    account = get_coach_account_by_coach_id(coach_id)
    if not account or not account.get('is_active'):
        return jsonify({'error': '该教练账号未启用，请联系管理员'}), 403

    _set_account_session(account)
    mark_account_login(account['id'])
    add_operation_log(
        account_id=account['id'], coach_id=account['coach_id'],
        actor_username=account['username'], actor_name=account['coach_name'],
        actor_role=account['role'], action='人脸登录', target_type='账号',
        target_id=account['id'], detail='相似度：' + str(round(similarity, 4)),
        method=request.method, path=request.path, status_code=200,
        ip_address=_audit_ip(),
    )
    return jsonify({
        'success': True,
        'liveness_enabled': liveness_enabled,
        'liveness_score': liveness_score,
        'coach': {'id': account['coach_id'], 'name': account['coach_name']},
        'account': {'username': account['username'], 'role': account['role']},
        'similarity': round(similarity, 4)
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """退出接口"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth-check', methods=['GET'])
def api_auth_check():
    """供同域管理模块校验管理员登录状态，不返回任何账户信息。"""
    if is_logged_in():
        return '', 204
    return '', 401


@app.route('/api/current-account', methods=['GET'])
@require_auth
def api_current_account():
    account = get_coach_account(session['account_id'])
    if not account:
        session.clear()
        return jsonify({'error': '账号不存在'}), 401
    return jsonify({
        'account': {
            'id': account['id'], 'coach_id': account['coach_id'],
            'username': account['username'], 'name': account['coach_name'],
            'role': account['role'], 'is_active': bool(account['is_active']),
            'password_set': bool(account.get('password_hash')),
            'face_enrolled': bool(account.get('face_enrolled')),
            'last_login_at': account.get('last_login_at') or '',
        }
    })


@app.route('/api/operation-logs', methods=['GET'])
@require_admin
def api_operation_logs():
    try:
        result = get_operation_logs(
            coach_id=request.args.get('coach_id') or None,
            action=request.args.get('action', ''),
            date_from=request.args.get('date_from', ''),
            date_to=request.args.get('date_to', ''),
            page=request.args.get('page', 1),
            page_size=request.args.get('page_size', 50),
        )
    except (TypeError, ValueError):
        return jsonify({'error': '筛选条件格式不正确'}), 400
    result['coaches'] = [
        {'id': c['id'], 'name': c['name']} for c in get_all_coaches()
    ]
    return jsonify(result)


@app.route('/api/change-password', methods=['POST'])
@require_auth
def api_change_password():
    """修改当前登录教练自己的密码。首次由人脸登录时可直接设置。"""
    data = request.get_json(silent=True) or {}
    old_password = data.get('old_password') or ''
    new_password = data.get('new_password') or ''
    confirm_password = data.get('confirm_password') or ''

    if not new_password:
        return jsonify({'error': '请填写新密码'}), 400
    if new_password != confirm_password:
        return jsonify({'error': '两次输入的新密码不一致'}), 400
    if len(new_password) < 6:
        return jsonify({'error': '新密码长度不能少于 6 位'}), 400

    account = get_coach_account(session['account_id'])
    if not account:
        return jsonify({'error': '账号不存在'}), 404
    expected_hash = account.get('password_hash') or ''
    if expected_hash and (not old_password or not check_password_hash(expected_hash, old_password)):
        return jsonify({'error': '旧密码错误'}), 401

    password_hash = generate_password_hash(new_password)
    update_coach_account(account['id'], password_hash=password_hash)
    if account.get('role') == 'admin':
        set_setting(ADMIN_PASSWORD_HASH_KEY, password_hash)
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


@app.route('/account')
@require_auth
def account_page():
    return render_template('account.html')


@app.route('/operation-logs')
@require_admin
def operation_logs_page():
    return render_template('operation_logs.html')


@app.route('/settings')
@require_admin
def settings_page():
    return render_template('settings.html')


@app.route('/exports')
@require_auth
def exports_page():
    return render_template('exports.html', demo_mode=face_engine.is_demo_mode())


@app.route('/weight-comparison')
@require_auth
def weight_comparison_page():
    return render_template('weight_comparison.html', today=date.today().isoformat())


@app.route('/camp-management')
@require_auth
def camp_management_page():
    return render_template('camp_management.html', demo_mode=face_engine.is_demo_mode())

# ─── API: 学员管理 ───────────────────────────
@app.route('/api/users', methods=['GET'])
@require_auth
def api_get_users():
    status = request.args.get('status', 'active')
    include_face = request.args.get('include_face', '1') not in ('0', 'false', 'False')
    users = get_all_users(status=status, include_face=include_face)
    coaches = get_all_coaches()
    if not is_admin():
        for coach in coaches:
            for field in ('account_id', 'username', 'account_role', 'account_active',
                          'password_set', 'last_login_at'):
                coach.pop(field, None)
    return jsonify({'users': users, 'coaches': coaches})

@app.route('/api/users', methods=['POST'])
@require_auth
def api_add_user():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '缺少姓名'}), 400
    user_id = add_user(
        data['name'], float(data.get('initial_weight', 0)), data.get('phone', ''),
        data.get('note', ''), float(data.get('tice_weight', 0)),
        int(data.get('coach_id', 0) or 0), data.get('enroll_date'),
        int(data.get('period_count', 1) or 1), 'active')
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

@app.route('/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@require_auth
def api_user(user_id):
    if request.method == 'GET':
        user = get_user(user_id)
        if not user:
            return jsonify({'error': '学员不存在'}), 404
        try:
            current_stay = _get_user_lodging(user_id)
            user['accommodation'] = (
                {'enabled': True, **_lodging_assignment_payload(current_stay)}
                if current_stay else {'enabled': False}
            )
        except LodgingServiceError as exc:
            user['accommodation'] = None
            user['accommodation_error'] = str(exc)
        return jsonify({'user': user})
    if request.method == 'DELETE':
        delete_user(user_id)
        return jsonify({'success': True})
    data = request.get_json()
    face_error = None
    if data:
        original_user = get_user(user_id)
        if not original_user:
            return jsonify({'error': '学员不存在'}), 404
        enroll_date = data.get('enroll_date')
        period_count = data.get('period_count')
        try:
            if enroll_date is not None:
                datetime.strptime(str(enroll_date), '%Y-%m-%d')
            if period_count is not None:
                period_count = max(1, int(period_count))
        except (TypeError, ValueError):
            return jsonify({'error': '入营日期或报名期数格式不正确'}), 400
        try:
            update_user(user_id, name=data.get('name'), phone=data.get('phone'),
                        initial_weight=data.get('initial_weight'), note=data.get('note'),
                        tice_weight=data.get('tice_weight'), coach_id=data.get('coach_id'),
                        enroll_date=enroll_date, period_count=period_count)
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        accommodation_result = None
        accommodation = data.get('accommodation')
        if isinstance(accommodation, dict) and accommodation.get('managed') is True:
            try:
                accommodation_result = _change_user_lodging(
                    user_id,
                    data.get('name') if data.get('name') is not None else original_user.get('name'),
                    accommodation,
                )
                update_current_period_accommodation(
                    user_id,
                    accommodation_result if accommodation_result.get('enabled') else {},
                )
            except LodgingServiceError as exc:
                update_user(
                    user_id,
                    name=original_user.get('name'), phone=original_user.get('phone'),
                    initial_weight=original_user.get('initial_weight'), note=original_user.get('note'),
                    tice_weight=original_user.get('tice_weight'), coach_id=original_user.get('coach_id'),
                    enroll_date=original_user.get('enroll_date'), period_count=original_user.get('period_count'),
                )
                return jsonify({'error': str(exc) + '，学员资料修改已撤销'}), exc.status
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
    if data and 'accommodation_result' in locals() and accommodation_result is not None:
        resp['accommodation'] = accommodation_result
    if face_error:
        resp['face_warning'] = face_error
    return jsonify(resp)


@app.route('/api/camp/enter', methods=['POST'])
@require_auth
def api_camp_enter():
    """办理入营并一次性完成基础档案。"""
    data = request.get_json() or {}
    required = {
        'name': '姓名', 'phone': '身高', 'initial_weight': '初始体重',
        'tice_weight': '体测体重', 'enroll_date': '入营日期',
        'coach_id': '责任教练', 'period_count': '报名期数'
    }
    missing = [label for key, label in required.items() if str(data.get(key, '')).strip() == '']
    if missing:
        return jsonify({'error': '请填写：' + '、'.join(missing)}), 400
    try:
        height = float(data['phone'])
        initial_weight = float(data['initial_weight'])
        tice_weight = float(data['tice_weight'])
        coach_id = int(data['coach_id'])
        period_count = max(1, int(data['period_count']))
        datetime.strptime(data['enroll_date'], '%Y-%m-%d')
    except (TypeError, ValueError):
        return jsonify({'error': '身高、体重、日期或报名期数格式不正确'}), 400
    if not 100 <= height <= 250:
        return jsonify({'error': '身高请填写 100-250cm'}), 400
    if initial_weight <= 0 or tice_weight <= 0:
        return jsonify({'error': '初始体重和体测体重必须大于0'}), 400
    if coach_id <= 0:
        return jsonify({'error': '请选择责任教练'}), 400

    accommodation = data.get('accommodation') or {}
    if not isinstance(accommodation, dict):
        return jsonify({'error': '住宿安排格式不正确'}), 400
    arrange_lodging = accommodation.get('enabled') is True
    lodging_candidates = []
    lodging_selected_room = None
    lodging_room_type = None
    lodging_has_air = None
    lodging_contact_phone = ''
    lodging_exclusive_use = False
    if arrange_lodging:
        lodging_room_type = str(accommodation.get('room_type') or '').upper() or None
        lodging_has_air = accommodation.get('has_air_conditioner', None)
        lodging_contact_phone = str(accommodation.get('contact_phone') or '').strip()
        lodging_exclusive_use = accommodation.get('exclusive_use') is True
        try:
            lodging_room_id = int(accommodation.get('room_id') or 0)
        except (TypeError, ValueError):
            lodging_room_id = 0
        if lodging_room_type and lodging_room_type not in LODGING_ROOM_TYPES:
            return jsonify({'error': '房型筛选条件不正确'}), 400
        if lodging_has_air is not None and not isinstance(lodging_has_air, bool):
            return jsonify({'error': '空调筛选条件不正确'}), 400
        if lodging_room_id <= 0:
            return jsonify({'error': '请选择具体入住房间'}), 400
        if len(lodging_contact_phone) > 20:
            return jsonify({'error': '住宿联系电话不能超过20个字符'}), 400
        try:
            lodging_candidates = _matching_lodging_rooms(lodging_room_type, lodging_has_air)
        except LodgingServiceError as exc:
            return jsonify({'error': str(exc)}), exc.status
        if not lodging_candidates:
            return jsonify({'error': '暂无符合筛选条件的可入住房间，请调整筛选条件'}), 409
        lodging_selected_room = next(
            (room for room in lodging_candidates if int(room.get('id') or 0) == lodging_room_id),
            None,
        )
        if lodging_selected_room is None:
            return jsonify({'error': '所选房间已满或不符合当前空调、房型条件，请重新选择'}), 409
        if lodging_exclusive_use and int(lodging_selected_room.get('occupiedCount') or 0) > 0:
            return jsonify({'error': '整间独住只能选择当前无人入住的房间'}), 409

    user_id = add_user(
        name=str(data['name']).strip(), initial_weight=initial_weight,
        phone=str(data['phone']).strip(), note=str(data.get('note', '') or '')[:500],
        tice_weight=tice_weight, coach_id=coach_id,
        enroll_date=data['enroll_date'], period_count=period_count,
        camp_status='active')

    lodging_assignment = None
    if arrange_lodging:
        try:
            lodging_assignment = _assign_lodging(
                [lodging_selected_room],
                user_id,
                str(data['name']).strip(),
                lodging_contact_phone,
                lodging_exclusive_use,
            )
        except LodgingServiceError as exc:
            try:
                delete_user(user_id)
            except Exception:
                app.logger.exception('住宿安排失败后回滚学员档案失败，user_id=%s', user_id)
                return jsonify({'error': '住宿安排失败，且学员档案需要人工检查，请联系管理员'}), 500
            return jsonify({'error': str(exc) + '，学员档案未创建'}), exc.status
        update_current_period_accommodation(user_id, lodging_assignment)

    face_warning = None
    if data.get('face_image'):
        try:
            img = base64.b64decode(data['face_image'].split(',')[-1])
            liveness_enabled = _is_liveness_enabled()
            if liveness_enabled and face_engine.is_liveness_available() and not face_engine.check_liveness(img):
                face_warning = '学员已建档，但人脸活体验证失败，请稍后补录人脸'
            else:
                feat = face_engine.extract_feature(img)
                if feat:
                    save_face_feature(user_id, feat, data['face_image'])
                    face_engine.invalidate_cache()
                else:
                    face_warning = '学员已建档，但未检测到有效人脸，请稍后补录'
        except Exception as exc:
            face_warning = '学员已建档，但人脸录入失败：' + str(exc)

    resp = {'success': True, 'user_id': user_id}
    if lodging_assignment:
        resp['accommodation'] = lodging_assignment
    if face_warning:
        resp['face_warning'] = face_warning
    return jsonify(resp), 201


@app.route('/api/camp/<int:user_id>/exit', methods=['POST'])
@require_auth
def api_camp_exit(user_id):
    """办理出营，保留完整历史档案。"""
    user = get_user(user_id)
    if not user:
        return jsonify({'error': '学员不存在'}), 404
    if user.get('camp_status', 'active') != 'active':
        return jsonify({'error': '该学员已经出营'}), 409
    data = request.get_json() or {}
    exit_date = data.get('exit_date') or date.today().isoformat()
    try:
        datetime.strptime(exit_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': '出营日期格式不正确'}), 400
    enroll_date = (user.get('enroll_date') or user.get('created_at') or '')[:10]
    if enroll_date and exit_date < enroll_date:
        return jsonify({'error': '出营日期不能早于入营日期'}), 400
    try:
        current_stay = _get_user_lodging(user_id)
    except LodgingServiceError as exc:
        return jsonify({'error': '暂时无法确认学员住宿状态：' + str(exc)}), exc.status
    exit_result = exit_user(user_id, exit_date, data.get('exit_note', ''))
    if not exit_result:
        return jsonify({'error': '办理出营失败'}), 409
    if current_stay:
        try:
            _lodging_request(
                'POST',
                '/rooms/{}/check-out/{}'.format(
                    int(current_stay['roomId']), int(current_stay['id'])
                ),
            )
        except LodgingServiceError as exc:
            restore_user(user_id, user.get('enroll_date'), user.get('period_count'))
            return jsonify({'error': '住宿退房失败，出营操作已撤销：' + str(exc)}), exc.status
    face_engine.invalidate_cache()
    return jsonify({
        'success': True,
        'accommodation_checked_out': bool(current_stay),
        **exit_result,
    })


@app.route('/api/camp/<int:user_id>/enter-next', methods=['POST'])
@require_auth
def api_camp_enter_next(user_id):
    """为已有学员办理下一期入营。"""
    user = get_user(user_id)
    if not user:
        return jsonify({'error': '学员不存在'}), 404
    if user.get('camp_status') == 'active':
        return jsonify({'error': '该学员当前已有在营期次'}), 409
    data = request.get_json() or {}
    required = {
        'enroll_date': '入营日期', 'initial_weight': '初始体重',
        'tice_weight': '体测体重', 'coach_id': '责任教练',
    }
    missing = [label for key, label in required.items() if str(data.get(key, '')).strip() == '']
    if missing:
        return jsonify({'error': '请填写：' + '、'.join(missing)}), 400
    try:
        datetime.strptime(str(data['enroll_date']), '%Y-%m-%d')
        initial_weight = float(data['initial_weight'])
        tice_weight = float(data['tice_weight'])
        coach_id = int(data['coach_id'])
        if initial_weight <= 0 or tice_weight <= 0 or coach_id <= 0:
            raise ValueError
        period_number = start_next_period(
            user_id, data['enroll_date'], coach_id, initial_weight, tice_weight,
        )
    except (TypeError, ValueError) as exc:
        message = str(exc) if str(exc) else '体重、日期或责任教练格式不正确'
        return jsonify({'error': message}), 400
    face_engine.invalidate_cache()
    return jsonify({'success': True, 'period_number': period_number})


@app.route('/api/camp/<int:user_id>/restore', methods=['POST'])
@require_auth
def api_camp_restore(user_id):
    """恢复误办出营的学员档案。"""
    data = request.get_json() or {}
    if not restore_user(user_id, data.get('enroll_date'), data.get('period_count')):
        return jsonify({'error': '该档案无法恢复'}), 409
    face_engine.invalidate_cache()
    return jsonify({'success': True})

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
@require_admin
def api_settings():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if data and 'settings' in data:
            settings_data = data['settings'] if isinstance(data['settings'], dict) else {}
            requested_username = str(settings_data.get('admin_username') or '').strip()
            if requested_username:
                try:
                    update_coach_account(session['account_id'], username=requested_username)
                except ValueError as exc:
                    return jsonify({'error': str(exc)}), 400
                session['username'] = requested_username
                set_setting(ADMIN_USERNAME_KEY, requested_username)
            for k, v in settings_data.items():
                if k not in (ADMIN_USERNAME_KEY, ADMIN_PASSWORD_HASH_KEY):
                    set_setting(k, str(v))
            return jsonify({'success': True})
        return jsonify({'error': '无数据'}), 400
    from models import get_db
    with get_db() as db:
        rows = db.execute('SELECT * FROM settings').fetchall()
    values = {
        r['key']: r['value'] for r in rows
        if r['key'] != ADMIN_PASSWORD_HASH_KEY
    }
    values[ADMIN_USERNAME_KEY] = session.get('username', DEFAULT_ADMIN_USERNAME)
    return jsonify({'settings': values})

@app.route('/api/system/info')
@require_admin
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
    coaches = get_all_coaches()
    if not is_admin():
        private_fields = ('account_id', 'username', 'account_role', 'account_active',
                          'password_set', 'last_login_at')
        for coach in coaches:
            for field in private_fields:
                coach.pop(field, None)
    return jsonify({'coaches': coaches, 'can_manage_accounts': is_admin()})

@app.route('/api/coaches', methods=['POST'])
@require_admin
def api_add_coach():
    data = request.get_json(silent=True) or {}
    if not data or not data.get('name'):
        return jsonify({'error': '缺少姓名'}), 400
    username = str(data.get('username') or data.get('phone') or '').strip()
    if not username:
        return jsonify({'error': '请输入教练登录账号'}), 400
    initial_password = str(data.get('initial_password') or '')
    if initial_password and len(initial_password) < 6:
        return jsonify({'error': '初始密码不能少于6位'}), 400
    coach_id = add_coach(str(data['name']).strip(), str(data.get('phone', '')).strip())
    try:
        ensure_account_for_coach(
            coach_id, username,
            generate_password_hash(initial_password) if initial_password else '',
            is_active=True,
        )
    except ValueError as exc:
        delete_coach(coach_id)
        return jsonify({'error': str(exc)}), 400
    return jsonify({'success': True, 'coach_id': coach_id}), 201

@app.route('/api/coaches/<int:coach_id>', methods=['PUT', 'DELETE'])
@require_admin
def api_coach(coach_id):
    if request.method == 'DELETE':
        account = get_coach_account_by_coach_id(coach_id)
        if account and account.get('role') == 'admin':
            return jsonify({'error': '管理员绑定教练不能删除'}), 400
        delete_coach(coach_id)
        return jsonify({'success': True})
    data = request.get_json()
    if data:
        update_coach(coach_id, name=data.get('name'), phone=data.get('phone'))
    return jsonify({'success': True})


@app.route('/api/coaches/<int:coach_id>/face', methods=['POST', 'DELETE'])
@require_admin
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
@require_admin
def api_coach_face_status(coach_id):
    """查询教练人脸录入状态"""
    feat = get_coach_face_feature(coach_id)
    return jsonify({
        'enrolled': feat is not None and feat.get('feature') is not None,
        'has_image': bool(feat and feat.get('face_image')),
        'face_image': feat['face_image'] if feat else ''
    })


@app.route('/api/coaches/<int:coach_id>/account', methods=['PUT'])
@require_admin
def api_update_coach_account(coach_id):
    data = request.get_json(silent=True) or {}
    account = get_coach_account_by_coach_id(coach_id)
    if not account:
        return jsonify({'error': '该教练尚未绑定账号'}), 404
    username = data.get('username') if 'username' in data else None
    new_password = str(data.get('new_password') or '')
    if new_password and len(new_password) < 6:
        return jsonify({'error': '新密码不能少于6位'}), 400
    is_active = data.get('is_active') if 'is_active' in data else None
    try:
        update_coach_account(
            account['id'], username=username,
            password_hash=(generate_password_hash(new_password) if new_password else None),
            is_active=is_active,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if int(account['id']) == int(session['account_id']):
        refreshed = get_coach_account(account['id'])
        session['username'] = refreshed['username']
        set_setting(ADMIN_USERNAME_KEY, refreshed['username'])
    return jsonify({'success': True})


@app.route('/api/export/all')
@require_auth
def api_export_all():
    # 只导出当前在营学员；已出营和待下一期入营学员不进入该报表。
    users = get_all_users(status='active', include_face=False)
    result = []
    for u in users:
        weights = get_user_weights(u['id'], limit=10000)
        evening_weights = get_user_evening_weights(u['id'], limit=10000)
        result.append((u, weights, evening_weights))
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
            WHERE u.camp_status='active' AND u.id NOT IN (
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
            WHERE u.camp_status='active' AND (w_yest.weight - w_today.weight) < 0.2
            ORDER BY u.name
        ''', (today, yesterday)).fetchall()
        for r in rows2:
            low_loss.append(dict(r))

        # 3. 超过8:10:59称重：从8:11:00起计为超时的学员
        late_weighed = []
        rows3 = db.execute(
            'SELECT u.id, u.name, u.phone, u.initial_weight, u.tice_weight, '
            'c.name as coach_name, w.weight as today_weight, w.recorded_at '
            'FROM users u '
            'LEFT JOIN coaches c ON c.id = u.coach_id '
            'JOIN weights w ON w.user_id = u.id AND w.weigh_date = ? '
            "WHERE u.camp_status='active' AND w.recorded_at > ? || ' 08:10:59'"
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

@app.route('/api/today-extra')
@require_auth
def api_today_extra():
    """返回今日加练人员及加练原因(JSON)"""
    from models import get_db
    from datetime import date, timedelta
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    result = {}
    with get_db() as db:
        rows = db.execute('''
            SELECT u.id, u.name FROM users u
            WHERE u.camp_status='active'
              AND u.id NOT IN (SELECT DISTINCT user_id FROM weights WHERE weigh_date = ?)
        ''', (today,)).fetchall()
        for r in rows:
            d = dict(r)
            result[d['id']] = {'user_id': d['id'], 'name': d['name'], 'reasons': ['今日未称重']}
        rows2 = db.execute('''
            SELECT u.id, u.name FROM users u
            JOIN weights w_today ON w_today.user_id=u.id AND w_today.weigh_date=?
            JOIN weights w_yest ON w_yest.user_id=u.id AND w_yest.weigh_date=?
            WHERE u.camp_status='active' AND (w_yest.weight - w_today.weight) < 0.2
        ''', (today, yesterday)).fetchall()
        for r in rows2:
            d = dict(r)
            if d['id'] not in result:
                result[d['id']] = {'user_id': d['id'], 'name': d['name'], 'reasons': []}
            result[d['id']]['reasons'].append('掉秤不足0.2斤')
        rows3 = db.execute(
            'SELECT u.id, u.name FROM users u '
            'JOIN weights w ON w.user_id=u.id AND w.weigh_date=? '
            "WHERE u.camp_status='active' AND w.recorded_at > ? || ' 08:10:59'",
            (today, today)).fetchall()
        for r in rows3:
            d = dict(r)
            if d['id'] not in result:
                result[d['id']] = {'user_id': d['id'], 'name': d['name'], 'reasons': []}
            result[d['id']]['reasons'].append('超时称重(8:11起)')
    for item in result.values():
        item['reason'] = '、'.join(item['reasons'])
    return jsonify(list(result.values()))

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




# --- Face image API (for data table lazy loading) ---
@app.route('/api/users/<int:user_id>/face-image')
@require_auth
def api_user_face_image(user_id):
    from models import get_face_feature
    feat = get_face_feature(user_id)
    if feat and feat.get('face_image'):
        return jsonify({'face_image': feat['face_image']})
    return jsonify({'face_image': ''})


# --- Data table page ---
@app.route('/data-table')
@require_auth
def data_table_page():
    return render_template('data_table.html')


# --- Morning/evening weight comparison API ---
@app.route('/api/weight-comparison')
@require_auth
def api_weight_comparison():
    compare_date = (request.args.get('date') or date.today().isoformat()).strip()
    try:
        compare_date = date.fromisoformat(compare_date).isoformat()
    except (TypeError, ValueError):
        return jsonify({'error': '日期格式无效，请使用 YYYY-MM-DD'}), 400

    from models import get_db
    with get_db() as db:
        rows = db.execute('''
            SELECT u.id, u.name, u.coach_id,
                   COALESCE(c.name, '未分配') AS coach_name,
                   w.weight AS morning_weight,
                   ew.weight AS evening_weight
            FROM users u
            LEFT JOIN coaches c ON c.id = u.coach_id
            LEFT JOIN weights w
                   ON w.user_id = u.id AND w.weigh_date = ?
            LEFT JOIN evening_weights ew
                   ON ew.user_id = u.id AND ew.weigh_date = ?
            WHERE u.camp_status = 'active'
            ORDER BY
                CASE WHEN w.weight IS NOT NULL AND ew.weight IS NOT NULL THEN 0 ELSE 1 END,
                COALESCE(c.name, ''), u.name
        ''', (compare_date, compare_date)).fetchall()

    students = []
    summary = {
        'total': len(rows),
        'completed': 0,
        'higher': 0,
        'lower': 0,
        'same': 0,
        'pending': 0,
    }
    for row in rows:
        item = dict(row)
        morning = item.get('morning_weight')
        evening = item.get('evening_weight')
        difference = None

        if morning is None or evening is None:
            summary['pending'] += 1
            if morning is None and evening is None:
                status = 'missing_both'
            elif morning is None:
                status = 'missing_morning'
            else:
                status = 'missing_evening'
        else:
            difference = round(float(evening) - float(morning), 2)
            summary['completed'] += 1
            if difference > 0:
                status = 'higher'
                summary['higher'] += 1
            elif difference < 0:
                status = 'lower'
                summary['lower'] += 1
            else:
                status = 'same'
                summary['same'] += 1

        item['difference'] = difference
        item['status'] = status
        students.append(item)

    return jsonify({
        'date': compare_date,
        'summary': summary,
        'students': students,
    })


# --- Batch weights API (for data table performance) ---
@app.route('/api/all-weights')
@require_auth
def api_all_weights():
    from models import get_db
    with get_db() as db:
        rows = db.execute('''
            SELECT user_id, weigh_date, weight, note, id, period_id
            FROM weights
            ORDER BY user_id, weigh_date
        ''').fetchall()
    return jsonify({'weights': [dict(r) for r in rows]})


# --- Weight record CRUD API ---
@app.route('/api/weights/<int:user_id>', methods=['POST'])
@require_auth
def api_save_weight(user_id):
    from models import save_weight
    data = request.get_json()
    if not data or 'weigh_date' not in data or 'weight' not in data:
        return jsonify({'error': 'missing params'}), 400
    note = str(data.get('note', ''))[:500] if 'note' in data else None
    save_weight(user_id, float(data['weight']), data['weigh_date'], note=note)
    return jsonify({'success': True})


@app.route('/api/weights/<int:user_id>/<path:weigh_date>', methods=['DELETE'])
@require_auth
def api_delete_weight(user_id, weigh_date):
    delete_weight(user_id, weigh_date)
    return jsonify({'success': True})


if __name__ == '__main__':
    print('=' * 50)
    print('  体重管理后台 (管理端)')
    print(f'  ArcFace: {"Demo" if face_engine.is_demo_mode() else "Real"}')
    print('  URL: http://localhost:5001')
    print('=' * 50)
    app.run(host=os.environ.get('ADMIN_HOST', '127.0.0.1'), port=5001, debug=False)
