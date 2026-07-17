/**
 * Templates — pre-built pipeline templates for common node combinations.
 *
 * Each template defines nodes, edges, suggested input data, and a description
 * in both English and Chinese. Templates are loaded into the canvas with a
 * single click, giving users a quick starting point.
 *
 * IMPORTANT: `params` are constructor arguments passed to Node.__init__().
 * `input_params` are runtime values merged into MosaicData and passed to run().
 * Mixing them up causes TypeError at node instantiation or missing values at
 * execution time.
 */
const Templates = (() => {
    const SPACING_X = 280;
    const SPACING_Y = 0;

    function pos(col, row) {
        return { x: col * SPACING_X + 40, y: row * (SPACING_Y + 120) + 40 };
    }

    const _templates = [
        {
            id: 'text-to-image-basic',
            name: { en: 'Text to Image (Basic)', zh: '文生图（基础）' },
            icon: '🖼️',
            description: {
                en: 'Generate an image from a text prompt using a diffusion model.',
                zh: '使用扩散模型从文本提示词生成图片。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25', guidance_scale: '7.5' },
                    ...pos(0, 0),
                },
            ],
            edges: [],
            input: { prompt: 'a cute cat sitting on a windowsill, warm sunlight, detailed fur' },
        },
        {
            id: 'text-to-image-upscale-export',
            name: { en: 'Generate → Upscale → Export', zh: '生成 → 放大 → 导出' },
            icon: '📊',
            description: {
                en: 'Generate an image, upscale it for higher resolution, then export.',
                zh: '生成图片后放大至更高分辨率，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'upscaler', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'a majestic mountain landscape at sunset, ultra detailed' },
        },
        {
            id: 'image-to-image-stylize',
            name: { en: 'Image → Stylize → Export', zh: '图片 → 风格化 → 导出' },
            icon: '🎨',
            description: {
                en: 'Transform an existing image with a style transfer, then export.',
                zh: '对已有图片进行风格迁移，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'image-to-image', label: '',
                    params: {},
                    input_params: { strength: '0.65' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'stylizer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'oil painting style, vibrant colors', image: '/path/to/input.jpg' },
        },
        {
            id: 'text-to-video',
            name: { en: 'Text to Video', zh: '文生视频' },
            icon: '🎬',
            description: {
                en: 'Generate a short video from a text prompt.',
                zh: '从文本提示词生成短视频。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-video', label: '',
                    params: {},
                    input_params: { num_frames: '24', fps: '8' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'video-encoder', label: '',
                    params: { format: 'mp4' },
                    input_params: {},
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { prompt: 'a cat playing with a ball of yarn, cinematic' },
        },
        {
            id: 'tts-digital-human',
            name: { en: 'TTS → Lip Sync → Render', zh: '语音合成 → 唇形同步 → 渲染' },
            icon: '🧑',
            description: {
                en: 'Generate speech from text, sync lips to a face, then render a digital human video.',
                zh: '从文本生成语音，进行唇形同步，然后渲染数字人视频。',
            },
            nodes: [
                {
                    id: 'n1', type: 'tts', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'lip-syncer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'realtime-renderer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'video-encoder', label: '',
                    params: { format: 'mp4' },
                    input_params: {},
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { text: '你好，欢迎使用 Mosaic 数字人系统。', source_image: '/path/to/avatar.png' },
        },
        {
            id: 'video-subtitle-export',
            name: { en: 'Audio → Subtitles → Export', zh: '音频 → 字幕 → 导出' },
            icon: '📝',
            description: {
                en: 'Transcribe audio to text, generate subtitles, then export.',
                zh: '将音频转录为文本，生成字幕，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'asr', label: '',
                    params: {},
                    input_params: { language: 'auto' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'subtitle-generator', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["srt"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { audio: '/path/to/audio.wav' },
        },
        {
            id: 'rag-qa',
            name: { en: 'Document → Retrieve', zh: '文档解析 → 检索' },
            icon: '📚',
            description: {
                en: 'Parse a document and answer questions using retrieval.',
                zh: '解析文档并使用检索回答问题。',
            },
            nodes: [
                {
                    id: 'n1', type: 'document-parser', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'retriever', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { file_path: '/path/to/doc.pdf', query: 'What is the capital of France?' },
        },
        {
            id: 'image-inpainting-export',
            name: { en: 'Inpainting → Export', zh: '局部重绘 → 导出' },
            icon: '✏️',
            description: {
                en: 'Edit specific regions of an image using inpainting, then export.',
                zh: '使用局部重绘编辑图片的特定区域，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'inpainting', label: '',
                    params: {},
                    input_params: { strength: '0.85' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { prompt: 'a red sports car', image: '/path/to/input.jpg', mask: '/path/to/mask.png' },
        },
        {
            id: 'music-generation',
            name: { en: 'Music Generation', zh: '音乐生成' },
            icon: '🎵',
            description: {
                en: 'Generate music from a text description.',
                zh: '从文本描述生成音乐。',
            },
            nodes: [
                {
                    id: 'n1', type: 'music-generator', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'audio', formats: '["wav"]' },
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { prompt: 'upbeat electronic music with a catchy melody, 120 BPM' },
        },
        {
            id: 'chat-fieldmapper-text-to-image',
            name: { en: 'Chat → Map → Image → Export', zh: '对话 → 映射 → 文生图 → 导出' },
            icon: '💬',
            description: {
                en: 'Chat generates text, field-mapper renames response→prompt, then generate image and export.',
                zh: '对话节点生成文本，字段映射将 response 重命名为 prompt，然后生成图片并导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'chat', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"response": "prompt"}', drop_fields: '["messages"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25', guidance_scale: '7.5' },
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { message: 'Describe a futuristic city at sunset with flying cars' },
        },
        {
            id: 'rag-complete',
            name: { en: 'Complete RAG Pipeline', zh: '完整 RAG 流程' },
            icon: '📖',
            description: {
                en: 'Parse document, index vectors, retrieve relevant chunks, and generate cited answer.',
                zh: '解析文档，索引向量，检索相关片段，生成带引用的回答。',
            },
            nodes: [
                {
                    id: 'n1', type: 'document-parser', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'vector-indexer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'retriever', label: '',
                    params: {},
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'citation-generator', label: '',
                    params: {},
                    input_params: {},
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { file_path: '/path/to/document.pdf', query: 'What are the key findings?' },
        },
        {
            id: 'subtitle-translation',
            name: { en: 'Audio → Subtitle → Translate → Export', zh: '音频 → 字幕 → 翻译 → 导出' },
            icon: '🌍',
            description: {
                en: 'Transcribe audio, generate subtitles, translate them, then export.',
                zh: '转录音频，生成字幕，翻译字幕，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'asr', label: '',
                    params: {},
                    input_params: { language: 'auto' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'subtitle-generator', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'subtitle-translator', label: '',
                    params: {},
                    input_params: { target_language: 'en' },
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["srt"]' },
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { audio: '/path/to/audio.wav' },
        },
        {
            id: 'image-bg-remove-export',
            name: { en: 'Generate → Remove BG → Export', zh: '生成 → 去背景 → 导出' },
            icon: '✂️',
            description: {
                en: 'Generate an image, remove its background, then export as PNG.',
                zh: '生成图片后去除背景，然后导出为 PNG。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'background-remover', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'a product photo of a red sneaker on white background' },
        },
        {
            id: 'prompt-expand-image-upscale',
            name: { en: 'Expand Prompt → Image → Upscale → Export', zh: '提示词扩展 → 文生图 → 放大 → 导出' },
            icon: '🔍',
            description: {
                en: 'Expand a short prompt into a detailed one, generate image, upscale, and export.',
                zh: '将简短提示词扩展为详细描述，生成图片，放大，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-generator', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"text": "prompt"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '30', guidance_scale: '7.5' },
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'upscaler', label: '',
                    params: {},
                    input_params: {},
                    ...pos(3, 0),
                },
                {
                    id: 'n5', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(4, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
            ],
            input: { prompt: 'a dragon perched on a mountain' },
        },
        {
            id: 'video-frame-interpolation',
            name: { en: 'Text → Video → Interpolate → Encode', zh: '文生视频 → 补帧 → 编码' },
            icon: '🎞️',
            description: {
                en: 'Generate a video, interpolate frames for smoothness, then encode as MP4.',
                zh: '生成视频后补帧提升流畅度，然后编码为 MP4。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-video', label: '',
                    params: {},
                    input_params: { num_frames: '16', fps: '8' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'frame-interpolation', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'video-encoder', label: '',
                    params: { format: 'mp4' },
                    input_params: {},
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'a butterfly flying through a garden, slow motion' },
        },
        {
            id: 'meeting-summary',
            name: { en: 'Audio → Transcribe → Summarize → Export', zh: '音频 → 转录 → 摘要 → 导出' },
            icon: '📋',
            description: {
                en: 'Transcribe meeting audio, generate a summary, then export as text.',
                zh: '转录会议音频，生成摘要，然后导出为文本。',
            },
            nodes: [
                {
                    id: 'n1', type: 'asr', label: '',
                    params: {},
                    input_params: { language: 'auto' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'text-summarizer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'text', formats: '["txt"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { audio: '/path/to/meeting.wav' },
        },
        {
            id: 'image-stylize-upscale',
            name: { en: 'Generate → Stylize → Upscale → Export', zh: '生成 → 风格化 → 放大 → 导出' },
            icon: '🎭',
            description: {
                en: 'Generate an image, apply artistic style transfer, upscale, and export.',
                zh: '生成图片后进行风格迁移，放大分辨率，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'stylizer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'upscaler', label: '',
                    params: {},
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'image', formats: '["png"]' },
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { prompt: 'a serene lake at dawn, mist rising from the water' },
        },
    ];

    function getAll() {
        return _templates.map(t => ({
            id: t.id,
            name: I18n.getLang() === 'zh' ? t.name.zh : t.name.en,
            description: I18n.getLang() === 'zh' ? t.description.zh : t.description.en,
            icon: t.icon,
            node_count: t.nodes.length,
            edge_count: t.edges.length,
        }));
    }

    function getGraph(templateId) {
        const tmpl = _templates.find(t => t.id === templateId);
        if (!tmpl) return null;

        // Regenerate IDs to avoid collisions with existing nodes
        const idMap = {};
        tmpl.nodes.forEach((n, i) => {
            idMap[n.id] = `n${Date.now()}${i}`;
        });

        const nodes = tmpl.nodes.map(n => ({
            id: idMap[n.id],
            type: n.type,
            x: n.x,
            y: n.y,
            params: { ...n.params },
            input_params: { ...(n.input_params || {}) },
            label: I18n.nodeName(n.type),
        }));

        const edges = tmpl.edges.map((e, i) => ({
            id: `e${Date.now()}${i}`,
            source: idMap[e.source],
            target: idMap[e.target],
        }));

        return {
            name: I18n.getLang() === 'zh' ? tmpl.name.zh : tmpl.name.en,
            nodes,
            edges,
            input: { data: { ...tmpl.input } },
        };
    }

    return { getAll, getGraph };
})();
