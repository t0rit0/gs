# 医疗助手系统 (Medical Assistant System)

一个基于 DrHyper 的智能医疗对话辅助系统，包含前端 Web 界面和后端 API 服务。

## 项目结构

```
gs/
├── main.py                  # Streamlit 前端应用入口
├── frontend/               # 前端界面组件
│   ├── app.py             # 主应用
│   ├── pages/             # 多页面
│   │   ├── chat.py        # 聊天页面
│   │   ├── patients.py    # 患者管理
│   │   └── settings.py    # 设置页面
│   └── components/        # UI 组件
├── backend/               # 后端 API 服务
│   ├── main.py            # 后端服务启动脚本
│   ├── api/               # API 路由
│   ├── services/          # 业务逻辑层
│   └── database/          # 数据库模型和操作
├── drhyper/               # DrHyper 核心依赖（对话和诊断引擎）
├── storage/               # 数据存储目录
└── pyproject.toml         # Python 依赖配置
```

## 快速开始

### 1. 环境准备


**克隆项目**

本项目包含 `drhyper` 作为 Git submodule，需要使用以下方式克隆：

```bash
# 方式一：克隆时自动初始化 submodule（推荐）
git clone --recursive https://github.com/t0rit0/gs
cd gs
```


### 2. 安装依赖

**使用 uv**
```bash
# 安装所有依赖
uv sync
```

**或使用 pip**
```bash
pip install -e .
```

### 3. 配置环境变量


配置 DrHyper 模型设置（详见 `drhyper/README.md`）：
```bash
# 编辑 drhyper/config/config.cfg
# 设置 Conversation LLM、Graph LLM和Vision LLM 的 API key 和 endpoint
```

### 4. 启动后端服务

后端 API 服务提供医疗对话和患者管理功能：

```bash
# 方式一：使用 python 模块启动（推荐）
python -m backend.main

# 方式二：使用 uvicorn 直接启动
uvicorn backend.api.server:app --reload --host 0.0.0.0 --port 8000

# 自定义端口
uvicorn backend.api.server:app --port 8080 --reload
```

后端服务启动后，API 文档可通过以下地址访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**主要 API 端点**
- `POST /api/conversations` - 创建对话会话
- `POST /api/conversations/{conversation_id}/messages` - 发送消息
- `POST /api/patients` - 创建患者档案
- `GET /api/patients` - 获取患者列表

### 5. 启动前端应用

Streamlit 前端提供 Web 界面：

```bash
# 返回项目根目录
cd ..

# 方式一：使用 streamlit 命令
streamlit run main.py

# 方式二：使用 python
python -m streamlit run main.py

# 自定义端口和地址
streamlit run main.py --server.port 8501 --server.address 0.0.0.0
```

前端应用启动后，在浏览器中打开：
- 默认地址: http://localhost:8501

## 使用方式

### Web 界面使用

1. **患者管理页面** - 创建和管理患者档案
2. **聊天页面** - 与 DrHyper 进行医疗对话
3. **设置页面** - 配置 API 参数和系统设置

### 命令行使用

DrHyper 也提供命令行界面（CLI）：

```bash
cd drhyper

# 创建知识图谱
python cli.py create-graph --verbose

# 开始交互式对话
python cli.py start --verbose
```

## 开发说明

### 代码格式检查

```bash
# 使用 ruff 检查代码
ruff check .

# 自动修复格式问题
ruff check --fix .
```

### 前端开发

前端使用 Streamlit 构建，位于 `frontend/` 目录：

- `frontend/app.py` - 主应用入口
- `frontend/pages/` - 多页面组件
- `frontend/components/` - 可复用 UI 组件
- `frontend/config.py` - 前端配置
- `frontend/utils/drhyper_client.py` - DrHyper API 客户端

### 后端开发

后端基于 FastAPI，位于 `backend/` 目录：

- `backend/main.py` - 后端服务启动入口
- `backend/api/server.py` - FastAPI 服务器
- `backend/services/` - 业务逻辑层
  - `conversation_service.py` - 对话服务
  - `patient_service.py` - 患者管理服务
- `backend/database/` - 数据库层
  - `models.py` - 数据模型
  - `crud.py` - 数据库操作
  - `schemas.py` - Pydantic 模式

## 常见问题

**Q: 后端服务无法启动**
- 检查 API key 是否正确配置
- 确认依赖已完整安装
- 查看端口是否被占用

**Q: 前端无法连接后端**
- 确认后端服务已启动
- 检查 `DRHYPER_API_BASE` 环境变量
- 查看浏览器控制台错误信息

**Q: 图片上传失败**
- 检查图片大小是否超过 200MB（Streamlit 默认限制）
- 确认图片格式（支持 PNG, JPG, JPEG, GIF, BMP）

## 更多信息

- [DrHyper 文档](./drhyper/README.md) - DrHyper 后端详细文档
- [API 文档](http://localhost:8000/docs) - 后端 API Swagger 文档（需先启动服务）
- [Streamlit 文档](https://docs.streamlit.io/) - Streamlit 官方文档
 