# 聚美康训练营管理系统

称重模块包括学员称重、出入营、教练账号、早晚称、30 天营期和 Excel 报表。住宿模块包括房间、床位、入住记录和 Excel 导入。两套服务使用各自的 SQLite 数据库，可通过本机 API 联动。

| 源码 | 技术 |
| --- | --- |
| `app.py`、`admin_app.py`、`models.py`、`excel_template.py` | Python / Flask / SQLite |
| `lodging/frontend` | TypeScript / React / Ant Design / Vite |
| `lodging/backend` | TypeScript / NestJS / Prisma / SQLite |

## 本地运行

建议使用 Python 3.12 和 Node.js 20 或 22。

### 称重

在仓库根目录安装依赖：`python -m pip install -r requirements.txt`。启动 `python app.py`，称重端默认监听 `127.0.0.1:5000`。

后台启动前，请通过环境变量设置随机的 `ADMIN_SECRET_KEY` 和首次登录密码 `ADMIN_INITIAL_PASSWORD`（至少 12 个字符）。签名密钥可以用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成。然后运行 `python admin_app.py`，默认监听 `127.0.0.1:5001`，管理员用户名默认为 `admin`，可在首次使用前通过 `ADMIN_USERNAME` 配置。首次访问时初始化空数据库及管理员账号。

### 住宿

在 `lodging/backend` 创建本地 `.env`，设置 `DATABASE_URL="file:./dev.db"`。依次执行 `npm ci`、`npx prisma db push`、`npm run dev`。API 默认监听 `127.0.0.1:3000`。

在 `lodging/frontend` 执行 `npm ci` 和 `npm run dev`。访问 `http://localhost:5173`。称重后台默认通过本机 3000 端口调用住宿 API，可设置 `LODGING_API_BASE` 覆盖。

后台内嵌部署时，可设置前端构建变量 `VITE_BASE_PATH=/accommodation/`、`VITE_API_BASE=/accommodation-api`；由网关同时保护页面和 API。独立住宿 API 没有独立登录，公网部署需要在网关加访问控制。

## 发布范围

此版本不包含生产数据库、学员数据、人脸样本、服务密钥、生产配置、备份或电子秤助手安装包。人脸识别需要自行取得并配置 ArcFace SDK 及授权文件；安装包相关动作需要另行部署对应资源。
