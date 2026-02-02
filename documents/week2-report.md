# Week 2 开发报告
**日期**: 2026-01-30

## 1. 当前版本

- **分支**: feat/data
- **Commit**: `81d2c98` (schema debug)

---

## 2. 本周完成内容

### 2.1 数据库搭建及对话缓存

#### 数据库设计

实现 SQLite 数据库存储患者、对话、消息记录：

| 表名 | 功能 | 关键字段 |
|------|------|----------|
| `patients` | 患者基本信息 | patient_id, name, age, gender, phone, address |
| `conversations` | 对话记录 | conversation_id, patient_id, **drhyper_state** (JSON), status |
| `messages` | 消息历史 | message_id, conversation_id, role, content, images |

**文件**: `/home/vic/gs/backend/database/models.py`

#### 对话缓存机制

**问题**: Pickle 序列化导致两个问题：
1. ImageAnalyzer 使用旧配置（pickle 保存了整个对象）
2. 图结构（entity_graph, relation_graph）未正确缓存

**解决方案**: 实现轻量级 JSON 缓存

- **序列化**: 使用 `to_cache_dict()` 方法将对话状态转换为 JSON 字典
  - 消息列表转换为字典格式
  - NetworkX 图使用 `node_link_data()` 序列化为 JSON
  - 图状态（step, accomplish）保存为元数据

- **反序列化**: 使用 `from_cache_dict()` 从缓存恢复对话
  - 使用 `node_link_graph()` 恢复图结构
  - 用最新配置重建 ImageAnalyzer（解决配置过期问题）

- **数据库集成**: 在 `process_message` 中实现完整的加载-处理-保存循环
---

### 2.2 ImageAnalyzer 医学图像类型路由

实现 `quick_classify` 方法，快速识别医学图像类型：

**支持的图像类型**:
- Laboratory Report（化验报告）
- ECG（心电图）
- X-ray（X光片）
- CT Scan（CT扫描）
- MRI（核磁共振）
- Ultrasound（超声）
- Pathology Report（病理报告）
- Other Medical Image（其他）

**实现位置**: `/home/vic/gs/drhyper/core/image_analyzer.py:159-261`

**核心逻辑**:
1. 图像上传后快速识别类型
2. 根据类型选取合适的 prompt 进行分析

## 3. 下周计划（Week 3）

根据 [development-roadmap.md](./development-roadmap.md)，Week 3 重点：**意图路由 + 数据同步**

### 任务清单

1. **意图路由系统**
   - [ ] 实现 IntentRouter 组件
   - [ ] 文本输入 → LLM 意图识别
   - [ ] 定义意图分类（SYMPTOM_INQUIRY, DATA_QUERY, DATA_UPDATE 等）
   - [ ] drhyper层的诊断目标识别

2. 患者管理的完善：
   - [ ] 患者的删除以及对话的删除

3. 患者数据同步：
   - [ ] graph的数据初始化以及同步问题
   - patient profile: drhyper在构建图的时候就要给出key node，保存一些关键节点的信息，同时这些关键节点应该支持数据的同步
   

