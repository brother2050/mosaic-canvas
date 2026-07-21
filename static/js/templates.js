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
                    input_params: { num_inference_steps: '25', guidance_scale: '7.5', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
                    input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'upscaler', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
                    input_params: { strength: '0.65', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'stylizer', label: '',
                    params: {},
                    input_params: { style: 'oil painting', strength: '0.65' },
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            name: { en: 'TTS → Lip Sync → Render → Encode', zh: '语音合成 → 唇形同步 → 渲染 → 编码' },
            icon: '🧑',
            description: {
                en: 'Generate speech from text, sync lips to a face, render a digital human, then encode as MP4.',
                zh: '从文本生成语音，进行唇形同步，渲染数字人，然后编码为 MP4。',
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
            input: { text: '你好，欢迎使用 Mosaic 数字人系统。', face_image: '/path/to/avatar.png' },
        },
        {
            id: 'video-subtitle-export',
            name: { en: 'Audio → Subtitles → Export', zh: '音频 → 字幕 → 导出' },
            icon: '📝',
            description: {
                en: 'Transcribe audio to text segments, map segments→data, then export as subtitles.',
                zh: '将音频转录为文本片段，字段映射 segments→data，然后导出为字幕。',
            },
            nodes: [
                {
                    id: 'n1', type: 'asr', label: '',
                    params: {},
                    input_params: { language: 'auto' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"segments": "data"}', drop_fields: '[]' },
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
                    input_params: { strength: '0.85', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            input: { prompt: 'a red sports car', image: '/path/to/input.jpg', mask_image: '/path/to/mask.png' },
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
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"audio": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'audio', formats: '["wav", "mp3"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'upbeat electronic music with a catchy melody, 120 BPM' },
        },
        {
            id: 'chat-fieldmapper-text-to-image',
            name: { en: 'Chat → Map → Image → Map → Export', zh: '对话 → 映射 → 文生图 → 映射 → 导出' },
            icon: '💬',
            description: {
                en: 'Chat generates text, field-mapper renames reply→prompt, generate image, second field-mapper renames image→data, then export.',
                zh: '对话节点生成文本，第一个字段映射将 reply 重命名为 prompt，生成图片，第二个字段映射将 image 重命名为 data，最后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'chat', label: '',
                    params: {},
                    input_params: {
                        system_prompt: 'You are a professional Stable Diffusion prompt engineer. Enhance the user\'s description into a detailed English prompt. Always append quality boosters (masterpiece, best quality, 8k, ultra-detailed), add relevant lighting/camera/style keywords, and suggest a negative prompt when beneficial. Output ONLY the English prompt, no explanations.',
                    },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"reply": "prompt"}', drop_fields: '["messages"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'text-to-image', label: '',
                    params: { model: 'stabilityai/sdxl-turbo' },
                    input_params: { num_inference_steps: '25', guidance_scale: '7.5', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            input: { messages: '[{"role":"user","content":"A beautiful sunset over the mountains, golden light, serene landscape"}]' },
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
                en: 'Transcribe audio, translate subtitles, map subtitles→data, then export.',
                zh: '转录音频，翻译字幕，字段映射 subtitles→data，然后导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'asr', label: '',
                    params: {},
                    input_params: { language: 'auto' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'subtitle-translator', label: '',
                    params: {},
                    input_params: { target_language: 'en' },
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'field-mapper', label: '',
                    params: { mapping: '{"subtitles": "data"}', drop_fields: '[]' },
                    input_params: {},
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
                    input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'background-remover', label: '',
                    params: {},
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            input: { prompt: 'a product photo of a red sneaker on white background' },
        },
        {
            id: 'prompt-expand-image-upscale',
            name: { en: 'Expand Prompt → Map → Image → Upscale → Export', zh: '提示词扩展 → 映射 → 文生图 → 放大 → 导出' },
            icon: '🔍',
            description: {
                en: 'Expand a short prompt, map text→prompt, generate image, upscale, and export.',
                zh: '将简短提示词扩展为详细描述，字段映射将 text 重命名为 prompt，生成图片，放大，然后导出。',
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
                    input_params: { num_inference_steps: '30', guidance_scale: '7.5', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
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
                    id: 'n3', type: 'field-mapper', label: '',
                    params: { mapping: '{"summary": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["txt"]' },
                    ...pos(3, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
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
                    input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'stylizer', label: '',
                    params: {},
                    input_params: { style: 'anime', strength: '0.7' },
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'upscaler', label: '',
                    params: {},
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            input: { prompt: 'a serene lake at dawn, mist rising from the water' },
        },
        // ════════════════════════════════════════════════════════════
        // Templates derived from Mosaic framework examples (examples/*.py)
        // Each template corresponds to a pipeline combination from the
        // official example files.
        // ════════════════════════════════════════════════════════════

        // ── 01_text_domain.py ──
        {
            id: 'ex01-text-gen-translate-summarize',
            name: { en: 'Text → Translate → Summarize', zh: '文本生成 → 翻译 → 摘要' },
            icon: '📝',
            description: {
                en: 'Generate text, translate it, then summarize (example 01).',
                zh: '生成文本后翻译，再生成摘要（示例01）。',
            },
            nodes: [
                { id: 'n1', type: 'text-generator', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'translator', label: '', params: {}, input_params: { target_language: 'en' }, ...pos(1, 0) },
                { id: 'n3', type: 'text-summarizer', label: '', params: {}, input_params: {}, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'Write a short article about artificial intelligence in healthcare' },
        },
        {
            id: 'ex01-text-rewriter',
            name: { en: 'Text Rewriter', zh: '文本改写' },
            icon: '✏️',
            description: { en: 'Rewrite text with a different style, then export as text (example 01).', zh: '以不同风格改写文本后导出为文本（示例01）。' },
            nodes: [
                { id: 'n1', type: 'text-rewriter', label: '', params: {}, input_params: { instruction: 'Rewrite in a formal style' }, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"text": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'The weather is nice today so lets go outside and play.' },
        },
        {
            id: 'ex01-text-classifier',
            name: { en: 'Chat → Classify', zh: '对话 → 分类' },
            icon: '🏷️',
            description: { en: 'Generate text via chat, then classify into categories (example 01).', zh: '通过对话生成文本后分类到指定类别（示例01）。' },
            nodes: [
                { id: 'n1', type: 'chat', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'text-classifier', label: '', params: {}, input_params: { labels: '["positive", "negative", "neutral"]' }, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'Tell me about a product you recently bought and loved.' },
        },

        // ── 02_image_domain.py ──
        {
            id: 'ex02-image-to-image',
            name: { en: 'Generate → Image to Image', zh: '文生图 → 图生图' },
            icon: '🖼️',
            description: { en: 'Generate an image, then transform it with a prompt (example 02).', zh: '生成图片后用提示词进行变换（示例02）。' },
            nodes: [
                { id: 'n1', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(0, 0) },
                { id: 'n2', type: 'image-to-image', label: '', params: { model: 'timbrooks/instruct-pix2pix' }, input_params: { strength: '0.8', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"image": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'image', formats: '["png"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { prompt: 'make it look like a watercolor painting' },
        },
        {
            id: 'ex02-inpainting',
            name: { en: 'Generate → Inpainting', zh: '文生图 → 图像修复' },
            icon: '🎨',
            description: { en: 'Generate an image, then fill masked regions (example 02).', zh: '生成图片后填充遮罩区域（示例02）。' },
            nodes: [
                { id: 'n1', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(0, 0) },
                { id: 'n2', type: 'inpainting', label: '', params: { model: 'runwayml/stable-diffusion-inpainting' }, input_params: { strength: '1.0', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"image": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'image', formats: '["png"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { mask_image: '/path/to/mask.png', prompt: 'a red sports car' },
        },

        // ── 03/20_video_domain.py ──
        {
            id: 'ex03-wan-video-encode',
            name: { en: 'WanVideo → Encode', zh: 'Wan视频 → 编码' },
            icon: '🎬',
            description: { en: 'Generate video with WanVideo, then encode as MP4 (example 03).', zh: '用 WanVideo 生成视频后编码为 MP4（示例03）。' },
            nodes: [
                { id: 'n1', type: 'wan-video', label: '', params: {}, input_params: { num_frames: '49', width: '832', height: '480' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: { fps: '16' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { prompt: 'a cat playing with a ball of yarn, slow motion' },
        },
        {
            id: 'ex03-hunyuan-video-encode',
            name: { en: 'HunyuanVideo → Encode', zh: '腾讯混元视频 → 编码' },
            icon: '🎬',
            description: { en: 'Generate video with HunyuanVideo, then encode (example 03).', zh: '用 HunyuanVideo 生成视频后编码（示例03）。' },
            nodes: [
                { id: 'n1', type: 'hunyuan-video', label: '', params: {}, input_params: { num_frames: '49' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { prompt: 'waves crashing on a rocky shore at sunset' },
        },
        {
            id: 'ex03-ltx-video-encode',
            name: { en: 'LTXVideo → Encode', zh: 'LTX视频 → 编码' },
            icon: '🎬',
            description: { en: 'Generate video with LTXVideo, then encode (example 03).', zh: '用 LTXVideo 生成视频后编码（示例03）。' },
            nodes: [
                { id: 'n1', type: 'ltx-video', label: '', params: {}, input_params: { num_frames: '33' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { prompt: 'a drone flying over a snowy mountain range' },
        },
        {
            id: 'ex03-image-to-video',
            name: { en: 'Image to Video', zh: '图生视频' },
            icon: '🎞️',
            description: { en: 'Animate a static image into a video (example 03).', zh: '将静态图片生成为视频（示例03）。' },
            nodes: [
                { id: 'n1', type: 'image-to-video', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { image: '/path/to/image.png', prompt: 'camera slowly zooming in' },
        },
        {
            id: 'ex03-video-continuation',
            name: { en: 'Video Continuation', zh: '视频续写' },
            icon: '▶️',
            description: { en: 'Continue an existing video with more frames (example 03).', zh: '为已有视频生成后续帧（示例03）。' },
            nodes: [
                { id: 'n1', type: 'video-continuation', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { video: '/path/to/video.mp4', prompt: 'the scene continues with more action' },
        },
        {
            id: 'ex03-frame-extractor',
            name: { en: 'Video → Frame Extractor', zh: '视频 → 帧提取' },
            icon: '🖼️',
            description: { en: 'Generate a video, then extract frames (example 03).', zh: '生成视频后提取帧（示例03）。' },
            nodes: [
                { id: 'n1', type: 'text-to-video', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(0, 0) },
                { id: 'n2', type: 'frame-extractor', label: '', params: {}, input_params: { mode: 'interval', interval: '2' }, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'image', formats: '["png"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'a cat playing with a ball of yarn, slow motion' },
        },

        // ── 04_audio_domain.py ──
        {
            id: 'ex04-voice-clone',
            name: { en: 'TTS → Voice Clone', zh: '语音合成 → 声音克隆' },
            icon: '🗣️',
            description: { en: 'Generate speech with TTS, then clone the voice (example 04).', zh: '用 TTS 生成语音后克隆声音（示例04）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'chattts' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'voice-clone', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { reference_audio: '/path/to/reference.wav', text: 'Hello, this is my cloned voice speaking.' },
        },
        {
            id: 'ex04-sound-effect',
            name: { en: 'Sound Effect Generator', zh: '音效生成' },
            icon: '🔊',
            description: { en: 'Generate sound effects from a prompt (example 04).', zh: '从提示词生成音效（示例04）。' },
            nodes: [
                { id: 'n1', type: 'sound-effect-generator', label: '', params: {}, input_params: { duration: '5' }, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'thunder rumbling in the distance' },
        },
        {
            id: 'ex04-asr-summarize',
            name: { en: 'Audio → Transcribe → Summarize', zh: '音频 → 转录 → 摘要' },
            icon: '📋',
            description: { en: 'Transcribe audio then summarize the transcript (example 04).', zh: '转录音频后对文本生成摘要（示例04）。' },
            nodes: [
                { id: 'n1', type: 'asr', label: '', params: {}, input_params: { language: 'auto' }, ...pos(0, 0) },
                { id: 'n2', type: 'text-summarizer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { audio: '/path/to/audio.wav' },
        },

        // ── 05-08 TTS backends ──
        {
            id: 'ex05-tts-chattts',
            name: { en: 'TTS (ChatTTS) → Export', zh: '语音合成 (ChatTTS) → 导出' },
            icon: '💬',
            description: { en: 'Text-to-speech using ChatTTS backend, then export as audio (example 05).', zh: '使用 ChatTTS 后端的语音合成后导出音频（示例05）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'chattts' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Hello world, this is a text to speech demo using ChatTTS.' },
        },
        {
            id: 'ex06-tts-fish-speech',
            name: { en: 'TTS (Fish Speech) → Export', zh: '语音合成 (Fish Speech) → 导出' },
            icon: '🐟',
            description: { en: 'Text-to-speech using Fish Speech backend, then export as audio (example 06).', zh: '使用 Fish Speech 后端的语音合成后导出音频（示例06）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'fish' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Hello world, this is a text to speech demo using Fish Speech.' },
        },
        {
            id: 'ex07-tts-gpt-sovits',
            name: { en: 'TTS (GPT-SoVITS) → Export', zh: '语音合成 (GPT-SoVITS) → 导出' },
            icon: '🎵',
            description: { en: 'Text-to-speech using GPT-SoVITS backend, then export as audio (example 07).', zh: '使用 GPT-SoVITS 后端的语音合成后导出音频（示例07）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'sovits' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Hello world, this is a text to speech demo using GPT-SoVITS.' },
        },
        {
            id: 'ex08-tts-cosyvoice',
            name: { en: 'TTS (CosyVoice) → Export', zh: '语音合成 (CosyVoice) → 导出' },
            icon: '🌧️',
            description: { en: 'Text-to-speech using CosyVoice backend, then export as audio (example 08).', zh: '使用 CosyVoice 后端的语音合成后导出音频（示例08）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'cosyvoice' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"audio": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'audio', formats: '["wav"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Hello world, this is a text to speech demo using CosyVoice.' },
        },

        // ── 09_subtitle_rag.py / 21_subtitle_domain.py / 23_rag_domain.py ──
        {
            id: 'ex09-subtitle-gen-translate',
            name: { en: 'Subtitle Generate → Translate', zh: '字幕生成 → 翻译' },
            icon: '📢',
            description: { en: 'Generate subtitles then translate them (example 09).', zh: '生成字幕后翻译（示例09）。' },
            nodes: [
                { id: 'n1', type: 'subtitle-generator', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'subtitle-translator', label: '', params: {}, input_params: { target_language: 'en' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { audio: '/path/to/audio.wav' },
        },
        {
            id: 'ex09-subtitle-gen-translate-align',
            name: { en: 'Subtitle Gen → Translate → Align', zh: '字幕生成 → 翻译 → 对齐' },
            icon: '🔗',
            description: { en: 'Generate, translate, and align subtitles (example 09).', zh: '生成、翻译并对齐字幕（示例09）。' },
            nodes: [
                { id: 'n1', type: 'subtitle-generator', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'subtitle-translator', label: '', params: {}, input_params: { target_language: 'en' }, ...pos(1, 0) },
                { id: 'n3', type: 'subtitle-aligner', label: '', params: {}, input_params: {}, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { audio: '/path/to/audio.wav' },
        },
        {
            id: 'ex09-rag-with-generator',
            name: { en: 'RAG: Parse → Index → Retrieve → Generate → Cite', zh: 'RAG: 解析 → 索引 → 检索 → 生成 → 引用' },
            icon: '📚',
            description: {
                en: 'Complete RAG with answer generation and citations (example 09).',
                zh: '完整 RAG 流程，包含答案生成和引用（示例09）。',
            },
            nodes: [
                { id: 'n1', type: 'document-parser', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'vector-indexer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'retriever', label: '', params: {}, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'text-generator', label: '', params: {}, input_params: {}, ...pos(3, 0) },
                { id: 'n5', type: 'citation-generator', label: '', params: {}, input_params: {}, ...pos(4, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
            ],
            input: { file_path: '/path/to/document.pdf', query: 'What are the main conclusions?' },
        },
        {
            id: 'ex09-video-content-qa',
            name: { en: 'Video Content QA (6 nodes)', zh: '视频内容问答（6节点）' },
            icon: '❓',
            description: {
                en: 'Transcribe video audio, generate subtitles, index, retrieve, generate answer with citations (example 09).',
                zh: '转录视频音频，生成字幕，索引、检索、生成带引用的回答（示例09）。',
            },
            nodes: [
                { id: 'n1', type: 'asr', label: '', params: {}, input_params: { language: 'auto' }, ...pos(0, 0) },
                { id: 'n2', type: 'subtitle-generator', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'vector-indexer', label: '', params: {}, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'retriever', label: '', params: {}, input_params: {}, ...pos(3, 0) },
                { id: 'n5', type: 'text-generator', label: '', params: {}, input_params: {}, ...pos(4, 0) },
                { id: 'n6', type: 'citation-generator', label: '', params: {}, input_params: {}, ...pos(5, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
                { id: 'e5', source: 'n5', target: 'n6' },
            ],
            input: { audio: '/path/to/video_audio.wav', query: 'What is discussed in this video?' },
        },

        // ── 10_digital_human.py ──
        {
            id: 'ex10-avatar-lipsync',
            name: { en: 'Avatar Drive → Lip Sync', zh: '虚拟人驱动 → 唇形同步' },
            icon: '🧑',
            description: { en: 'Drive an avatar then apply lip sync (example 10).', zh: '驱动虚拟人后进行唇形同步（示例10）。' },
            nodes: [
                { id: 'n1', type: 'avatar-driver', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'lip-syncer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { source_image: '/path/to/avatar.png', driving_audio: '/path/to/audio.wav' },
        },
        {
            id: 'ex10-tts-lipsync-encode',
            name: { en: 'TTS → Lip Sync → Encode', zh: '语音合成 → 唇形同步 → 编码' },
            icon: '🎬',
            description: { en: 'Generate speech, lip sync to avatar, then encode video (example 10).', zh: '生成语音后进行唇形同步，再编码视频（示例10）。' },
            nodes: [
                { id: 'n1', type: 'tts', label: '', params: { backend: 'chattts' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'lip-syncer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Hello, I am a digital human. Nice to meet you!', face_image: '/path/to/avatar.png' },
        },
        {
            id: 'ex10-motion-avatar',
            name: { en: 'Motion → Avatar Drive', zh: '动作生成 → 虚拟人驱动' },
            icon: '💃',
            description: { en: 'Generate motion data then drive an avatar (example 10).', zh: '生成动作数据后驱动虚拟人（示例10）。' },
            nodes: [
                { id: 'n1', type: 'motion-generator', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'avatar-driver', label: '', params: {}, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { prompt: 'a person waving their hand', face_image: '/path/to/avatar.png' },
        },

        // ── 11_cross_domain_pipeline.py ──
        {
            id: 'ex11-text-image-video-export',
            name: { en: 'Text → Map → Image → Upscale → Video → Export', zh: '文本 → 映射 → 图像 → 放大 → 视频 → 导出' },
            icon: '🏭',
            description: {
                en: 'Full cross-domain chain: generate text, map text→prompt, generate image, upscale, animate, export (example 11).',
                zh: '完整跨域链路：生成文本、字段映射 text→prompt、生成图像、放大、生成视频、导出（示例11）。',
            },
            nodes: [
                { id: 'n1', type: 'text-generator', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"text": "prompt"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(2, 0) },
                { id: 'n4', type: 'upscaler', label: '', params: {}, input_params: { scale_factor: '2' }, ...pos(3, 0) },
                { id: 'n5', type: 'wan-video', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(4, 0) },
                { id: 'n6', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'video', formats: '["mp4"]' }, ...pos(5, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
                { id: 'e5', source: 'n5', target: 'n6' },
            ],
            input: { prompt: 'a majestic castle on a hilltop at golden hour' },
        },
        {
            id: 'ex11-digital-human-creation',
            name: { en: 'Create Digital Human', zh: '创建数字人' },
            icon: '🤖',
            description: {
                en: 'Generate avatar image, TTS, map image→face_image, lip sync (merge image+audio), then encode (example 11).',
                zh: '生成虚拟人形象、语音合成，字段映射将 image 重命名为 face_image，唇形同步（合并图像与音频）后编码（示例11）。',
            },
            nodes: [
                { id: 'n1', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(0, 0) },
                { id: 'n2', type: 'tts', label: '', params: { backend: 'chattts' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"image": "face_image"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'lip-syncer', label: '', params: {}, input_params: {}, ...pos(3, 0) },
                { id: 'n5', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(4, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n3' },
                { id: 'e2', source: 'n2', target: 'n4' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
            ],
            input: { prompt: 'a professional headshot of a friendly news anchor', text: 'Welcome to today\'s news broadcast.' },
        },
        {
            id: 'ex11-document-qa-simple',
            name: { en: 'Document QA (Simple)', zh: '文档问答（简易版）' },
            icon: '📄',
            description: { en: 'Parse, index, retrieve, and generate citations (example 11).', zh: '解析、索引、检索并生成引用（示例11）。' },
            nodes: [
                { id: 'n1', type: 'document-parser', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'vector-indexer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'retriever', label: '', params: {}, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'citation-generator', label: '', params: {}, input_params: {}, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { file_path: '/path/to/report.pdf', query: 'What is the revenue growth?' },
        },
        {
            id: 'ex11-dubbing-pipeline',
            name: { en: 'Video Dubbing Pipeline', zh: '视频配音流程' },
            icon: '🎙️',
            description: {
                en: 'Generate video, TTS, subtitles, align, and encode (example 11).',
                zh: '生成视频、语音合成、字幕、对齐后编码（示例11）。',
            },
            nodes: [
                { id: 'n1', type: 'wan-video', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(0, 0) },
                { id: 'n2', type: 'tts', label: '', params: { backend: 'chattts' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'subtitle-generator', label: '', params: {}, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'subtitle-aligner', label: '', params: {}, input_params: {}, ...pos(3, 0) },
                { id: 'n5', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(4, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n5' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
                { id: 'e4', source: 'n4', target: 'n5' },
            ],
            input: { prompt: 'a nature documentary scene', text: 'In this video, we explore the wonders of the ocean.' },
        },

        // ── 12_consistency_domain.py ──
        {
            id: 'ex12-identity-keeper',
            name: { en: 'Generate → Identity Keeper', zh: '文生图 → 身份保持' },
            icon: '🔐',
            description: { en: 'Generate an image, then preserve character identity (example 12).', zh: '生成图片后保持角色身份（示例12）。' },
            nodes: [
                { id: 'n1', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(0, 0) },
                { id: 'n2', type: 'identity-keeper', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"image": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'image', formats: '["png"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { image: '/path/to/character.png', prompt: 'the character in a spacesuit on Mars' },
        },
        {
            id: 'ex12-style-keeper',
            name: { en: 'Generate → Style Keeper', zh: '文生图 → 风格保持' },
            icon: '🎭',
            description: { en: 'Generate an image, then preserve artistic style (example 12).', zh: '生成图片后保持艺术风格（示例12）。' },
            nodes: [
                { id: 'n1', type: 'text-to-image', label: '', params: { model: 'stabilityai/sdxl-turbo' }, input_params: { num_inference_steps: '25', negative_prompt: 'blurry, low quality, distorted, deformed, watermark, text' }, ...pos(0, 0) },
                { id: 'n2', type: 'style-keeper', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"image": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'image', formats: '["png"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { image: '/path/to/style_reference.png', prompt: 'a mountain landscape in this style' },
        },
        {
            id: 'ex12-cross-frame-consistency',
            name: { en: 'Video → Cross-Frame Consistency', zh: '视频 → 跨帧一致性' },
            icon: '🎞️',
            description: { en: 'Generate a video, then apply cross-frame consistency (example 12).', zh: '生成视频后应用跨帧一致性（示例12）。' },
            nodes: [
                { id: 'n1', type: 'text-to-video', label: '', params: {}, input_params: { num_frames: '25' }, ...pos(0, 0) },
                { id: 'n2', type: 'cross-frame-consistency', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'field-mapper', label: '', params: { mapping: '{"video": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(2, 0) },
                { id: 'n4', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'video', formats: '["mp4"]' }, ...pos(3, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
                { id: 'e3', source: 'n3', target: 'n4' },
            ],
            input: { prompt: 'maintain consistent character appearance' },
        },

        // ── 13/22_export_domain.py ──
        {
            id: 'ex13-livestream',
            name: { en: 'Livestream', zh: '直播推流' },
            icon: '📡',
            description: { en: 'Extract frames from video, then stream to RTMP/SRT endpoint (example 13).', zh: '从视频提取帧，然后推流到 RTMP/SRT 地址（示例13）。' },
            nodes: [
                { id: 'n1', type: 'frame-extractor', label: '', params: {}, input_params: { mode: 'interval', interval: '1' }, ...pos(0, 0) },
                { id: 'n2', type: 'livestreamer', label: '', params: {}, input_params: { stream_url: 'rtmp://localhost/live/stream' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { video: '/path/to/video.mp4' },
        },
        {
            id: 'ex13-video-encode-subtitle',
            name: { en: 'Video Encode with Subtitle', zh: '带字幕视频编码' },
            icon: '🎬',
            description: { en: 'Extract frames, encode video with subtitle overlay (example 13).', zh: '提取帧，编码带字幕叠加的视频（示例13）。' },
            nodes: [
                { id: 'n1', type: 'frame-extractor', label: '', params: {}, input_params: { mode: 'interval', interval: '1' }, ...pos(0, 0) },
                { id: 'n2', type: 'video-encoder', label: '', params: { format: 'mp4' }, input_params: {}, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { video: '/path/to/video.mp4', subtitle: '/path/to/subtitles.srt' },
        },
        // ── Helper nodes: data manipulation ──
        {
            id: 'data-merge-export',
            name: { en: 'Data Merge → Export', zh: '数据合并 → 导出' },
            icon: '🔀',
            description: {
                en: 'Merge data from multiple sources and export as text.',
                zh: '合并多个数据源并导出为文本。',
            },
            nodes: [
                { id: 'n1', type: 'data-merger', label: '', params: { merge_keys: '["field1", "field2"]' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"merged": "data"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { data: '{"key": "value"}' },
        },
        {
            id: 'json-parse-transform-export',
            name: { en: 'JSON Parse → Transform → Export', zh: 'JSON解析 → 转换 → 导出' },
            icon: '📋',
            description: {
                en: 'Parse JSON, apply field mapping, and export.',
                zh: '解析 JSON，应用字段映射，然后导出。',
            },
            nodes: [
                { id: 'n1', type: 'json-parser', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'field-mapper', label: '', params: { mapping: '{"old_field": "new_field"}', drop_fields: '[]' }, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }, { id: 'e2', source: 'n2', target: 'n3' }],
            input: { text: '{"name": "Alice", "age": 30, "city": "Beijing"}' },
        },
        // ── Helper nodes: file I/O ──
        {
            id: 'file-read-process-write',
            name: { en: 'Read → Process → Write', zh: '读取 → 处理 → 写入' },
            icon: '📁',
            description: {
                en: 'Read a file, process its content, and write the result.',
                zh: '读取文件，处理内容，然后写入结果。',
            },
            nodes: [
                { id: 'n1', type: 'file-reader', label: '', params: {}, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'text-summarizer', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'file-writer', label: '', params: {}, input_params: { format: 'txt' }, ...pos(2, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }, { id: 'e2', source: 'n2', target: 'n3' }],
            input: { file_path: '/path/to/input.txt' },
        },
        // ── Helper nodes: API integration ──
        {
            id: 'api-call-export',
            name: { en: 'API Call → Export', zh: 'API调用 → 导出' },
            icon: '🌐',
            description: {
                en: 'Call an external API and export the response.',
                zh: '调用外部 API 并导出响应结果。',
            },
            nodes: [
                { id: 'n1', type: 'api-caller', label: '', params: { method: 'GET', url: 'https://api.example.com/data', headers: '{"Accept": "application/json"}' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: {},
        },
        // ── Helper nodes: data validation ──
        {
            id: 'schema-validate-export',
            name: { en: 'Schema Validate → Export', zh: '数据校验 → 导出' },
            icon: '✅',
            description: {
                en: 'Validate data against a schema and export valid records.',
                zh: '根据 schema 校验数据并导出有效记录。',
            },
            nodes: [
                { id: 'n1', type: 'schema-validator', label: '', params: { schema: '{"type": "object", "properties": {"name": {"type": "string"}}}' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { data: '{"name": "Alice"}' },
        },
        // ── Helper nodes: control flow ──
        {
            id: 'conditional-switch-export',
            name: { en: 'Switch → Export', zh: '条件分支 → 导出' },
            icon: '🔀',
            description: {
                en: 'Route data through conditional branches and export results.',
                zh: '通过条件分支路由数据并导出结果。',
            },
            nodes: [
                { id: 'n1', type: 'switch', label: '', params: { conditions: '[{"field": "type", "op": "eq", "value": "image"}]' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { data: '{"type": "image", "content": "..."}' },
        },
        // ── Helper nodes: caching ──
        {
            id: 'cache-store-retrieve',
            name: { en: 'Cache Store → Retrieve', zh: '缓存存储 → 检索' },
            icon: '💾',
            description: {
                en: 'Store results in cache and retrieve them later.',
                zh: '将结果存入缓存，供后续检索使用。',
            },
            nodes: [
                { id: 'n1', type: 'result-cache', label: '', params: { cache_keys: '["prompt", "model"]' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(1, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }],
            input: { prompt: 'test prompt', model: 'test-model' },
        },
        // ── Helper nodes: text processing chain ──
        {
            id: 'text-chunk-classify-export',
            name: { en: 'Chunk → Classify → Export', zh: '分块 → 分类 → 导出' },
            icon: '📝',
            description: {
                en: 'Split text into chunks, classify each chunk, and export.',
                zh: '将文本分块，对每个块进行分类，然后导出。',
            },
            nodes: [
                { id: 'n1', type: 'text-chunker', label: '', params: { strategy: 'sentence', chunk_size: '500' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'text-classifier', label: '', params: {}, input_params: { labels: '["important", "trivial", "reference"]' }, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }, { id: 'e2', source: 'n2', target: 'n3' }],
            input: { text: 'A long document that needs to be chunked and classified...' },
        },
        // ── Helper nodes: monitoring & debugging ──
        {
            id: 'log-debug-export',
            name: { en: 'Log → Debug → Export', zh: '日志 → 调试 → 导出' },
            icon: '🐛',
            description: {
                en: 'Log data flow, add debug checkpoint, and export for inspection.',
                zh: '记录数据流，添加调试检查点，导出供检查。',
            },
            nodes: [
                { id: 'n1', type: 'logger', label: '', params: { level: 'info' }, input_params: {}, ...pos(0, 0) },
                { id: 'n2', type: 'debugger', label: '', params: {}, input_params: {}, ...pos(1, 0) },
                { id: 'n3', type: 'multi-format-exporter', label: '', params: {}, input_params: { content_type: 'subtitle', formats: '["txt"]' }, ...pos(2, 0) },
            ],
            edges: [{ id: 'e1', source: 'n1', target: 'n2' }, { id: 'e2', source: 'n2', target: 'n3' }],
            input: { data: '{"message": "debug test"}' },
        },
        // ── 中文提示词转英文模板 ──
        {
            id: 'zh-to-en-prompt-image',
            name: { en: 'CN Prompt → EN → Image', zh: '中文提示词转英文 → 生图' },
            icon: '🔄',
            description: {
                en: 'Translate Chinese prompts to English SD prompts, then generate image.',
                zh: '将中文提示词转为适合SD的英文提示词，然后生成图片。',
            },
            nodes: [
                {
                    id: 'n1', type: 'chat', label: '',
                    params: {},
                    input_params: {
                        system_prompt: 'You are a professional Stable Diffusion prompt engineer. Translate the user\'s Chinese text into an English prompt. Always append quality boosters (masterpiece, best quality, 8k, ultra-detailed), add relevant lighting/camera/style keywords, and suggest a negative prompt when beneficial. Output ONLY the English prompt, no explanations.',
                    },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"reply": "prompt"}', drop_fields: '["messages"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'text-to-image', label: '',
                    params: {},
                    input_params: {},
                    ...pos(2, 0),
                },
                {
                    id: 'n4', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
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
            input: { messages: '[{"role":"user","content":"一个漂亮的女孩在花园里散步，阳光明媚"}]' },
        },
        // ── 文本翻译导出模板 ──
        {
            id: 'translate-export',
            name: { en: 'Translate → Export', zh: '翻译 → 导出' },
            icon: '🌐',
            description: {
                en: 'Translate text to another language and export.',
                zh: '将文本翻译为另一种语言并导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'translator', label: '',
                    params: {},
                    input_params: { target_language: 'en' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"translated_text": "data"}', drop_fields: '["source_language", "target_language"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["txt"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: '今天天气真好，适合出去散步。' },
        },
        // ── 文本摘要导出模板 ──
        {
            id: 'summarize-export',
            name: { en: 'Summarize → Export', zh: '摘要 → 导出' },
            icon: '📝',
            description: {
                en: 'Summarize long text and export the summary.',
                zh: '对长文本进行摘要并导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-summarizer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"summary": "data"}', drop_fields: '["original_length", "summary_length", "compression_ratio"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["txt"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'Artificial intelligence (AI) is intelligence demonstrated by machines, in contrast to the natural intelligence displayed by humans and animals. Leading AI textbooks define the field as the study of "intelligent agents": any device that perceives its environment and takes actions that maximize its chance of successfully achieving its goals.' },
        },
        // ── 文本分类导出模板 ──
        {
            id: 'classify-export',
            name: { en: 'Classify → Export', zh: '分类 → 导出' },
            icon: '🏷️',
            description: {
                en: 'Classify text into categories and export results.',
                zh: '对文本进行分类并导出结果。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-classifier', label: '',
                    params: {},
                    input_params: { labels: '["positive", "negative", "neutral"]' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"classification": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["txt"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: 'This product is amazing! The quality exceeds my expectations.', labels: '["positive", "negative", "neutral"]' },
        },
        // ── 语音合成导出模板 ──
        {
            id: 'tts-export',
            name: { en: 'TTS → Export', zh: '语音合成 → 导出' },
            icon: '🔊',
            description: {
                en: 'Convert text to speech and export audio.',
                zh: '将文本转为语音并导出音频。',
            },
            nodes: [
                {
                    id: 'n1', type: 'tts', label: '',
                    params: {},
                    input_params: { language: 'zh', emotion: 'neutral' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"audio": "data"}', drop_fields: '["text", "duration"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'audio', formats: '["wav", "mp3"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { text: '你好，欢迎使用语音合成功能。' },
        },
        // ── 文生视频导出模板 ──
        {
            id: 'text-to-video-export',
            name: { en: 'Text → Video → Export', zh: '文生视频 → 导出' },
            icon: '🎬',
            description: {
                en: 'Generate video from text and export.',
                zh: '从文字生成视频并导出。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-to-video', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"video": "data"}', drop_fields: '["frames", "fps", "prompt", "seed", "num_frames", "duration"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
                {
                    id: 'n3', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'video', formats: '["mp4"]' },
                    ...pos(2, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
                { id: 'e2', source: 'n2', target: 'n3' },
            ],
            input: { prompt: 'A cat playing in a garden, cinematic, 4K' },
        },
        // ── 前缀模板：对话 → 映射（可接任意下游节点）──
        {
            id: 'prefix-chat-mapper',
            name: { en: 'Chat → Mapper (Prefix)', zh: '对话 → 映射（前缀）' },
            icon: '🔗',
            description: {
                en: 'Use chat to generate content, then map reply to prompt. Connect any downstream node.',
                zh: '用对话生成内容，将 reply 映射为 prompt。可接任意下游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'chat', label: '',
                    params: {},
                    input_params: {
                        system_prompt: 'You are a professional Stable Diffusion prompt engineer. Translate the user\'s Chinese text into an English prompt. Always append quality boosters (masterpiece, best quality, 8k, ultra-detailed), add relevant lighting/camera/style keywords, and suggest a negative prompt when beneficial. Output ONLY the English prompt, no explanations.',
                    },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"reply": "prompt"}', drop_fields: '["messages"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { messages: '[{"role":"user","content":"一只可爱的猫咪坐在窗台上"}]' },
        },
        // ── 前缀模板：翻译 → 映射 ──
        {
            id: 'prefix-translate-mapper',
            name: { en: 'Translate → Mapper (Prefix)', zh: '翻译 → 映射（前缀）' },
            icon: '🌐',
            description: {
                en: 'Translate text, then map translated_text to prompt. Connect any downstream node.',
                zh: '翻译文本，将 translated_text 映射为 prompt。可接任意下游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'translator', label: '',
                    params: {},
                    input_params: { target_language: 'en' },
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"translated_text": "prompt"}', drop_fields: '["source_language", "target_language"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { text: '今天天气真好，适合出去散步。' },
        },
        // ── 前缀模板：摘要 → 映射 ──
        {
            id: 'prefix-summarize-mapper',
            name: { en: 'Summarize → Mapper (Prefix)', zh: '摘要 → 映射（前缀）' },
            icon: '📝',
            description: {
                en: 'Summarize text, then map summary to prompt. Connect any downstream node.',
                zh: '摘要文本，将 summary 映射为 prompt。可接任意下游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'text-summarizer', label: '',
                    params: {},
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'field-mapper', label: '',
                    params: { mapping: '{"summary": "prompt"}', drop_fields: '["original_length", "summary_length", "compression_ratio"]' },
                    input_params: {},
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: { text: 'Artificial intelligence is intelligence demonstrated by machines, in contrast to natural intelligence displayed by humans. Leading AI textbooks define the field as the study of intelligent agents.' },
        },
        // ── 后缀模板：映射 → 导出（图像）──
        {
            id: 'suffix-mapper-export-image',
            name: { en: 'Mapper → Export (Image)', zh: '映射 → 导出（图像）' },
            icon: '🖼️',
            description: {
                en: 'Map image field to data, then export. Connect any image-generating upstream node.',
                zh: '将 image 映射为 data 后导出。可接任意图像生成上游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'field-mapper', label: '',
                    params: { mapping: '{"image": "data"}', drop_fields: '[]' },
                    input_params: {},
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
            input: {},
        },
        // ── 后缀模板：映射 → 导出（音频）──
        {
            id: 'suffix-mapper-export-audio',
            name: { en: 'Mapper → Export (Audio)', zh: '映射 → 导出（音频）' },
            icon: '🎵',
            description: {
                en: 'Map audio field to data, then export. Connect any audio-generating upstream node.',
                zh: '将 audio 映射为 data 后导出。可接任意音频生成上游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'field-mapper', label: '',
                    params: { mapping: '{"audio": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'audio', formats: '["wav", "mp3"]' },
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: {},
        },
        // ── 后缀模板：映射 → 导出（视频）──
        {
            id: 'suffix-mapper-export-video',
            name: { en: 'Mapper → Export (Video)', zh: '映射 → 导出（视频）' },
            icon: '🎬',
            description: {
                en: 'Map video field to data, then export. Connect any video-generating upstream node.',
                zh: '将 video 映射为 data 后导出。可接任意视频生成上游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'field-mapper', label: '',
                    params: { mapping: '{"video": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'video', formats: '["mp4"]' },
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: {},
        },
        // ── 后缀模板：映射 → 导出（文本）──
        {
            id: 'suffix-mapper-export-text',
            name: { en: 'Mapper → Export (Text)', zh: '映射 → 导出（文本）' },
            icon: '📄',
            description: {
                en: 'Map text field to data, then export. Connect any text-generating upstream node.',
                zh: '将 text 映射为 data 后导出。可接任意文本生成上游节点。',
            },
            nodes: [
                {
                    id: 'n1', type: 'field-mapper', label: '',
                    params: { mapping: '{"text": "data"}', drop_fields: '[]' },
                    input_params: {},
                    ...pos(0, 0),
                },
                {
                    id: 'n2', type: 'multi-format-exporter', label: '',
                    params: {},
                    input_params: { content_type: 'subtitle', formats: '["txt"]' },
                    ...pos(1, 0),
                },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2' },
            ],
            input: {},
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
