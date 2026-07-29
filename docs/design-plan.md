# Mosaic-Canvas 深入整改方案

## 一、问题诊断

### 1.1 模板与真实代码脱节
- Mosaic 项目有 28 个 Python 示例（examples/01-28），但 templates.js 仅覆盖到 ex13
- ex14-ex28 共 15 个示例完全缺失（主要是数字人引擎示例）
- 部分模板参数与后端节点定义不一致（上一轮已修复 14 个节点）

### 1.2 中文适配不完整
- 节点面板描述显示英文（来自 introspect.py 的英文 description）
- 搜索功能基于英文名/描述，中文关键词无法匹配
- logs.html 和 resources.html 完全未 i18n
- HTML lang 属性硬编码 "en"，不随语言切换

### 1.3 缺少组合模块功能
- 所有节点都是原子的，无法将常用节点组合封装为可复用模块
- 已有"自定义模板"保存功能，但模板加载后展开为独立节点，不是封装单元

## 二、整改方案（三阶段）

### 阶段一：补全完整流程模板（P1）

#### 缺失模板清单（15个）

| 示例 | 模板ID | 节点链 | 中文名 |
|------|--------|--------|--------|
| 14_sadtalker | ex14-sadtalker-lipsync | lip-syncer(method=sadtalker) → video-encoder | SadTalker 唇形同步 |
| 15_liveportrait | ex15-liveportrait-lipsync | lip-syncer(method=liveportrait) → video-encoder | LivePortrait 唇形同步 |
| 16_geneface | ex16-geneface-lipsync | lip-syncer(method=geneface) → video-encoder | GeneFace 唇形同步 |
| 17_audio2face | ex17-audio2face-driver | avatar-driver(method=audio2face) → video-encoder | Audio2Face 形象驱动 |
| 18_face_enhancer | ex18-face-enhancer | lip-syncer → video-encoder(enhancer=gfpgan) | 人脸增强唇形同步 |
| 19_wav2lip | ex19-wav2lip-lipsync | lip-syncer(method=wav2lip) → video-encoder | Wav2Lip 唇形同步 |
| 20_video_domain | ex20-video-multi-engine | wan-video/hunyuan-video/ltx-video → video-encoder | 视频多引擎 |
| 21_subtitle | ex21-subtitle-full | subtitle-generator → subtitle-aligner → subtitle-translator | 完整字幕流程 |
| 22_export | ex22-export-modes | video-encoder + livestreamer + multi-format-exporter | 导出多模式 |
| 23_rag | ex23-rag-full | document-parser → vector-indexer → retriever → citation-generator | 完整 RAG 流程 |
| 24_hallo | ex24-hallo-lipsync | lip-syncer(method=hallo) → video-encoder | Hallo 唇形同步 |
| 25_tpsmn | ex25-tpsmn-lipsync | lip-syncer(method=tpsmn) → video-encoder | TPSMN 唇形同步 |
| 26_anitalker | ex26-anitalker-lipsync | lip-syncer(method=anitalker) → video-encoder | AniTalker 唇形同步 |
| 27_aniportrait | ex27-aniportrait-driver | avatar-driver(method=aniportrait) → video-encoder | AniPortrait 形象驱动 |
| 28_funasr | ex28-funasr-asr-export | funasr-asr → field-mapper → multi-format-exporter | FunASR 语音识别导出 |

#### 关键设计
- 数字人引擎示例通过 `lip-syncer`/`avatar-driver` 的 `method` 参数选择引擎
- 每个模板包含完整的 `name.zh`/`description.zh` 双语字段
- 参照真实 examples 代码设置 `params` 和 `input_params`

### 阶段二：全面中文化（P0+P1）

#### 2.1 节点面板描述中文化（P0）
- 在 i18n.js 新增 `_nodeDesc` 字典（80个节点的中文描述）
- 新增 `nodeDesc(name, fallback)` 函数
- palette.js 第192行改用 `I18n.nodeDesc(node.name, node.description)`

#### 2.2 搜索功能支持中文（P0）
- palette.js 搜索时拼接中英文字段：节点英文名+英文描述+中文名+中文描述+中文域名
- 搜索"唇形"、"图片生成"等中文关键词即可命中

#### 2.3 HTML lang 动态切换（P0）
- i18n.js `setLang()` 中增加 `document.documentElement.lang = lang`
- 初始化时立即设置

#### 2.4 logs/resources 页面 i18n（P1）
- 引入 i18n.js
- 为硬编码文本添加 `data-i18n` 属性
- 新增 `logs.*` 和 `resources.*` 翻译键

### 阶段三：组合模块功能（P2+P3）

#### 核心设计：折叠组 + 执行时展开

组合模块在画布上显示为**可折叠的组容器**（显示模块名+内部节点缩略），双击可展开编辑内部节点；执行时由前端展开为纯节点图提交，后端完全无感。

#### 数据结构

```json
{
  "kind": "composite-module",
  "version": 1,
  "id": "my-digital-human",
  "name": { "en": "My Digital Human", "zh": "我的数字人模块" },
  "icon": "🧑",
  "graph": { "nodes": [...], "edges": [...] },
  "ports": {
    "inputs": [{ "name": "text", "type": "text", "mapped_node": "m_n1" }],
    "outputs": [{ "name": "video", "type": "video", "mapped_node": "m_n2" }]
  }
}
```

#### 交互流程
1. **创建**：框选节点 → 右键"封装为模块" → 填写名称 → 自动推断端口 → 保存
2. **使用**：面板"组合模块"分组 → 点击拖入画布 → 显示为折叠组
3. **查看**：双击组容器展开内部节点
4. **执行**：提交前 `toExecutableGraph()` 展开所有组合模块为纯节点图

#### 后端 API
- `GET /api/modules` - 列出所有模块
- `GET /api/modules/{filename}` - 加载模块定义
- `POST /api/modules` - 保存模块
- `DELETE /api/modules/{filename}` - 删除模块

#### 涉及文件
| 文件 | 改动 |
|------|------|
| i18n.js | _nodeDesc字典、lang同步、logs/resources键 |
| palette.js | 搜索扩展、组合模块分组 |
| templates.js | 追加15个模板 |
| store.js | 多选状态、toExecutableGraph() |
| canvas.js | box-select、组容器渲染 |
| app.js | 模块创建对话框 |
| api.js | 模块CRUD客户端 |
| server.py | 模块CRUD路由 |
| logs.html / resources.html | i18n适配 |
| style.css | 组合模块样式 |

## 三、实施顺序

```
P0 中文化核心 → P1 补全模板 → P1 logs/resources i18n → P2 组合模块基础 → P3 组合模块完整功能
```

## 四、风险评估

| 风险 | 等级 | 缓解措施 |
|------|:---:|---------|
| 组合模块展开时边重映射错误 | 高 | 端口选择器让用户明确指定映射 |
| 多选与现有拖拽冲突 | 中 | 严格区分空白区域和节点区域 mousedown |
| 模板节点type不匹配 | 低 | 实施前验证80个注册节点名 |
| 组合模块嵌套 | 低 | v1限制仅原子节点可封装 |
