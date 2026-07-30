# 体重管理系统

人脸识别 + 体重管理的一体化解决方案

## 系统架构

```
┌── 浏览器 (PC/手机) ──────┐
│ 称重页 / 看板 / 排名       │ ← HTTP API
└─────────────────────────┘      ↓
┌── Linux 云服务器 ──────────┐
│ Flask + ArcFace + SQLite    │
└─────────────────────────────┘
┌── Windows 管理端 (PyQt5) ──┐
│ 学员管理 / 人脸录入 / 导出   │ ← HTTP API
└─────────────────────────────┘
```

## 快速开始

### 1. 本地测试 (Windows)

```bash
start.bat
```

浏览器打开 http://localhost:5000

### 2. 部署到 Linux 服务器

```bash
chmod +x start.sh
./start.sh
```

浏览器打开 http://服务器IP:5000

### 3. Windows 管理端

```bash
cd win-admin
python main.py
```

打包为单文件:
```bash
cd win-admin
build.bat
```

## 功能说明

| 页面 | 功能 | 说明 |
|---|---|---|
| `/` 称重页 | 摄像头识别 + 体重录入 | PC/手机双端适配 |
| `/dashboard` 看板 | 周/月排名、统计 | 支持 Excel 导出 |
| `/leaderboard` 大屏 | 排行榜投屏 | 自动刷新 |
| `/admin` 学员管理 | 增删改查、人脸录入 | 支持摄像头拍照录入 |
| `/settings` 设置 | ArcFace 授权、系统参数 | |

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/recognize | 人脸识别 (1:N) |
| POST | /api/weigh | 保存体重 |
| PUT | /api/weigh | 覆盖当日体重 |
| GET | /api/rankings/{week,month} | 排名数据 |
| GET/POST | /api/users | 学员管理 |
| GET/POST | /api/settings | 系统设置 |

## 硬件要求

- **服务器**: Linux, 2GB RAM, Python 3.9+
- **称重区**: 任意带摄像头的设备 (笔记本/手机/PC + USB 摄像头)
- **电子秤**: 可选, 支持手动输入

## ArcFace SDK 配置

1. 将 SDK 文件放入 `sdk/` 目录:
   - Windows: `sdk/win64/libarcsoft_face_engine.dll`
   - Linux: `sdk/linux/libarcsoft_face_engine.so`
2. 在设置页面填入 APP_ID 和 SDK_KEY
3. 重启服务生效

> 无 SDK 时自动启用 Demo 模式, 所有功能可用 (人脸识别用随机匹配模拟)

## 项目结构

```
weight-system/
├── app.py              # Flask 后端
├── config.py           # 配置
├── models.py           # 数据库操作
├── sdk/                # ArcFace SDK
│   ├── __init__.py
│   └── arcface_engine.py
├── templates/          # HTML 页面
├── static/             # CSS/JS
├── win-admin/          # Windows 管理端
│   └── main.py         # PyQt5 程序
├── start.sh            # Linux 部署
├── start.bat           # Windows 启动
└── README.md
```

## 掉秤率计算

```
掉秤率 = (期末体重 - 期初体重) / 期初体重 × 100%
```

负数 = 体重减少 (掉秤), 正数 = 体重增加
排名按掉秤率从高到低 (掉秤越多排名越前)

## 人脸活体验证

系统已集成 **ArcFace RGB 单目活体检测**（SDK V3.0 的 `ASF_LIVENESS`），可在设置中开启或关闭：

| 特性 | 说明 |
|------|------|
| 检测类型 | 单目 RGB 活体（非动作活体） |
| 防护目标 | 防止照片、屏幕、视频等非真实人脸攻击 |
| 开关位置 | 设置页 → "启用人脸活体验证" |
| 默认状态 | 开启 |
| 生效范围 | 称重识别、学员录入、教练录入、Windows 管理端 |

> 关闭活体后，系统仅做 1:N 人脸识别，不再判断是否为真实人脸。适用于调试或摄像头环境较差的情况。

## 定价参考

- 本系统: 300-500 元 (一次部署, 永久使用)
- 对比 SaaS: 月费 99-199 元/月 (需联网)
- 对比一体机: 2000-5000 元/台
