# Mosaic Canvas 流模型使用指南

Mosaic Canvas 是一个可视化管线编辑器。你把各种 AI 能力（文生图、语音合成、视频生成等）拖到画布上，用线连起来，数据就会沿着连线从上游节点流向下游节点，最终产出你想要的结果。

这篇文章讲清楚一件事：画布上那些方块和连线，在底层到底是怎么运作的。理解了这些规则，你就能自己手写 JSON 管线文件，也能快速排查为什么某个管线跑不通。

---

## 一张图长什么样

一个管线就是一份 JSON 文件，包含三个部分：节点、连线和输入数据。

```json
{
  "name": "我的管线",
  "nodes": [ ... ],
  "edges": [ ... ],
  "input": { "data": { ... } }
}
```

- `nodes` 是画布上那些方块，每个方块代表一种 AI 能力
- `edges` 是方块之间的连线，决定了数据流动的方向
- `input.data` 是你提供给整个管线的外部数据，比如一段文字、一张图片路径

这三部分缺一不可，但 `edges` 可以是空数组（表示只有一个节点，独立运行）。

---

## 节点：画布上的方块

每个节点描述了一个具体的 AI 操作。它的核心信息是「我是什么类型的节点」和「我要怎么配置」。

```json
{
  "id": "n1",
  "type": "text-to-image",
  "params": { "model": "stabilityai/sdxl-turbo" },
  "input_params": { "num_inference_steps": "25", "guidance_scale": "7.5" },
  "x": 40,
  "y": 40,
  "label": "文生图"
}
```

### id 和 type

`id` 是节点在当前管线中的唯一名字，你随便取，只要不重复就行。`type` 是节点类型，必须是系统已注册的名称，比如 `text-to-image`、`tts`、`video-encoder`。类型决定了这个节点能干什么、接受什么输入、产出什么输出。

`x` 和 `y` 是画布坐标，只影响在界面上的显示位置，不影响执行结果。`label` 是显示名称，也是纯 UI 用途。

### params 和 input_params：最容易搞混的地方

这是整个系统里最关键的概念。每个节点有两类参数，放错了节点就会报错或者不工作。

**`params` 是构造参数**。你可以理解为「造这台机器时的出厂设置」。节点在启动时会用这些参数初始化自己，比如选哪个模型、用什么编码格式、选哪个推理引擎。设置好之后整个执行过程中不会变。

常见的 `params` 参数：
- `model` — 指定使用哪个模型，如 `"stabilityai/sdxl-turbo"`
- `format` — 输出格式，如 `"mp4"`、`"wav"`
- `method` — 数字人引擎选择，如 `"sadtalker"`、`"wav2lip"`
- `backend` — TTS 后端选择，如 `"edge_tts"`、`"chattts"`
- `mapping` — 字段重映射规则，如 `'{"image": "data"}'`

**`input_params` 是运行参数**。这是「每次加工时调节的旋钮」，比如生成多少帧、引导系数多大、负面提示词是什么。这些参数在执行时和上游传来的数据合并在一起，传给节点处理。

常见的 `input_params` 参数：
- `prompt` / `negative_prompt` — 提示词
- `num_frames` / `fps` — 视频帧数和帧率
- `num_inference_steps` / `guidance_scale` — 扩散模型参数
- `voice` / `language` / `emotion` — 语音合成参数
- `seed` — 随机种子

**怎么判断一个参数该放哪里？** 如果你不确定，可以这样想：这个参数是在「选机器」时就决定的（比如用哪个模型），还是每次「加工」时可能调的（比如提示词）。前者放 `params`，后者放 `input_params`。

### 值都是字符串

从界面传过来的值默认都是字符串。后端会自动做类型转换：`"25"` 会变成整数 25，`"true"` 会变成布尔值 True，`"7.5"` 会变成浮点数 7.5。空字符串 `""` 会被当作 None，让节点使用自己的默认值。

有些字段名比较特殊，它们虽然写成字符串，但实际上是 JSON 结构。比如 `padding`、`mapping`、`formats` 这些字段，你写成 `"[0, 20, 0, 20]"`，后端会自动解析成列表 `[0, 20, 0, 20]`。

---

## 连线：数据怎么流动

连线决定了数据从哪个节点流到哪个节点。每条边有三个必填字段：`id`（唯一标识）、`source`（起点节点 id）、`target`（终点节点 id）。

