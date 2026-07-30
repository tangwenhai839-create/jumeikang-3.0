"""
体重管理系统 - Windows 管理端

功能: 学员管理、人脸录入、数据导出、系统设置

运行: python main.py
打包: pyinstaller --onefile --windowed --icon=icon.ico main.py
"""

import sys
import os
import json
import requests
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QLabel, QLineEdit, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QHeaderView, QSplitter, QFrame, QProgressBar,
    QComboBox, QDateEdit, QGroupBox, QStatusBar, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont, QIcon


# ─── 配置 ──────────────────────────────────────────
CONFIG_FILE = 'admin_config.json'
DEFAULT_SERVER = 'http://localhost:5000'


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'server_url': DEFAULT_SERVER}


def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


# ─── API 客户端 ───────────────────────────────────
class ApiClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def get(self, path):
        resp = requests.get(self.base_url + path, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def post(self, path, data=None):
        resp = requests.post(self.base_url + path, json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def put(self, path, data=None):
        resp = requests.put(self.base_url + path, json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path):
        resp = requests.delete(self.base_url + path, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def detect_face(self, image_b64):
        resp = requests.post(self.base_url + '/api/face/detect',
                             json={'image': image_b64}, timeout=10)
        resp.raise_for_status()
        return resp.json()


def check_liveness_from_detect(api, image_b64):
    """调用 /api/face/detect 检查人脸和活体，返回 (ok, message)"""
    try:
        data = api.detect_face(image_b64)
        if data.get('count', 0) == 0:
            return False, '未检测到人脸'
        if data.get('liveness_enabled') and data.get('liveness'):
            live_info = data['liveness'][0]
            if not live_info.get('is_live'):
                return False, '活体验证失败，请使用真实人脸'
        return True, ''
    except Exception as e:
        return True, ''  # 检测接口异常时放行，由后端最终校验


# ─── 添加/编辑学员对话框 ─────────────────────────


class StudentDetailDialog(QDialog):
    """学员体重详情对话框"""
    def __init__(self, api, user_id, user_name, parent=None):
        super().__init__(parent)
        self.api = api
        self.user_id = user_id
        self.setWindowTitle(f'体重详情 - {user_name}')
        self.setMinimumSize(500, 400)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        self.info_label.setStyleSheet('font-size: 14px; padding: 8px; background: #f5f5f5; border-radius: 6px;')
        layout.addWidget(self.info_label)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['日期', '体重 (kg)', '录入时间'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        btn = QPushButton('关闭')
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def load_data(self):
        try:
            user = self.api.get('/api/users')
            u = next((s for s in user.get('users', []) if s['id'] == self.user_id), None)
            if u:
                self.info_label.setText(f'学员: {u["name"]}  |  初始: {u.get("initial_weight","--")} kg  |  最新: {u.get("latest_weight","--")} kg')
            weights = self.api.get(f'/api/users/{self.user_id}/weights')
            rows = weights.get('weights', [])
            self.table.setRowCount(len(rows))
            for i, w in enumerate(rows):
                self.table.setItem(i, 0, QTableWidgetItem(w.get('weigh_date', '')))
                self.table.setItem(i, 1, QTableWidgetItem(str(w.get('weight', ''))))
                self.table.setItem(i, 2, QTableWidgetItem((w.get('recorded_at') or '')[:19]))
        except Exception as e:
            self.info_label.setText(f'加载失败: {e}')
class StudentDialog(QDialog):
    def __init__(self, api, student=None, parent=None):
        super().__init__(parent)
        self.api = api
        self.student = student
        self.captured_image = None
        self.liveness_passed = False
        self.setWindowTitle('编辑学员' if student else '添加学员')
        self.setMinimumWidth(400)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.weight_input = QLineEdit()
        self.weight_input.setPlaceholderText('初始体重 (kg)')
        self.phone_input = QLineEdit()
        self.note_input = QLineEdit()

        layout.addRow('姓名 *:', self.name_input)
        layout.addRow('初始体重:', self.weight_input)
        layout.addRow('手机号:', self.phone_input)
        layout.addRow('备注:', self.note_input)

        # 人脸录入
        face_group = QGroupBox('人脸录入 (可选)')
        face_layout = QVBoxLayout()
        self.face_label = QLabel('点击下方按钮打开摄像头拍照')
        self.face_label.setAlignment(Qt.AlignCenter)
        self.face_label.setMinimumHeight(200)
        self.face_label.setStyleSheet('background: #f0f0f0; border-radius: 8px;')
        self.capture_btn = QPushButton('📷 打开摄像头拍照')
        self.capture_btn.clicked.connect(self.capture_face)
        face_layout.addWidget(self.face_label)
        face_layout.addWidget(self.capture_btn)
        face_group.setLayout(face_layout)
        layout.addRow(face_group)

        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        if self.student:
            self.name_input.setText(self.student.get('name', ''))
            self.weight_input.setText(str(self.student.get('initial_weight', '')))
            self.phone_input.setText(self.student.get('phone', ''))
            self.note_input.setText(self.student.get('note', ''))
            if self.student.get('face_image'):
                self.show_face_image(self.student['face_image'])

    def capture_face(self):
        """打开摄像头拍照并检测活体"""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                QMessageBox.warning(self, '错误', '无法打开摄像头')
                return

            ret, frame = cap.read()
            cap.release()

            if ret:
                import base64
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                img_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()

                # 调用后端检测人脸+活体
                self.face_label.setText('活体检测中...')
                QApplication.processEvents()
                try:
                    data = self.api.post('/api/face/detect', {'image': img_b64})
                    liveness_enabled = data.get('liveness_enabled', False)
                    liveness = data.get('liveness', [])
                    live_info = liveness[0] if liveness else None

                    if not liveness_enabled:
                        self.liveness_passed = True
                        self.face_label.setText('⚠️ 活体检测已关闭')
                    elif live_info and live_info.get('is_live'):
                        self.liveness_passed = True
                        self.face_label.setText('✅ 活体通过')
                    else:
                        self.liveness_passed = False
                        self.face_label.setText('❌ 非活体，请使用真实人脸')
                        QMessageBox.warning(self, '活体验证失败', '检测到非活体，请使用真实人脸重新拍照')
                        return
                except Exception as e:
                    self.liveness_passed = True
                    self.face_label.setText('检测接口异常，放行')

                self.captured_image = img_b64
                self.show_face_image(self.captured_image)
            else:
                QMessageBox.warning(self, '错误', '拍照失败')
        except ImportError:
            QMessageBox.warning(self, '提示', '需要安装 opencv-python: pip install opencv-python')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'摄像头错误: {e}')

    def show_face_image(self, img_data):
        try:
            import base64
            from io import BytesIO
            data = base64.b64decode(img_data.split(',')[1])
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.face_label.setPixmap(pixmap.scaled(300, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except:
            pass

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, '提示', '请输入姓名')
            return
        self.accept()

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'initial_weight': float(self.weight_input.text()) if self.weight_input.text() else 0,
            'phone': self.phone_input.text().strip(),
            'note': self.note_input.text().strip(),
            'face_image': self.captured_image or '',
        }


# ─── 主窗口 ────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.api = ApiClient(self.config.get('server_url', DEFAULT_SERVER))
        self.setWindowTitle('体重管理 - Windows 管理端')
        self.setMinimumSize(900, 600)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 导航栏 (暗色)
        nav_widget = QWidget()
        nav_widget.setObjectName("navBar")
        nav_widget.setFixedHeight(50)
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(16, 0, 16, 0)
        self.nav_brand = QLabel('⚖️  体重管理系统')
        self.nav_brand.setStyleSheet('color: #fff; font-size: 16px; font-weight: 700; letter-spacing: 1px;')
        self.status_label = QLabel('⏳ 连接中...')
        self.status_label.setStyleSheet('color: #f0ad4e; padding: 4px 8px; font-size: 13px;')
        self.connect_btn = QPushButton('🔄 重连')
        self.settings_btn = QPushButton('⚙️ 设置')
        for btn in [self.connect_btn, self.settings_btn]:
            btn.setStyleSheet('background: transparent; color: #fff; border: 1px solid rgba(255,255,255,0.25); border-radius: 6px; padding: 6px 14px; font-size: 12px;')
            btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.clicked.connect(self.test_connection)
        self.settings_btn.clicked.connect(self.show_settings)
        nav_layout.addWidget(self.nav_brand)
        nav_layout.addStretch()
        nav_layout.addWidget(self.status_label)
        nav_layout.addWidget(self.connect_btn)
        nav_layout.addWidget(self.settings_btn)
        layout.addWidget(nav_widget)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_student_tab(), '👥 学员管理')
        self.tabs.addTab(self.create_ranking_tab(), '🏆 排名查看')
        self.tabs.addTab(self.create_export_tab(), '📊 数据导出')
        self.tabs.addTab(self.create_settings_tab(), '⚙️ 设置')
        self.tabs.addTab(self.create_system_tab(), 'ℹ️ 系统信息')
        layout.addWidget(self.tabs)

        self.statusBar().showMessage('就绪')
        QTimer.singleShot(500, self.test_connection)


        self.face_batch_btn = QPushButton('📷 批量录入人脸')
        self.face_batch_btn.clicked.connect(self.batch_enroll)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.face_batch_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 学员表格
        self.student_table = QTableWidget()
        self.student_table.setColumnCount(7)
        self.student_table.setHorizontalHeaderLabels(['ID', '姓名', '初始体重', '最新体重', '人脸状态', '注册日期', '操作'])
        self.student_table.horizontalHeader().setStretchLastSection(True)
        self.student_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.student_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.student_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.student_table.doubleClicked.connect(self.on_student_double_click)
        layout.addWidget(self.student_table)

        return widget

    def create_export_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel('从服务器导出排名数据为 Excel 文件')
        info.setStyleSheet('font-size: 13px; color: #666; margin-bottom: 8px; padding: 8px 0;')
        layout.addWidget(info)

        form = QHBoxLayout()
        form.addWidget(QLabel('周期:'))
        self.export_period = QComboBox()
        self.export_period.addItems(['本周', '本月'])
        form.addWidget(self.export_period)
        form.addWidget(QLabel('日期:'))
        self.export_date = QDateEdit()
        self.export_date.setCalendarPopup(True)
        self.export_date.setDate(datetime.now().date())
        form.addWidget(self.export_date)
        form.addStretch()
        layout.addLayout(form)

        self.export_btn = QPushButton('📥 导出排名 Excel')
        self.export_btn.clicked.connect(self.export_data)
        self.export_btn.setMinimumHeight(40)
        layout.addWidget(self.export_btn)

        layout.addStretch()
        return widget

    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group1 = QGroupBox('ArcFace SDK 配置')
        form1 = QFormLayout()
        self.sdk_appid_input = QLineEdit()
        self.sdk_appid_input.setPlaceholderText('输入 APP_ID')
        self.sdk_key_input = QLineEdit()
        self.sdk_key_input.setPlaceholderText('输入 SDK_KEY')
        form1.addRow('APP_ID:', self.sdk_appid_input)
        form1.addRow('SDK_KEY:', self.sdk_key_input)
        group1.setLayout(form1)
        layout.addWidget(group1)

        group2 = QGroupBox('识别参数')
        form2 = QFormLayout()
        self.threshold_input = QLineEdit('0.8')
        self.threshold_input.setPlaceholderText('0.65-0.95 推荐 0.8')
        self.weekday_combo = QComboBox()
        self.weekday_combo.addItems(['周一', '周日'])
        self.liveness_checkbox = QCheckBox('启用人脸活体验证（防止照片/屏幕攻击）')
        self.liveness_checkbox.setChecked(True)
        form2.addRow('识别阈值:', self.threshold_input)
        form2.addRow('周起始日:', self.weekday_combo)
        form2.addRow('活体检测:', self.liveness_checkbox)
        group2.setLayout(form2)
        layout.addWidget(group2)

        layout.addStretch()

        btn_row = QHBoxLayout()
        load_btn = QPushButton('🔄 读取当前配置')
        load_btn.clicked.connect(self.load_settings_from_server)
        save_btn = QPushButton('💾 保存配置')
        save_btn.clicked.connect(self.save_settings_to_server)
        save_btn.setMinimumHeight(36)
        btn_row.addWidget(load_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        return widget

    def create_system_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.system_info = QTextEdit()
        self.system_info.setReadOnly(True)
        self.system_info.setMinimumHeight(200)
        layout.addWidget(self.system_info)

        refresh_info_btn = QPushButton('🔄 刷新系统信息')
        refresh_info_btn.clicked.connect(self.load_system_info)
        layout.addWidget(refresh_info_btn)
        layout.addStretch()
        return widget

    def load_settings_from_server(self):
        try:
            data = self.api.get('/api/settings')
            s = data.get('settings', {})
            self.sdk_appid_input.setText(s.get('arcface_app_id', ''))
            self.sdk_key_input.setText(s.get('arcface_sdk_key', ''))
            self.threshold_input.setText(s.get('recognition_threshold', '0.8'))
            self.weekday_combo.setCurrentText('周日' if s.get('week_start_day') == '6' else '周一')
            self.liveness_checkbox.setChecked(s.get('liveness_enabled') not in ('0', 'false', 'False'))
            self.statusBar().showMessage('配置已加载')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'加载失败: {e}')

    def save_settings_to_server(self):
        try:
            settings = {
                'arcface_app_id': self.sdk_appid_input.text().strip(),
                'arcface_sdk_key': self.sdk_key_input.text().strip(),
                'recognition_threshold': self.threshold_input.text().strip(),
                'week_start_day': '6' if self.weekday_combo.currentText() == '周日' else '0',
                'liveness_enabled': '1' if self.liveness_checkbox.isChecked() else '0',
            }
            self.api.post('/api/settings', {'settings': settings})
            QMessageBox.information(self, '完成', '配置已保存到服务器')
            self.statusBar().showMessage('配置已保存')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'保存失败: {e}')

    # ─── 功能函数 ─────────────────────────────────

    def test_connection(self):
        self.status_label.setText('⏳ 连接中...')
        self.status_label.setStyleSheet('color: #f0ad4e; padding: 4px 8px;')
        self.statusBar().showMessage('正在连接服务器...')
        QTimer.singleShot(100, self._connect_check)

    def _connect_check(self):
        try:
            info = self.api.get('/api/system/info')
            self.status_label.setText('✅ 已连接')
            self.status_label.setStyleSheet('color: #2ecc71; padding: 4px 8px;')
            self.statusBar().showMessage('连接成功')
            QTimer.singleShot(200, self.load_students)
            QTimer.singleShot(400, self.load_rankings)
            QTimer.singleShot(600, self.load_system_info)
        except Exception as e:
            self.status_label.setText('❌ 连接失败')
            self.status_label.setStyleSheet('color: #e74c3c; padding: 4px 8px;')
            self.statusBar().showMessage('连接失败，请检查服务器')

    def show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('设置')
        dialog.setMinimumWidth(400)
        layout = QFormLayout(dialog)

        url_input = QLineEdit(self.config.get('server_url', DEFAULT_SERVER))
        layout.addRow('服务器地址:', url_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() == QDialog.Accepted:
            self.config['server_url'] = url_input.text().strip()
            save_config(self.config)
            self.api = ApiClient(self.config['server_url'])
            self.test_connection()



    def on_student_double_click(self, index):
        row = index.row()
        uid = self.student_table.item(row, 0)
        name = self.student_table.item(row, 1)
        if uid and name:
            StudentDetailDialog(self.api, int(uid.text()), name.text(), self).exec_()

    def show_student_detail(self, user_id, user_name):
        StudentDetailDialog(self.api, user_id, user_name, self).exec_()

    # ─── 功能: 排名 ─────────────────────────────
    def create_ranking_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('周期:'))
        self.rank_period = QComboBox()
        self.rank_period.addItems(['本周', '本月'])
        self.rank_period.currentTextChanged.connect(self.load_rankings)
        controls.addWidget(self.rank_period)
        controls.addWidget(QLabel('日期:'))
        self.rank_date = QDateEdit()
        self.rank_date.setCalendarPopup(True)
        self.rank_date.setDate(datetime.now().date())
        self.rank_date.dateChanged.connect(self.load_rankings)
        controls.addWidget(self.rank_date)
        controls.addStretch()
        self.rank_refresh_btn = QPushButton('🔄 刷新')
        self.rank_refresh_btn.clicked.connect(self.load_rankings)
        controls.addWidget(self.rank_refresh_btn)
        layout.addLayout(controls)

        self.rank_table = QTableWidget()
        self.rank_table.setColumnCount(6)
        self.rank_table.setHorizontalHeaderLabels(['排名', '姓名', '期初体重', '期末体重', '掉秤率', '趋势'])
        self.rank_table.horizontalHeader().setStretchLastSection(True)
        self.rank_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rank_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rank_table.doubleClicked.connect(self.on_rank_double_click)
        layout.addWidget(self.rank_table)
        hint = QLabel('双击学员行查看体重详情')
        hint.setStyleSheet('color: #999; font-size: 11px; padding: 4px 0;')
        layout.addWidget(hint)
        return widget

    def load_rankings(self):
        try:
            period_map = {'本周': 'week', '本月': 'month'}
            period = period_map.get(self.rank_period.currentText(), 'week')
            ref_date = self.rank_date.date().toString('yyyy-MM-dd')
            data = self.api.get(f'/api/rankings/{period}?ref_date={ref_date}')
            rankings = data.get('rankings', [])
            self.rank_table.setRowCount(len(rankings))
            for i, r in enumerate(rankings):
                rate = r.get('change_rate', 0)
                self.rank_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
                self.rank_table.setItem(i, 1, QTableWidgetItem(r['name']))
                self.rank_table.setItem(i, 2, QTableWidgetItem(f"{r.get('first_weight','')} kg"))
                self.rank_table.setItem(i, 3, QTableWidgetItem(f"{r.get('last_weight','')} kg"))
                self.rank_table.setItem(i, 4, QTableWidgetItem(f"{rate:.2f}%"))
                self.rank_table.setItem(i, 5, QTableWidgetItem('📉' if rate <= 0 else '📈'))
            self.statusBar().showMessage(f'{len(rankings)} 人')
        except Exception as e:
            self.statusBar().showMessage(f'排名加载失败')

    def on_rank_double_click(self, index):
        row = index.row()
        name = self.rank_table.item(row, 1)
        if not name: return
        try:
            data = self.api.get('/api/users')
            for s in data.get('users', []):
                if s['name'] == name.text():
                    StudentDetailDialog(self.api, s['id'], name.text(), self).exec_()
                    break
        except:
            pass

    def load_students(self):
        try:
            data = self.api.get('/api/users')
            students = data.get('users', [])
            self.student_table.setRowCount(len(students))

            for i, s in enumerate(students):
                face_status = '✅ 已录入' if s.get('face_image') else '❌ 未录入'
                self.student_table.setItem(i, 0, QTableWidgetItem(str(s['id'])))
                self.student_table.setItem(i, 1, QTableWidgetItem(s['name']))
                self.student_table.setItem(i, 2, QTableWidgetItem(f"{s.get('initial_weight', '--')} kg"))
                self.student_table.setItem(i, 3, QTableWidgetItem(f"{s.get('latest_weight', '--')} kg" if s.get('latest_weight') else '--'))
                self.student_table.setItem(i, 4, QTableWidgetItem(face_status))
                self.student_table.setItem(i, 5, QTableWidgetItem((s.get('created_at') or '')[:10]))

                # 操作按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                edit_btn = QPushButton('✏️')
                edit_btn.setFixedWidth(36)
                sid = s['id']
                edit_btn.clicked.connect(lambda checked, uid=sid: self.edit_student(uid))
                del_btn = QPushButton('🗑️')
                del_btn.setFixedWidth(36)
                del_btn.clicked.connect(lambda checked, uid=sid: self.delete_student(uid))
                face_btn = QPushButton('📷')
                face_btn.setFixedWidth(36)
                face_btn.clicked.connect(lambda checked, uid=sid: self.enroll_face(uid))
                btn_layout.addWidget(edit_btn)
                btn_layout.addWidget(del_btn)
                btn_layout.addWidget(face_btn)
                self.student_table.setCellWidget(i, 6, btn_widget)

            self.statusBar().showMessage(f'已加载 {len(students)} 名学员')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'加载学员失败: {e}')

    def add_student(self):
        dialog = StudentDialog(self.api, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.api.post('/api/users', data)
                self.load_students()
                self.statusBar().showMessage(f'学员 {data["name"]} 添加成功')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'添加失败: {e}')

    def edit_student(self, user_id):
        data = self.api.get('/api/users')
        student = None
        for s in data.get('users', []):
            if s['id'] == user_id:
                student = s
                break
        if not student:
            return

        dialog = StudentDialog(self.api, student=student, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.api.put(f'/api/users/{user_id}', data)
                self.load_students()
                self.statusBar().showMessage(f'学员 {data["name"]} 已更新')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'更新失败: {e}')

    def delete_student(self, user_id):
        reply = QMessageBox.question(self, '确认删除', '确定删除该学员? 相关体重记录也会被删除。',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.api.delete(f'/api/users/{user_id}')
                self.load_students()
                self.statusBar().showMessage('学员已删除')
            except Exception as e:
                QMessageBox.warning(self, '错误', f'删除失败: {e}')

    def enroll_face(self, user_id):
        """单独录入人脸"""
        try:
            import cv2
            import base64
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                QMessageBox.warning(self, '错误', '无法打开摄像头')
                return
            ret, frame = cap.read()
            cap.release()
            if not ret:
                QMessageBox.warning(self, '错误', '拍照失败')
                return

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            img_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()

            # 先检测活体
            try:
                detect_data = self.api.post('/api/face/detect', {'image': img_b64})
                liveness_enabled = detect_data.get('liveness_enabled', False)
                liveness = detect_data.get('liveness', [])
                live_info = liveness[0] if liveness else None
                if liveness_enabled and (not live_info or not live_info.get('is_live')):
                    QMessageBox.warning(self, '活体验证失败', '检测到非活体，请使用真实人脸重新拍照')
                    return
            except Exception:
                pass  # 检测接口失败时放行，后端会再校验

            self.api.post(f'/api/users/{user_id}/face', {'image': img_b64})
            self.load_students()
            self.statusBar().showMessage('人脸录入成功')
        except ImportError:
            QMessageBox.warning(self, '提示', '需要安装 opencv-python')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'人脸录入失败: {e}')

    def batch_enroll(self):
        """逐个为未录入人脸的学员拍照"""
        try:
            import cv2
            import base64
            data = self.api.get('/api/users')
            unenrolled = [s for s in data.get('users', []) if not s.get('face_image')]

            if not unenrolled:
                QMessageBox.information(self, '提示', '所有学员已录入人脸')
                return

            for s in unenrolled:
                reply = QMessageBox.question(
                    self, f'录入人脸: {s["name"]}',
                    f'为学员 "{s["name"]}" 录入人脸?\n点击 Yes 打开摄像头, No 跳过',
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                if reply == QMessageBox.Cancel:
                    break
                if reply == QMessageBox.No:
                    continue

                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    QMessageBox.warning(self, '错误', '无法打开摄像头')
                    break
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    continue

                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                img_b64 = 'data:image/jpeg;base64,' + base64.b64encode(buffer).decode()

                # 先检测活体
                try:
                    detect_data = self.api.post('/api/face/detect', {'image': img_b64})
                    liveness_enabled = detect_data.get('liveness_enabled', False)
                    liveness = detect_data.get('liveness', [])
                    live_info = liveness[0] if liveness else None
                    if liveness_enabled and (not live_info or not live_info.get('is_live')):
                        QMessageBox.warning(self, '活体验证失败', f'学员 {s["name"]}: 非活体，跳过')
                        continue
                except Exception:
                    pass

                self.api.post(f'/api/users/{s["id"]}/face', {'image': img_b64})
                self.load_students()
                self.statusBar().showMessage(f'{s["name"]} 人脸已录入')

            self.load_students()
        except ImportError:
            QMessageBox.warning(self, '提示', '需要安装 opencv-python')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'批量录入失败: {e}')

    def export_data(self):
        try:
            period_map = {'本周': 'week', '本月': 'month'}
            period = period_map.get(self.export_period.currentText(), 'week')
            ref_date = self.export_date.date().toString('yyyy-MM-dd')
            url = f'/api/rankings/{period}/export?ref_date={ref_date}'

            resp = requests.get(self.api.base_url + url, timeout=30)
            if resp.status_code != 200:
                QMessageBox.warning(self, '错误', '导出失败: 无数据')
                return

            # 保存到桌面
            import re
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            cd = resp.headers.get('Content-Disposition', '')
            fname = '体重排名.xlsx'
            match = re.search(r'filename=(.+)', cd)
            if match:
                fname = match.group(1).strip('"\'')
            filepath = os.path.join(desktop, fname)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            QMessageBox.information(self, '导出成功', f'排名文件已保存到:\n{filepath}')
            self.statusBar().showMessage(f'已导出: {filepath}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'导出失败: {e}')

    def load_system_info(self):
        try:
            info = self.api.get('/api/system/info')
            text = f"""
            <h3>系统信息</h3>
            <table>
            <tr><td><b>平台:</b></td><td>{info.get('platform', '--')}</td></tr>
            <tr><td><b>Python:</b></td><td>{info.get('python_version', '--')}</td></tr>
            <tr><td><b>人脸引擎:</b></td><td>{'⚠️ Demo 模式' if info.get('demo_mode') else '✅ ArcFace'}</td></tr>
            <tr><td><b>数据库:</b></td><td>{info.get('db_path', '--')}</td></tr>
            <tr><td><b>服务器:</b></td><td>{self.api.base_url}</td></tr>
            </table>
            """
            self.system_info.setHtml(text)
        except Exception as e:
            self.system_info.setHtml(f'<p style="color:red">获取失败: {e}</p>')


# ─── 启动 ──────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 网页风格 QSS 样式表
    app.setStyleSheet('''
        QMainWindow, QDialog {
            background: #f0f2f5;
        }
        QWidget {
            font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
            font-size: 13px;
            color: #333;
        }
        /* 导航栏 */
        QWidget#navBar {
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1a1a2e, stop:1 #16213e);
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }
        /* 选项卡 */
        QTabWidget::pane {
            background: #f0f2f5;
            border: none;
            padding: 8px;
        }
        QTabBar::tab {
            background: #e0e0e0;
            color: #555;
            padding: 10px 22px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-size: 13px;
            font-weight: 500;
        }
        QTabBar::tab:selected {
            background: #fff;
            color: #e94560;
            font-weight: 700;
        }
        QTabBar::tab:hover:!selected {
            background: #d0d0d0;
        }
        /* 分组卡片 */
        QGroupBox {
            background: #fff;
            border-radius: 10px;
            border: none;
            margin-top: 10px;
            padding: 18px 14px 14px 14px;
            font-size: 14px;
            font-weight: 600;
            color: #1a1a2e;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
        }
        /* 按钮 */
        QPushButton {
            background: #e94560;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover { background: #d63851; }
        QPushButton:pressed { background: #c22e47; }
        QPushButton:disabled { background: #ccc; color: #888; }
        /* 次要操作按钮 (刷新/拍照/编辑等) */
        QPushButton[text^="🔄"], QPushButton[text^="📷"], QPushButton[text^="✏️"],
        QPushButton[text^="🗑️"], QPushButton[text^="📊"], QPushButton[text^="📥"] {
            background: #eee;
            color: #444;
            padding: 6px 14px;
        }
        QPushButton[text^="🔄"]:hover, QPushButton[text^="📷"]:hover { background: #ddd; }
        /* 输入框 */
        QLineEdit, QTextEdit {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px 14px;
            background: #fff;
            font-size: 13px;
        }
        QLineEdit:focus, QTextEdit:focus {
            border-color: #e94560;
            border-width: 2px;
        }
        QComboBox, QDateEdit {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 8px 14px;
            background: #fff;
            font-size: 13px;
            min-width: 90px;
        }
        QComboBox:focus, QDateEdit:focus { border-color: #e94560; }
        QComboBox::drop-down { border: none; width: 24px; }
        /* 表格 */
        QTableWidget {
            background: #fff;
            border: none;
            border-radius: 10px;
            gridline-color: #f0f0f0;
            font-size: 13px;
        }
        QHeaderView::section {
            background: #fafafa;
            color: #555;
            padding: 10px 14px;
            border: none;
            border-bottom: 2px solid #eee;
            font-weight: 600;
            font-size: 12px;
        }
        QTableWidget::item {
            padding: 8px 14px;
            border-bottom: 1px solid #f5f5f5;
        }
        QTableWidget::item:selected {
            background: #fff0f0;
            color: #333;
        }
        /* 标签 */
        QLabel { color: #333; }
        QLabel#navBrand { color: #fff; }
        /* 状态栏 */
        QStatusBar {
            background: #fff;
            border-top: 1px solid #eee;
            color: #888;
            font-size: 12px;
            padding: 4px 12px;
        }
    ''')

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
