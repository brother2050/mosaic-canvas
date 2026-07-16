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
            input: { text: '你好，欢迎使用 Mosaic 数字人系统。', avatar: '/path/to/avatar.png' },
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