```json
{
  "id": "e1",
  "source": "n1",
  "target": "n2"
}
```

### 连线有四条规则

1. 不能自己连自己（`source` 和 `target` 不能相同）
2. 同一对节点之间只能有一条连线
3. 不能形成环——数据只能往前流，不能绕回来
4. 连线的两端必须指向真实存在的节点

### 数据过滤：不是所有数据都会传过去

默认情况下，连线会把上游节点产出的数据智能过滤后再传给下游。过滤的依据是下游节点声明了需要哪些字段。比如 `video-encoder` 需要的是 `frames` 和 `fps`，那么上游传过来的其他字段（比如 `text`、`audio`）就会被过滤掉。

如果你想要精确控制，可以用 `pass_fields` 字段显式指定只传哪些字段：

```json
{
  "id": "e1",
  "source": "n1",
  "target": "n2",
  "pass_fields": ["frames", "fps"]
}
```

### 字段别名：名字对不上怎么办

有时候上游输出的字段名和下游期望的不一样。比如 `tts` 节点输出的是 `waveform`，但 `lip-syncer` 节点需要的是 `audio`。系统内置了一张别名映射表，会自动帮你桥接：

- 需要 `audio` → 会去找 `waveform`、`voice`、`audio_path`
- 需要 `face_image` → 会去找 `image`、`images`、`avatar`、`source_image`
- 需要 `frames` → 会去找 `video`、`images`、`image`、`frame_list`
- 需要 `prompt` → 会去找 `text`、`reply`、`response`、`summary`

大部分时候你不需要操心这个，系统会自动处理。但如果管线跑不通、提示缺少某个字段，可能就是别名没覆盖到的情况，这时候可以加一个 `field-mapper` 节点手动做字段重命名。

---

## 全局输入：给管线喂料

`input.data` 是你提供给整个管线的外部数据。它是一个扁平的键值对字典：

```json
{
  "input": {
    "data": {
      "prompt": "一只猫在玩毛线球",
      "text": "你好，欢迎使用数字人系统",
      "negative_prompt": "blurry, low quality"
    }
  }
}
```

### 注入规则

对于管线中最前面的节点（没有上游连线的节点，叫「源节点」），`input.data` 里的所有字段会直接注入到它的输入中。比如源节点是 `tts`，那么 `input.data.text` 就会成为它的文本输入。

对于后面的节点，`input.data` 只起补充作用——如果某个字段上游已经传过来了，就不会被覆盖；如果没传过来，才从 `input.data` 里取。这个机制让你可以设置全局默认值，比如所有节点共用一个 `seed` 或 `negative_prompt`。

### 优先级

一个节点最终拿到的输入数据，按优先级从低到高是：

1. 上游节点传来的数据（优先级最低）
2. 全局 `input.data` 里的字段（只填补上游没传的空缺）
3. 节点自己的 `input_params`（优先级最高，会覆盖同名字段）

---

## 执行顺序：谁先跑谁后跑

系统会自动分析节点之间的依赖关系，算出一个执行顺序（拓扑排序）。规则很简单：一个节点必须等它所有上游节点都跑完，才能开始执行。如果节点之间没有依赖关系，它们可能会并行执行。

执行过程中如果任何一个节点报错，整个管线会立即停止（fail-fast 机制），不会继续跑后面的节点。

最终结果从管线末端的节点（没有下游连线的节点，叫「汇节点」）收集。如果只有一个汇节点，直接返回它的输出；如果有多个，返回一个字典，key 是节点 id，value 是各自的输出。

---

## 常用节点速查

以下是搭建管线时最常用的节点类型。完整列表可以在画布左侧的节点面板里查看。

### 文本类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `text-generator` | 文本生成 | prompt | text |
| `text-summarizer` | 文本摘要 | text | text |
| `translator` | 翻译 | text | text |
| `chat` | 多轮对话 | messages | text |

### 图像类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `text-to-image` | 文生图 | prompt | image |
| `image-to-image` | 图生图 | image + prompt | image |
| `upscaler` | 超分辨率放大 | image | image |
| `background-remover` | 背景移除 | image | image |

### 视频类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `text-to-video` | 文生视频 | prompt | frames + fps |
| `image-to-video` | 图生视频 | image + prompt | frames + fps |
| `wan-video` | 万相视频 | prompt | frames + fps |
| `ltx-video` | LTX 视频 | prompt | frames + fps |

