/**
 * i18n — Internationalization system with Chinese (zh) and English (en) support.
 *
 * Usage:
 *   I18n.t('key')           → translated string
 *   I18n.setLang('zh')      → switch language
 *   I18n.getLang()          → current language code
 *   I18n.on(callback)       → subscribe to language changes
 *   I18n.applyToDOM(root)   → update all [data-i18n] elements
 *
 * HTML elements with data-i18n="key" are auto-translated.
 * For attributes, use data-i18n-title, data-i18n-placeholder.
 */
const I18n = (() => {
    const STORAGE_KEY = 'mosaic-canvas-lang';
    let _lang = localStorage.getItem(STORAGE_KEY) || (navigator.language.startsWith('zh') ? 'zh' : 'en');
    const _listeners = [];

    // ---- Translation dictionaries ----
    const _dict = {
        en: {
            // Toolbar
            'app.title': 'Mosaic Canvas — Visual Pipeline Editor',
            'btn.new': 'New',
            'btn.save': 'Save',
            'btn.load': 'Load',
            'btn.validate': 'Validate',
            'btn.export': 'Export',
            'btn.run': 'Run',
            'btn.stop': 'Stop',
            'btn.templates': 'Templates',
            'btn.shortcuts': 'Shortcuts',
            'btn.lang': 'Language',
            'btn.auto_layout': 'Auto Layout',
            'btn.duplicate': 'Duplicate',
            'btn.delete': 'Delete',
            'btn.copy': 'Copy',
            'btn.paste': 'Paste',

            // Pipeline name
            'pipeline.untitled': 'Untitled Pipeline',
            'pipeline.name_placeholder': 'Pipeline name…',

            // Palette
            'palette.title': 'Nodes',
            'palette.search': 'Search nodes…',
            'palette.loading': 'Loading nodes…',
            'palette.no_nodes': 'No nodes available. Is Mosaic installed?',
            'palette.no_match': 'No nodes match your search.',
            'palette.templates_section': 'Quick Start Templates',

            // Canvas
            'canvas.empty_title': 'Drag nodes from the left panel to start building',
            'canvas.empty_hint': 'Connect nodes by dragging from output ● to input ●',
            'canvas.empty_template': 'Or pick a template to get started →',
            'canvas.zoom_in': 'Zoom in',
            'canvas.zoom_out': 'Zoom out',
            'canvas.zoom_fit': 'Fit to view',
            'canvas.source': 'Source',
            'canvas.in': 'In',
            'canvas.out': 'Out',

            // Sidebar tabs
            'tab.properties': 'Properties',
            'tab.input': 'Input',
            'tab.results': 'Results',

            // Properties panel
            'prop.empty': 'Select a node to edit its properties',
            'prop.node_not_found': 'Node not found',
            'prop.label': 'Label',
            'prop.label_placeholder': 'Custom label…',
            'prop.parameters': 'Parameters',
            'prop.no_params': 'This node has no configurable parameters.',
            'prop.delete_node': 'Delete Node',
            'prop.default_value': 'Default',
            'prop.reset_default': 'Reset to default',
            'param.type': 'Type',
            'param.required': 'Required',
            'param.optional': 'Optional',
            'param.show_help': 'Show help',
            'param.hide_help': 'Hide help',
            'param.no_help': 'No description available.',
            'param.changed': 'Modified',
            'param.default_option': '— Use default —',

            // Input panel
            'input.title': 'Pipeline Input Data',
            'input.hint': 'Key-value pairs passed to source nodes as MosaicData',
            'input.add_field': '+ Add field',
            'input.key_placeholder': 'key',
            'input.value_placeholder': 'value',
            'input.common_keys': 'Common keys',

            // Results panel
            'results.empty': 'Run a pipeline to see results',
            'results.running': 'Running…',
            'results.status': 'Status',
            'results.duration': 'Duration',
            'results.nodes': 'Nodes',
            'results.success': 'Success',
            'results.failed': 'Failed',
            'results.node_results': 'Node Results',
            'results.final_output': 'Final Output',
            'results.skipped': 'Skipped (upstream error)',

            // Modals
            'modal.export_title': 'Exported Python Code',
            'modal.copy_clipboard': 'Copy to clipboard',
            'modal.close': 'Close',
            'modal.validate_title': 'Validation Results',
            'modal.load_title': 'Load Pipeline',
            'modal.load_hint': 'Paste pipeline JSON below or select a file:',
            'modal.load_confirm': 'Load',
            'modal.cancel': 'Cancel',
            'modal.templates_title': 'Pipeline Templates',
            'modal.templates_hint': 'Click a template to load it. Your current pipeline will be replaced.',
            'modal.shortcuts_title': 'Keyboard Shortcuts',

            // Validation
            'validate.valid': '✓ Pipeline is valid!',
            'validate.nodes_label': 'Nodes',
            'validate.edges_label': 'Edges',
            'validate.exec_order': 'Execution order',

            // Status bar
            'status.ready': 'Ready',
            'status.loading_catalog': 'Loading node catalog…',
            'status.failed_load': 'Failed to load nodes',
            'status.validating': 'Validating…',
            'status.validation_passed': 'Validation passed',
            'status.validation_failed': 'Validation failed',
            'status.generating_code': 'Generating code…',
            'status.code_generated': 'Code generated',
            'status.export_error': 'Export error',
            'status.running': 'Running pipeline…',
            'status.execution_failed': 'Execution failed',
            'status.nodes_count': 'nodes',
            'status.edges_count': 'edges',

            // Toasts
            'toast.new_created': 'New pipeline created',
            'toast.saved': 'Pipeline saved',
            'toast.loaded': 'Pipeline loaded',
            'toast.load_failed': 'Failed to parse JSON: ',
            'toast.select_file': 'Please select a file or paste JSON',
            'toast.validation_error': 'Validation error: ',
            'toast.export_error': 'Export error: ',
            'toast.copied': 'Copied to clipboard',
            'toast.copy_failed': 'Failed to copy',
            'toast.add_node_first': 'Add at least one node before running',
            'toast.stop_unsupported': 'Stop is not yet supported. Execution runs to completion.',
            'toast.run_success': 'Pipeline completed successfully',
            'toast.run_failed': 'Pipeline execution failed',
            'toast.exec_error': 'Execution error: ',
            'toast.loaded_nodes': 'Loaded {count} nodes across {domains} domains',
            'toast.load_catalog_failed': 'Failed to load node catalog: ',
            'toast.template_loaded': 'Template "{name}" loaded',
            'toast.clear_confirm': 'Clear the current pipeline?',
            'toast.node_deleted': 'Node deleted',
            'toast.node_duplicated': 'Node duplicated',
            'toast.edge_deleted': 'Connection deleted',
            'toast.edge_cycle': 'Cannot connect: would create a cycle',
            'toast.edge_duplicate': 'Connection already exists',
            'toast.edge_self': 'Cannot connect a node to itself',
            'toast.lang_changed': 'Language switched to {lang}',

            // Run progress
            'run.queued': 'Running: {count} nodes queued',
            'run.node_start': 'Running: {name}',
            'run.node_done': 'Completed: {name} ({duration}s)',
            'run.node_error': 'Error in: {name}',
            'run.complete': 'Pipeline {status} in {duration}s',
            'run.complete_status_ok': 'completed',
            'run.complete_status_fail': 'failed',

            // Keyboard shortcuts
            'shortcut.delete': 'Delete selected',
            'shortcut.escape': 'Cancel selection / connection',
            'shortcut.space_drag': 'Pan canvas',
            'shortcut.wheel': 'Zoom canvas',
            'shortcut.ctrl_d': 'Duplicate selected node',
            'shortcut.ctrl_c': 'Copy selected node',
            'shortcut.ctrl_v': 'Paste copied node',

            // Domains
            'domain.text': 'Text',
            'domain.image': 'Image',
            'domain.video': 'Video',
            'domain.audio': 'Audio',
            'domain.subtitle': 'Subtitle',
            'domain.consistency': 'Consistency',
            'domain.digital_human': 'Digital Human',
            'domain.export': 'Export',
            'domain.rag': 'RAG',
            'domain.core': 'Core',

            // Common input keys
            'input_key.prompt': 'Text prompt',
            'input_key.negative_prompt': 'Negative prompt',
            'input_key.width': 'Width',
            'input_key.height': 'Height',
            'input_key.seed': 'Seed',
            'input_key.text': 'Text content',
            'input_key.audio': 'Audio path',
            'input_key.image': 'Image path',
            'input_key.video': 'Video path',
        },

        zh: {
            // Toolbar
            'app.title': 'Mosaic Canvas — 可视化流水线编辑器',
            'btn.new': '新建',
            'btn.save': '保存',
            'btn.load': '加载',
            'btn.validate': '校验',
            'btn.export': '导出',
            'btn.run': '运行',
            'btn.stop': '停止',
            'btn.templates': '模板',
            'btn.shortcuts': '快捷键',
            'btn.lang': '语言',
            'btn.auto_layout': '自动排列',
            'btn.duplicate': '复制节点',
            'btn.delete': '删除',
            'btn.copy': '复制',
            'btn.paste': '粘贴',

            // Pipeline name
            'pipeline.untitled': '未命名流水线',
            'pipeline.name_placeholder': '流水线名称…',

            // Palette
            'palette.title': '节点',
            'palette.search': '搜索节点…',
            'palette.loading': '正在加载节点…',
            'palette.no_nodes': '无可用节点。请确认 Mosaic 已安装。',
            'palette.no_match': '没有匹配的节点。',
            'palette.templates_section': '快速开始模板',

            // Canvas
            'canvas.empty_title': '从左侧面板拖拽节点开始构建',
            'canvas.empty_hint': '从输出端口 ● 拖拽到输入端口 ● 连接节点',
            'canvas.empty_template': '或选择一个模板快速开始 →',
            'canvas.zoom_in': '放大',
            'canvas.zoom_out': '缩小',
            'canvas.zoom_fit': '适应视图',
            'canvas.source': '输入源',
            'canvas.in': '输入',
            'canvas.out': '输出',

            // Sidebar tabs
            'tab.properties': '属性',
            'tab.input': '输入',
            'tab.results': '结果',

            // Properties panel
            'prop.empty': '选择一个节点来编辑其属性',
            'prop.node_not_found': '未找到节点',
            'prop.label': '标签',
            'prop.label_placeholder': '自定义标签…',
            'prop.parameters': '参数',
            'prop.no_params': '此节点没有可配置的参数。',
            'prop.delete_node': '删除节点',
            'prop.default_value': '默认值',
            'prop.reset_default': '恢复默认',
            'param.type': '类型',
            'param.required': '必填',
            'param.optional': '可选',
            'param.show_help': '显示帮助',
            'param.hide_help': '隐藏帮助',
            'param.no_help': '暂无描述信息。',
            'param.changed': '已修改',
            'param.default_option': '— 使用默认值 —',

            // Input panel
            'input.title': '流水线输入数据',
            'input.hint': '键值对，将作为 MosaicData 传递给源节点',
            'input.add_field': '+ 添加字段',
            'input.key_placeholder': '键名',
            'input.value_placeholder': '值',
            'input.common_keys': '常用键名',

            // Results panel
            'results.empty': '运行流水线以查看结果',
            'results.running': '运行中…',
            'results.status': '状态',
            'results.duration': '耗时',
            'results.nodes': '节点数',
            'results.success': '成功',
            'results.failed': '失败',
            'results.node_results': '节点结果',
            'results.final_output': '最终输出',
            'results.skipped': '已跳过（上游错误）',

            // Modals
            'modal.export_title': '导出的 Python 代码',
            'modal.copy_clipboard': '复制到剪贴板',
            'modal.close': '关闭',
            'modal.validate_title': '校验结果',
            'modal.load_title': '加载流水线',
            'modal.load_hint': '在下方粘贴流水线 JSON 或选择文件：',
            'modal.load_confirm': '加载',
            'modal.cancel': '取消',
            'modal.templates_title': '流水线模板',
            'modal.templates_hint': '点击模板以加载。当前流水线将被替换。',
            'modal.shortcuts_title': '键盘快捷键',

            // Validation
            'validate.valid': '✓ 流水线校验通过！',
            'validate.nodes_label': '节点',
            'validate.edges_label': '连接',
            'validate.exec_order': '执行顺序',

            // Status bar
            'status.ready': '就绪',
            'status.loading_catalog': '正在加载节点目录…',
            'status.failed_load': '加载节点失败',
            'status.validating': '校验中…',
            'status.validation_passed': '校验通过',
            'status.validation_failed': '校验未通过',
            'status.generating_code': '生成代码中…',
            'status.code_generated': '代码已生成',
            'status.export_error': '导出错误',
            'status.running': '正在运行流水线…',
            'status.execution_failed': '执行失败',
            'status.nodes_count': '个节点',
            'status.edges_count': '条连接',

            // Toasts
            'toast.new_created': '已创建新流水线',
            'toast.saved': '流水线已保存',
            'toast.loaded': '流水线已加载',
            'toast.load_failed': 'JSON 解析失败：',
            'toast.select_file': '请选择文件或粘贴 JSON',
            'toast.validation_error': '校验错误：',
            'toast.export_error': '导出错误：',
            'toast.copied': '已复制到剪贴板',
            'toast.copy_failed': '复制失败',
            'toast.add_node_first': '运行前请先添加至少一个节点',
            'toast.stop_unsupported': '暂不支持停止。执行将运行至完成。',
            'toast.run_success': '流水线执行成功',
            'toast.run_failed': '流水线执行失败',
            'toast.exec_error': '执行错误：',
            'toast.loaded_nodes': '已加载 {count} 个节点，涵盖 {domains} 个领域',
            'toast.load_catalog_failed': '加载节点目录失败：',
            'toast.template_loaded': '已加载模板「{name}」',
            'toast.clear_confirm': '清空当前流水线？',
            'toast.node_deleted': '节点已删除',
            'toast.node_duplicated': '节点已复制',
            'toast.edge_deleted': '连接已删除',
            'toast.edge_cycle': '无法连接：会形成环路',
            'toast.edge_duplicate': '连接已存在',
            'toast.edge_self': '无法连接到自身',
            'toast.lang_changed': '语言已切换为{lang}',

            // Run progress
            'run.queued': '运行中：{count} 个节点排队',
            'run.node_start': '运行中：{name}',
            'run.node_done': '完成：{name}（{duration}秒）',
            'run.node_error': '错误：{name}',
            'run.complete': '流水线{status}，耗时 {duration} 秒',
            'run.complete_status_ok': '完成',
            'run.complete_status_fail': '失败',

            // Keyboard shortcuts
            'shortcut.delete': '删除选中项',
            'shortcut.escape': '取消选择 / 连接',
            'shortcut.space_drag': '平移画布',
            'shortcut.wheel': '缩放画布',
            'shortcut.ctrl_d': '复制选中节点',
            'shortcut.ctrl_c': '复制选中节点',
            'shortcut.ctrl_v': '粘贴已复制节点',

            // Domains
            'domain.text': '文本',
            'domain.image': '图像',
            'domain.video': '视频',
            'domain.audio': '音频',
            'domain.subtitle': '字幕',
            'domain.consistency': '一致性',
            'domain.digital_human': '数字人',
            'domain.export': '导出',
            'domain.rag': 'RAG',
            'domain.core': '核心',

            // Common input keys
            'input_key.prompt': '文本提示词',
            'input_key.negative_prompt': '负向提示词',
            'input_key.width': '宽度',
            'input_key.height': '高度',
            'input_key.seed': '随机种子',
            'input_key.text': '文本内容',
            'input_key.audio': '音频路径',
            'input_key.image': '图像路径',
            'input_key.video': '视频路径',
        },
    };

    // ---- Parameter friendly name translations ----
    const _paramLabels = {
        en: {
            'model': 'Model',
            'device': 'Device',
            'dtype': 'Precision',
            'enable_attention_slicing': 'Attention Slicing',
            'enable_vae_slicing': 'VAE Slicing',
            'enable_vae_tiling': 'VAE Tiling',
            'enable_model_cpu_offload': 'CPU Offload',
            'scheduler_name': 'Scheduler',
            'pipeline_class': 'Pipeline Class',
            'backend': 'Backend',
            'language': 'Language',
            'seed': 'Seed',
            'width': 'Width',
            'height': 'Height',
            'num_inference_steps': 'Inference Steps',
            'guidance_scale': 'Guidance Scale',
            'negative_prompt': 'Negative Prompt',
            'num_images': 'Image Count',
            'num_frames': 'Frame Count',
            'fps': 'FPS',
            'format': 'Format',
            'scale': 'Scale Factor',
            'strength': 'Strength',
            'skeleton_type': 'Skeleton Type',
            'cache_dir': 'Cache Directory',
            'output_dir': 'Output Directory',
            'quality': 'Quality',
            'chunk_size': 'Chunk Size',
            'overlap': 'Overlap',
            'temperature': 'Temperature',
            'top_p': 'Top P',
            'top_k': 'Top K',
            'max_tokens': 'Max Tokens',
        },
        zh: {
            'model': '模型',
            'device': '设备',
            'dtype': '精度',
            'enable_attention_slicing': '注意力切片',
            'enable_vae_slicing': 'VAE 切片',
            'enable_vae_tiling': 'VAE 分块',
            'enable_model_cpu_offload': 'CPU 卸载',
            'scheduler_name': '调度器',
            'pipeline_class': 'Pipeline 类',
            'backend': '后端引擎',
            'language': '语言',
            'seed': '随机种子',
            'width': '宽度',
            'height': '高度',
            'num_inference_steps': '推理步数',
            'guidance_scale': '引导系数',
            'negative_prompt': '负向提示词',
            'num_images': '图片数量',
            'num_frames': '帧数',
            'fps': '帧率',
            'format': '格式',
            'scale': '缩放倍数',
            'strength': '强度',
            'skeleton_type': '骨架类型',
            'cache_dir': '缓存目录',
            'output_dir': '输出目录',
            'quality': '质量',
            'chunk_size': '块大小',
            'overlap': '重叠',
            'temperature': '温度',
            'top_p': 'Top P',
            'top_k': 'Top K',
            'max_tokens': '最大 Token 数',
        },
    };

    // ---- Parameter description translations (bilingual) ----
    const _paramHelp = {
        en: {
            'model': 'HuggingFace model ID or local path. Example: stabilityai/sdxl-turbo',
            'device': 'Inference device. "auto" picks the best available GPU.',
            'dtype': 'Model precision. float16 saves VRAM; float32 is more stable.',
            'enable_attention_slicing': 'Reduce VRAM usage by processing attention in slices. Slower but uses less memory.',
            'enable_vae_slicing': 'Reduce VRAM by decoding VAE in slices. Useful for large batch sizes.',
            'enable_vae_tiling': 'Tile VAE decoding for large images. Prevents OOM on high-res outputs.',
            'enable_model_cpu_offload': 'Move model modules to GPU one at a time. Greatly reduces VRAM at cost of speed.',
            'scheduler_name': 'Diffusion scheduler class. Common: EulerDiscreteScheduler, DDIMScheduler, DPMSolverMultistepScheduler.',
            'pipeline_class': 'Explicit diffusers Pipeline class override (advanced). Leave empty for auto-detection.',
            'backend': 'TTS backend engine to use.',
            'language': 'Language code for text/speech processing.',
            'seed': 'Random seed for reproducibility. Leave empty for random each run.',
            'width': 'Output image width in pixels. Must be a multiple of 8.',
            'height': 'Output image height in pixels. Must be a multiple of 8.',
            'num_inference_steps': 'Number of denoising steps. More = higher quality but slower. Typical: 20-50.',
            'guidance_scale': 'Classifier-free guidance scale. Higher = more prompt adherence. Typical: 7-10.',
            'negative_prompt': 'Describe what to avoid in the generation.',
            'num_images': 'Number of images to generate per prompt.',
            'num_frames': 'Number of video frames to generate.',
            'fps': 'Frames per second for output video.',
            'format': 'Output file format.',
            'scale': 'Upscaling factor. Common: 2, 4.',
            'strength': 'Transformation strength. 0 = no change, 1 = full transformation.',
        },
        zh: {
            'model': 'HuggingFace 模型 ID 或本地路径。示例：stabilityai/sdxl-turbo',
            'device': '推理设备。"auto" 自动选择最佳可用 GPU。',
            'dtype': '模型精度。float16 节省显存；float32 更稳定。',
            'enable_attention_slicing': '通过分片处理注意力来减少显存占用。速度较慢但内存更省。',
            'enable_vae_slicing': '通过分片解码 VAE 来减少显存。适用于大批量生成。',
            'enable_vae_tiling': '对大图进行 VAE 分块解码。防止高分辨率输出时显存溢出。',
            'enable_model_cpu_offload': '逐个将模型模块移至 GPU。大幅减少显存占用，但速度较慢。',
            'scheduler_name': '扩散调度器类名。常用：EulerDiscreteScheduler、DDIMScheduler、DPMSolverMultistepScheduler。',
            'pipeline_class': '显式指定 diffusers Pipeline 类（高级）。留空则自动检测。',
            'backend': 'TTS 语音合成后端引擎。',
            'language': '文本/语音处理的语言代码。',
            'seed': '随机种子，用于结果复现。留空则每次随机。',
            'width': '输出图片宽度（像素）。必须为 8 的倍数。',
            'height': '输出图片高度（像素）。必须为 8 的倍数。',
            'num_inference_steps': '去噪步数。越多质量越高但速度越慢。典型值：20-50。',
            'guidance_scale': '分类器自由引导系数。越高越遵循提示词。典型值：7-10。',
            'negative_prompt': '描述生成中需要避免的内容。',
            'num_images': '每个提示词生成的图片数量。',
            'num_frames': '生成的视频帧数。',
            'fps': '输出视频的帧率。',
            'format': '输出文件格式。',
            'scale': '放大倍数。常用：2、4。',
            'strength': '变换强度。0 = 不变，1 = 完全变换。',
        },
    };

    // ---- Node name translations ----
    const _nodeNames = {
        en: {}, // English uses the original names
        zh: {
            'text-to-image': '文生图',
            'image-to-image': '图生图',
            'inpainting': '局部重绘',
            'upscaler': '图像放大',
            'background-remover': '背景移除',
            'stylizer': '风格迁移',
            'text-to-video': '文生视频',
            'image-to-video': '图生视频',
            'video-continuation': '视频续写',
            'frame-interpolation': '帧插值',
            'frame-extractor': '帧提取',
            'ltx-video': 'LTX 视频',
            'wan-video': 'Wan 视频',
            'hunyuan-video': '混元视频',
            'text-to-speech': '文本转语音',
            'speech-to-text': '语音转文本',
            'music-generator': '音乐生成',
            'voice-cloner': '声音克隆',
            'subtitle-generator': '字幕生成',
            'subtitle-translator': '字幕翻译',
            'subtitle-merger': '字幕合并',
            'cross-frame-consistency': '跨帧一致性',
            'identity-keeper': '身份保持',
            'style-keeper': '风格保持',
            'motion-generator': '动作生成',
            'realtime-renderer': '实时渲染',
            'avatar-driver': '虚拟人驱动',
            'lip-syncer': '唇形同步',
            'multi-format-exporter': '多格式导出',
            'video-encoder': '视频编码',
            'livestreamer': '直播推流',
            'rag-qa': 'RAG 问答',
            'document-loader': '文档加载',
            'text-rewriter': '文本改写',
        },
    };

    function t(key, params) {
        let str = (_dict[_lang] && _dict[_lang][key]) || (_dict.en && _dict.en[key]) || key;
        if (params) {
            Object.keys(params).forEach(k => {
                str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), params[k]);
            });
        }
        return str;
    }

    function paramLabel(name) {
        return (_paramLabels[_lang] && _paramLabels[_lang][name])
            || (_paramLabels.en && _paramLabels.en[name])
            || name;
    }

    function paramHelp(name) {
        return (_paramHelp[_lang] && _paramHelp[_lang][name])
            || (_paramHelp.en && _paramHelp.en[name])
            || '';
    }

    function nodeName(name) {
        return (_nodeNames[_lang] && _nodeNames[_lang][name])
            || (_nodeNames.en && _nodeNames.en[name])
            || name;
    }

    function domainLabel(domain) {
        return t('domain.' + domain) !== ('domain.' + domain) ? t('domain.' + domain) : domain;
    }

    function setLang(lang) {
        if (lang === _lang) return;
        _lang = lang;
        localStorage.setItem(STORAGE_KEY, lang);
        _listeners.forEach(fn => fn(lang));
        applyToDOM();
    }

    function getLang() { return _lang; }

    function on(callback) {
        _listeners.push(callback);
    }

    function applyToDOM(root) {
        const scope = root || document;
        // Text content
        scope.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.dataset.i18n;
            el.textContent = t(key);
        });
        // Title attribute
        scope.querySelectorAll('[data-i18n-title]').forEach(el => {
            el.title = t(el.dataset.i18nTitle);
        });
        // Placeholder attribute
        scope.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            el.placeholder = t(el.dataset.i18nPlaceholder);
        });
    }

    return { t, paramLabel, paramHelp, nodeName, domainLabel, setLang, getLang, on, applyToDOM };
})();
