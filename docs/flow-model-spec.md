# Mosaic Canvas 流模型规则文档

> **版本**: 1.0  
> **最后更新**: 2026-07-29  
> **适用范围**: Mosaic Canvas 可视化管线编辑器及执行引擎

---

## 1. 概述

Mosaic Canvas 使用**有向无环图（DAG）**作为流模型的核心数据结构。一个流模型（Pipeline）由节点（Node）、边（Edge）和全局输入（Input）三部分组成，序列化为 JSON 格式存储和传输。

### 1.1 设计原则

- **JSON 可序列化**：所有数据结构可无损序列化为 JSON，支持保存、加载、版本控制
- **前后端一致**：前端画布状态与后端执行引擎使用同一套数据模型
- **拓扑执行**：节点按拓扑序执行，数据沿边流动
- **类型安全**：端口类型系统防止不兼容的节点连接

---

## 2. JSON 顶层结构

```json
{
  "name": "管线名称",
  "nodes": [ /* GraphNode[] */ ],
  "edges": [ /* GraphEdge[] */ ],
  "input": {
    "data": { /* key: value 键值对 */ }
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 管线名称，默认 `"Untitled Pipeline"` |
| `nodes` | array | 是 | 节点数组，至少包含一个节点 |
| `edges` | array | 否 | 边数组，空数组表示各节点独立执行 |
| `input` | object | 否 | 全局输入，默认 `{"data": {}}` |
| `input.data` | object | 否 | 扁平 key-value 字典，注入到源节点的输入中 |

---

## 3. 节点定义（GraphNode）

### 3.1 完整字段

```json
{
  "id": "n1",
  "type": "text-to-video",
  "x": 40.0,
  "y": 40.0,
  "params": {
    "model": "THUDM/CogVideoX-5b"
  },
  "input_params": {
    "num_frames": "49",
    "fps": "8"
  },
  "label": "视频生成"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | **是** | 节点唯一标识符，同一图内不可重复 |
| `type` | string | **是** | 节点注册名（registry key），如 `"text-to-video"` |
| `x` | number | 否 | 画布 X 坐标，仅用于 UI 展示，不影响执行 |
| `y` | number | 否 | 画布 Y 坐标，仅用于 UI 展示，不影响执行 |
| `params` | object | 否 | **构造函数参数**，传递给 `Node.__init__()` |
| `input_params` | object | 否 | **运行时参数**，合并进 `MosaicData` 传给 `run()` |
| `label` | string | 否 | 用户自定义标签，仅用于 UI 显示 |

### 3.2 params 与 input_params 的关键区别

**这是流模型中最重要的规则，混淆会导致实例化失败或执行异常。**

| 维度 | `params`（构造参数） | `input_params`（运行参数） |
|------|---------------------|-------------------------|
| 用途 | 节点实例化时传入 `__init__()` | 执行时合并进 `MosaicData` 传给 `run()` |
| 典型字段 | `model`, `device`, `dtype`, `format`, `method`, `mapping` | `prompt`, `num_frames`, `fps`, `guidance_scale`, `negative_prompt` |
| 类型转换 | 按 `ui_type` 自动转换（int/float/bool） | 按 `ui_type` 自动转换；JSON 字段自动解析 |
| 优先级 | 实例化时一次性设置 | 执行时覆盖前驱输出和全局输入的同名字段 |

**判断规则**：
- 如果参数在 `Node.__init__()` 签名中声明 → 放入 `params`
- 如果参数在 `run()` 方法中通过 `MosaicData` 读取 → 放入 `input_params`
- 不确定时，查看节点的 `input_fields`（内省输出），在其中声明的字段用 `input_params`

### 3.3 值类型规则

UI 传过来的值默认为**字符串**，后端按参数的 `ui_type` 自动转换：

| ui_type | 转换规则 | 示例 |
|---------|---------|------|
| `int` | `int(float(value))` | `"49"` → `49` |
| `float` | `float(value)` | `"6.0"` → `6.0` |
| `bool` | `str(value).lower() in ("true","1","yes","on")` | `"true"` → `True` |
| `choice` | `str(value)` | `"mp4"` → `"mp4"` |
| `string` | 原样保留 | `"hello"` → `"hello"` |
| 空字符串 | 转为 `None`（使用节点默认值） | `""` → `None` |

### 3.4 JSON 字段自动解析

以下字段名在 `input_params` 或 `input.data` 中为字符串时，会自动解析为 Python 对象：

```
messages, formats, filter_metadata, padding, labels, results, prompts,
metadata, timestamps, mapping, drop_fields, mappings, conversions,
template, values, schema, aggregations, headers, fields, cases
```

例如：`"padding": "[0, 20, 0, 20]"` 会被解析为 `[0, 20, 0, 20]`。

---

## 4. 边定义（GraphEdge）

### 4.1 完整字段

```json
{
  "id": "e1",
  "source": "n1",
  "target": "n2",
  "pass_fields": ["frames", "fps"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | **是** | 边唯一标识符 |
| `source` | string | **是** | 源节点 ID（必须存在于 nodes 中） |
| `target` | string | **是** | 目标节点 ID（必须存在于 nodes 中） |
| `pass_fields` | array\|null | 否 | 字段白名单，`null` 或省略表示智能过滤 |

### 4.2 边的约束规则

1. **禁止自环**：`source` 不能等于 `target`
2. **禁止重复边**：同一 `source → target` 对只能存在一条边
3. **禁止成环**：图中不允许存在环（DAG 约束），通过 DFS 三色标记法检测
4. **引用完整性**：`source` 和 `target` 必须指向 `nodes` 中已定义的节点 ID

### 4.3 数据传递规则

数据沿边从源节点输出传递到目标节点输入，传递规则按优先级从高到低：

**优先级 1：边级白名单（`pass_fields`）**
- 若 `pass_fields` 非空，仅传递列表中指定的字段
- 示例：`"pass_fields": ["frames", "fps"]` → 只传递 `frames` 和 `fps`

**优先级 2：节点级智能过滤（默认）**
- 若 `pass_fields` 为 `null`（默认），根据目标节点声明的 `input_fields` 过滤
- 仅传递目标节点 `input_fields` 中声明的字段
- 若目标节点 `input_types` 包含 `"mosaic"`，则传递所有字段（全量传递）

**优先级 3：字段别名自动映射**
- 当目标节点需要的字段名与源节点输出的字段名不一致时，自动桥接
- 别名映射表见下方 §5.3

### 4.4 端口类型兼容矩阵

前端在连线时进行类型校验，后端不做类型检查（依赖前端校验）。支持 12 种端口类型：

| 输出类型 \ 可连接的输入类型 | 兼容列表 |
|---------------------------|---------|
| `text` | text, image, audio, video, document, json, rag_query_result, mosaic |
| `image` | image, video, avatar, json, mosaic |
| `audio` | audio, text, subtitle, json, mosaic |
| `video` | video, image, json, mosaic |
| `subtitle` | subtitle, text, json, mosaic |
| `file` | file, text, image, audio, video, subtitle, document, json, mosaic |
| `motion` | motion, mosaic |
| `avatar` | avatar, image, mosaic |
| `document` | document, text, json, mosaic |
| `rag_query_result` | rag_query_result, text, json, mosaic |
| `json` | json, text, mosaic |
| `mosaic` | 所有类型（通配） |

校验规则（按优先级）：
1. 任一方端口类型声明为空 → 允许（向后兼容）
2. 目标 `input_types` 含 `"mosaic"` → 允许任何连接
3. 输出类型与输入类型有精确交集 → 允许
4. 根据兼容矩阵可转换 → 允许
5. 都不满足 → 拒绝

---

## 5. 执行引擎规则

### 5.1 执行流程

```
1. 实例化节点 → 2. 拓扑排序 → 3. 按序执行 → 4. 收集输出 → 5. 清理资源
```

**阶段 1：实例化节点**
- 对每个节点，通过 `registry.get_class(type)` 获取节点类
- 将 `params` 按 `ui_type` 做类型转换
- 执行 `instance = NodeClass(**params)` 实例化
- 任一节点实例化失败 → fail-fast 中断

**阶段 2：拓扑排序**
- 使用 Kahn 算法（入度法）计算拓扑序
- 先通过 DFS 三色标记法检测环，有环则抛出异常
- 入度为 0 的节点先入队，逐步删除边并收集顺序

**阶段 3：按拓扑序执行**
对每个节点：
1. 组装输入 `MosaicData`（见 §5.2）
2. 调用 `instance.run(node_input)`
3. 成功 → 序列化输出，继续下一节点
4. 失败 → fail-fast 中断剩余节点

**阶段 4：收集最终输出**
- 从 sink 节点（无出边的节点）收集结果
- 单 sink → 直接取其输出
- 多 sink → 返回 `{node_id: output}` 字典

**阶段 5：清理**
- 释放所有节点占用的 GPU 内存

### 5.2 输入数据组装规则

每个节点的 `node_input`（MosaicData）按以下优先级从低到高合并：

```
① 前驱输出字段（经 pass_fields / 智能过滤 / 别名映射）
    ↓ 合并（仅填充缺失键）
② pipeline input.data（全局输入，对非源节点仅填充缺失键）
    ↓ 合并（覆盖同名键）
③ node.input_params（节点级运行参数，最高优先级）
```

**源节点（无前驱）**：
- `node_input = MosaicData(pipeline_input.data)` — 全局输入直接注入
- 应用字段别名安全网

**非源节点（有前驱）**：
- 从每个前驱的输出中提取字段（按 §4.3 传递规则）
- 全局 `input.data` 仅填充尚未存在的键（不覆盖前驱输出）
- `input_params` 覆盖同名键（最高优先级）

### 5.3 字段别名映射表

当目标节点需要的字段名与源节点输出不匹配时，执行器自动查找别名：

| 目标字段 | 可接受的源字段（按查找顺序） |
|---------|---------------------------|
| `data` | image, images, video, audio, text, reply, response, frames, subtitles, subtitle, segments, waveform, document, pages |
| `prompt` | reply, response, text, message, summary, query, question, results, context, translated_text |
| `image` | images, data, face_image, source_image |
| `images` | image, data |
| `text` | reply, response, prompt, summary, transcript, results, context |
| `frames` | video, images, image, frame_list, data |
| `face_image` | image, images, avatar, source_image, data |
| `source_image` | image, images, avatar, face_image, data |
| `input_stream` | audio, text, video, data, frames |
| `audio` | audio_path, audio_data, voice, waveform |
| `subtitle` | subtitles, segments, subtitle_data |
| `document` | text, pages, content, data |
| `results` | context, text, rag_query_result, reply, response |
| `query` | question, search_query, text |
| `reference_audio` | audio, audio_path, voice, waveform |
| `driving_audio` | audio, audio_path, voice, waveform |
| `driving_video` | video, frames, motion, keypoints |
| `file_path` | file, path, document, filename |
| `stream_url` | url, rtmp_url, stream |
| `mask_image` | mask, mask_path, mask_image_path |

### 5.4 输出序列化规则

节点输出通过 `_serialize_output` 转换为 UI 友好格式：

| 内部类型 | 序列化结果 |
|---------|-----------|
| PIL Image | 保存为 PNG/JPG 文件，返回 `{"__display_type__": "image", "src": "/outputs/xxx.png"}` |
| waveform (ndarray) | 编码为 WAV 文件（截断 60s），返回 audio descriptor |
| frames (list) | 生成缩略图 + 尝试用 imageio 编码 MP4 |
| 超长字符串 (>10000 字符) | 截断 |
| 超长列表 (>50 项) | 转为 summary |

---

## 6. 全局输入（PipelineInput）

### 6.1 结构

```json
{
  "input": {
    "data": {
      "prompt": "一只猫在玩毛线球",
      "seed": 42,
      "face_image": "/path/to/avatar.png"
    }
  }
}
```

### 6.2 注入规则

- `input.data` 是扁平的 key-value 字典
- 值可以是字符串、数字、布尔，或 JSON 字符串（对 `_JSON_FIELDS` 中的字段自动解析）
- **对源节点**：所有字段直接合并进 `node_input`，作为主要输入数据源
- **对非源节点**：仅填充 `node_input` 中尚不存在的键（补充默认值）
- 常用于设置全局默认值：`negative_prompt`、`seed`、`face_image`、`audio` 等路径

### 6.3 优先级

```
前驱输出 < pipeline input.data < node.input_params
```

---

## 7. 节点注册名速查

### 7.1 文本域 (text)

| 注册名 | 输入类型 | 输出类型 | 说明 |
|--------|---------|---------|------|
| `text-generator` | text, mosaic | text | 文本生成 |
| `chat` | text, mosaic | text | 多轮对话 |
| `text-summarizer` | text, mosaic | text | 文本摘要 |
| `translator` | text, mosaic | text | 翻译 |
| `text-classifier` | text, mosaic | text | 文本分类 |
| `text-rewriter` | text, mosaic | text | 文本改写 |

### 7.2 图像域 (image)

| 注册名 | 输入类型 | 输出类型 | 说明 |
|--------|---------|---------|------|
| `text-to-image` | text, mosaic | image | 文生图 |
| `image-to-image` | image, mosaic | image | 图生图 |
| `inpainting` | image, mosaic | image | 图像修复 |
| `upscaler` | image, mosaic | image | 超分辨率 |
| `background-remover` | image, mosaic | image | 背景移除 |
| `stylizer` | image, mosaic | image | 风格化 |

### 7.3 视频域 (video)

| 注册名 | 输入类型 | 输出类型 | 关键参数 |
|--------|---------|---------|---------|
| `text-to-video` | text, mosaic | video | `num_frames`, `fps`, `width`, `height` |
| `image-to-video` | image, mosaic | video | `image`, `num_frames`, `fps` |
| `hunyuan-video` | text, mosaic | video | `num_frames`, `width`, `height`, `fps` |
| `ltx-video` | text, mosaic | video | `num_frames`, `width`, `height`, `fps` |
| `wan-video` | text, mosaic | video | `num_frames`, `width`, `height`, `fps` |
| `video-continuation` | video, mosaic | video | `num_frames`, `fps` |
| `frame-interpolation` | video, mosaic | video | `target_fps`, `method` |
| `frame-extractor` | video, mosaic | image | `fps`, `count` |

### 7.4 音频域 (audio)

| 注册名 | 输入类型 | 输出类型 | 关键参数 |
|--------|---------|---------|---------|
| `tts` | text, mosaic | audio | `text`, `emotion`, `voice`, `language`, `speed` |
| `asr` | audio, mosaic | text | `audio`, `language`, `task` |
| `funasr-asr` | audio, mosaic | text | `audio`, `language` |
| `music-generator` | text, mosaic | audio | `prompt`, `duration` |
| `sound-effect-generator` | text, mosaic | audio | `prompt`, `duration` |
| `voice-clone` | audio, text, mosaic | audio | `reference_audio`, `text` |

### 7.5 数字人域 (digital_human)

| 注册名 | 输入类型 | 输出类型 | 关键参数 |
|--------|---------|---------|---------|
| `lip-syncer` | image, audio, video, mosaic | video, image, audio, mosaic | `face_image`, `audio`, `fps`, `padding` |
| `realtime-renderer` | image, audio, text, motion, mosaic | video, image, mosaic | `source_image`, `mode`, `input_stream`, `target_fps` |
| `avatar-driver` | image, video, audio, mosaic | video, image, mosaic | `source_image`, `driving_video`, `driving_audio`, `fps` |
| `motion-generator` | text, audio, mosaic | motion, mosaic | `prompt`, `audio`, `duration`, `fps` |

**数字人引擎选择**：通过 `lip-syncer` 或 `avatar-driver` 的 `params.method` 构造参数切换引擎：

| method 值 | 说明 | 典型 input_params |
|-----------|------|-------------------|
| `sadtalker` | SadTalker 3DMM | `pose_style`, `still`, `expression_scale`, `enhancer`, `size` |
| `liveportrait` | LivePortrait | `relative_motion`, `animate_eyes`, `lip_zero` |
| `geneface` | GeneFace | `torso`, `head_torso_threshold` |
| `wav2lip` | Wav2Lip | `enhancer`, `face_restore_weight`, `crop_size` |
| `wav2lip-original` | Wav2Lip 原版 | 同上 |
| `ultralight` | 轻量级 | 同上 |
| `audio2face` | Audio2Face | `quality_preset` |
| `hallo` | Hallo | `batch_size`, `vae_dtype` |
| `tpsmn` | TPSMN | （空） |
| `anitalker` | AniTalker | `pose_style` |
| `aniportrait` | AniPortrait | `dtype` |

### 7.6 字幕域 (subtitle)

| 注册名 | 输入类型 | 输出类型 | 说明 |
|--------|---------|---------|------|
| `subtitle-generator` | audio, mosaic | subtitle | 字幕生成 |
| `subtitle-aligner` | subtitle, audio, mosaic | subtitle | 字幕对齐 |
| `subtitle-translator` | subtitle, mosaic | subtitle | 字幕翻译 |

### 7.7 一致性域 (consistency)

| 注册名 | 输入类型 | 输出类型 | 说明 |
|--------|---------|---------|------|
| `identity-keeper` | image, mosaic | image | 身份保持 |
| `style-keeper` | image, mosaic | image | 风格保持 |
| `cross-frame-consistency` | image, text, mosaic | image | 跨帧一致性 |

### 7.8 导出域 (export)

| 注册名 | 输入类型 | 输出类型 | 关键参数 |
|--------|---------|---------|---------|
| `video-encoder` | video, image, mosaic | file | `params.format`: mp4/avi/webm/gif |
| `multi-format-exporter` | video, image, audio, subtitle, text, mosaic | file | `input_params.formats`, `content_type` |
| `livestreamer` | video, image, mosaic | file | `input_params.stream_url` |

### 7.9 RAG 域 (rag)

| 注册名 | 输入类型 | 输出类型 | 说明 |
|--------|---------|---------|------|
| `document-parser` | text, mosaic | document, mosaic | 文档解析 |
| `vector-indexer` | document, mosaic | mosaic | 向量索引 |
| `retriever` | text, mosaic | rag_query_result, mosaic | 向量检索 |
| `citation-generator` | rag_query_result, mosaic | text, mosaic | 引用生成 |

### 7.10 辅助节点 (helpers)

| 子域 | 节点列表 |
|------|---------|
| dataflow | `field-mapper`, `type-converter`, `data-merger`, `data-splitter`, `value-injector`, `schema-validator` |
| container | `json-parser`, `json-builder`, `json-path`, `list-ops`, `dict-ops`, `string-ops`, `data-flattener`, `data-grouper`, `text-chunker` |
| controlflow | `loop`, `retry`, `timeout`, `switch`, `parallel-map` |
| processing | `filter`, `batcher`, `aggregator`, `template-renderer`, `throttler` |
| cache | `result-cache`, `checkpoint`, `kv-store`, `state-store` |
| monitoring | `logger`, `profiler`, `webhook-notifier`, `debugger` |
| io | `file-reader`, `file-writer`, `api-caller`, `data-injector` |

---

## 8. 视频时长计算规则

视频时长由帧数和帧率决定：

```
时长（秒）= num_frames / fps
```

### 8.1 常见配置

| 目标时长 | fps | num_frames | 适用场景 |
|---------|-----|-----------|---------|
| 6s | 8 | 49 | CogVideoX 默认 |
| 10s | 8 | 81 | Wan Video |
| 10s | 30 | 301 | LTX Video |
| 30s | 8 | 241 | 长视频生成 |
| 30s | 25 | 751 | 数字人唇形同步 |

### 8.2 30 秒视频配置示例

**方案 A：文生视频直接生成**
- 节点：`text-to-video` → `video-encoder`
- 参数：`num_frames: "241"`, `fps: "8"`（241/8 ≈ 30.1s）

**方案 B：TTS + 数字人唇形同步**
- 节点：`tts` → `lip-syncer` → `video-encoder`
- TTS 生成约 30 秒音频，lip-syncer 以 `fps: "25"` 生成 750 帧视频

**方案 C：图生视频 + 帧插值**
- 节点：`image-to-video` → `frame-interpolation` → `video-encoder`
- 先以低帧率生成，再插值提升到目标帧率

---

## 9. 完整 JSON 示例

### 9.1 最小有效图

```json
{
  "name": "最小示例",
  "nodes": [
    {
      "id": "n1",
      "type": "text-generator",
      "x": 40,
      "y": 40,
      "params": {},
      "input_params": {},
      "label": ""
    }
  ],
  "edges": [],
  "input": {
    "data": {
      "prompt": "你好"
    }
  }
}
```

### 9.2 线性管线（文生视频 → 编码）

```json
{
  "name": "文生视频管线",
  "nodes": [
    {
      "id": "n1",
      "type": "text-to-video",
      "x": 40,
      "y": 40,
      "params": {},
      "input_params": {
        "num_frames": "49",
        "fps": "8"
      },
      "label": ""
    },
    {
      "id": "n2",
      "type": "video-encoder",
      "x": 320,
      "y": 40,
      "params": { "format": "mp4" },
      "input_params": {},
      "label": ""
    }
  ],
  "edges": [
    { "id": "e1", "source": "n1", "target": "n2" }
  ],
  "input": {
    "data": {
      "prompt": "a cat playing with a ball of yarn, cinematic"
    }
  }
}
```

### 9.3 分支图（多输出并行）

```json
{
  "name": "多引擎并行视频生成",
  "nodes": [
    {
      "id": "n1",
      "type": "wan-video",
      "x": 40, "y": 40,
      "params": {},
      "input_params": { "num_frames": "81", "fps": "16" },
      "label": ""
    },
    {
      "id": "n2",
      "type": "video-encoder",
      "x": 320, "y": 40,
      "params": { "format": "mp4" },
      "input_params": {},
      "label": ""
    },
    {
      "id": "n3",
      "type": "ltx-video",
      "x": 40, "y": 160,
      "params": {},
      "input_params": { "num_frames": "97", "fps": "30" },
      "label": ""
    },
    {
      "id": "n4",
      "type": "video-encoder",
      "x": 320, "y": 160,
      "params": { "format": "mp4" },
      "input_params": {},
      "label": ""
    }
  ],
  "edges": [
    { "id": "e1", "source": "n1", "target": "n2" },
    { "id": "e2", "source": "n3", "target": "n4" }
  ],
  "input": {
    "data": {
      "prompt": "a cat playing with a ball of yarn, slow motion"
    }
  }
}
```

---

## 10. API 端点

| 端点 | 方法 | 用途 | 请求体 |
|------|------|------|--------|
| `/api/validate` | POST | 校验图结构 | Graph JSON |
| `/api/run` | POST | 同步执行 | Graph JSON |
| `/ws/run` | WS | 实时执行（流式） | Graph JSON |
| `/api/export/python` | POST | 导出 Python 代码 | Graph JSON |
| `/api/templates` | GET | 列出已保存模板 | — |
| `/api/templates` | POST | 保存模板 | Graph JSON |
| `/api/templates/{filename}` | GET | 加载模板 | — |
| `/api/templates/{filename}` | DELETE | 删除模板 | — |
| `/api/modules` | GET | 列出组合模块 | — |
| `/api/modules` | POST | 保存组合模块 | Module JSON |
| `/api/modules/{filename}` | GET | 加载组合模块 | — |
| `/api/modules/{filename}` | DELETE | 删除组合模块 | — |

---

## 11. 校验规则清单

在提交执行前，图必须通过以下校验：

1. **节点 ID 唯一性**：所有 `nodes[].id` 不可重复
2. **边引用完整性**：所有 `edges[].source` 和 `edges[].target` 必须存在于 `nodes` 中
3. **无环检测**：图中不允许存在环
4. **节点类型有效**：所有 `nodes[].type` 必须是已注册的节点名
5. **参数类型匹配**：`params` 中的参数必须是节点构造函数的合法参数
6. **禁止自环**：边的 `source` 不能等于 `target`
7. **禁止重复边**：同一 `source → target` 对只能有一条边

---

## 12. 常见错误与规避

| 错误 | 原因 | 规避方法 |
|------|------|---------|
| `TypeError: __init__() got unexpected keyword` | `params` 中包含了构造函数不接受的参数 | 查看 `introspect` 输出的 `params` 列表 |
| 节点执行时缺少必需字段 | 前驱输出字段名与目标节点期望的不匹配 | 使用 `field-mapper` 节点显式映射，或依赖别名机制 |
| 视频时长不正确 | `num_frames / fps` 计算错误 | 按 §8 公式计算 |
| `input_params` 不生效 | 参数放在了 `params` 中（或反之） | 按 §3.2 规则区分 |
| JSON 字段未解析 | 字段名不在 `_JSON_FIELDS` 列表中 | 手动在 `field-mapper` 中处理 |
| 端口类型不兼容 | 前驱输出类型与后继输入类型不匹配 | 查阅 §4.4 兼容矩阵 |

---

*本文档基于 Mosaic Canvas 代码库自动生成，对应 `graph.py`、`executor.py`、`introspect.py` 的实现逻辑。*