### 音频类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `tts` | 语音合成 | text | audio |
| `asr` | 语音识别 | audio | text |
| `music-generator` | 音乐生成 | prompt | audio |
| `voice-clone` | 语音克隆 | reference_audio + text | audio |

### 数字人类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `lip-syncer` | 唇形同步 | face_image + audio | frames + fps |
| `avatar-driver` | 头像驱动 | source_image + driving_audio | frames + fps |

### 导出类

| 类型 | 做什么 | 需要的输入 | 产出 |
|------|--------|-----------|------|
| `video-encoder` | 视频编码 | frames + fps | file |
| `multi-format-exporter` | 多格式导出 | data | file |

### 辅助类

| 类型 | 做什么 |
|------|--------|
| `field-mapper` | 字段重命名/映射/删除 |
| `data-merger` | 合并多个来源的数据 |
| `value-injector` | 注入静态值 |

---

## 数字人引擎选择

`lip-syncer` 和 `avatar-driver` 通过 `params.method` 切换底层引擎：

| method | 引擎 | 说明 |
|--------|------|------|
| `sadtalker` | SadTalker | 3DMM 驱动，适合肖像照片 |
| `wav2lip` | Wav2Lip | 经典唇形同步，速度快 |
| `liveportrait` | LivePortrait | 表情更自然，支持眼睛动画 |
| `geneface` | GeneFace | 支持头部和躯干动画 |
| `hallo` | Hallo | 高质量音频驱动肖像动画 |
| `audio2face` | Audio2Face | Nvidia 方案，需 GPU |
| `anitalker` | AniTalker | 轻量级方案 |

---

## 视频时长怎么算

视频时长由帧数和帧率决定：`时长（秒）= num_frames / fps`。

比如 `num_frames: "241"` 配合 `fps: "8"`，生成的视频大约 30 秒。`num_frames: "49"` 配合 `fps: "8"`，大约 6 秒。

注意 `num_frames` 和 `fps` 都是放在 `input_params` 里的运行参数，不是 `params`。

---

## 常见问题

**节点报 TypeError: unexpected keyword argument**
你把运行参数放到了 `params` 里。检查这个参数是不是应该放在 `input_params`。

**节点提示缺少必需字段**
上游输出的字段名和下游期望的对不上。试试加一个 `field-mapper` 节点做手动映射，比如 `{"image": "data"}` 把 `image` 字段重命名为 `data`。

**导出的文件是空的或格式不对**
检查 `video-encoder` 的 `params.format` 是否正确（mp4/avi/webm/gif），以及上游是否真的输出了 `frames` 字段。

**多格式导出器报错**
`multi-format-exporter` 需要的输入字段名是 `data`，但大多数节点输出的字段名是 `image`、`audio` 等。在前面加一个 `field-mapper`，设置 `mapping: '{"image": "data"}'` 或 `mapping: '{"audio": "data"}'`。

---

## 测试用 JSON 文件

`docs/test-pipelines/` 目录下有一组开箱即用的管线 JSON 文件，覆盖了最常见的使用场景。每个文件都可以直接在 Mosaic Canvas 中加载运行，不需要额外准备素材。

| 文件 | 场景 | 节点数 | 说明 |
|------|------|--------|------|
| `01-text-to-image.json` | 文生图 | 3 | 文生图 → 字段映射 → 导出 PNG |
| `02-text-to-video.json` | 文生视频 | 2 | 文生视频 → 编码 MP4 |
| `03-tts-audio.json` | 语音合成 | 3 | TTS → 字段映射 → 导出 WAV |
| `04-music-generation.json` | 音乐生成 | 3 | 音乐生成 → 字段映射 → 导出 |
| `05-text-summarizer.json` | 文本摘要 | 2 | 文本摘要 → 输出 |
| `06-translate-tts.json` | 翻译 + 语音 | 3 | 翻译 → TTS → 导出 |
| `07-digital-human-30s.json` | 30s 数字人 | 3 | TTS → 唇形同步 → 编码 MP4 |
| `08-multi-engine-video.json` | 多引擎并行 | 6 | 两种视频引擎并行生成 |

前 6 个文件只需要文本输入，不依赖任何外部文件。第 7 个数字人管线需要提供一张人脸图片路径（`face_image` 字段），这是唇形同步的必要输入。第 8 个展示了分支拓扑——两个视频引擎各走一条链路，互不干扰。
