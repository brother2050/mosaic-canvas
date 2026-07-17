/**
 * Guide — comprehensive user guide rendered into a modal.
 *
 * Content is bilingual. In Chinese mode, node names are automatically
 * localized via I18n.nodeName() using a post-render replacement pass
 * on elements with data-node-name attributes.
 *
 * Sections:
 *  1. Overview
 *  2. Layout
 *  3. Adding Nodes
 *  4. Connecting Nodes
 *  5. Configuring Parameters
 *  6. Output Data Structure
 *  7. Data Flow & Field Mapping
 *  8. Prompt Library
 *  9. Node Reference (complete list by domain)
 * 10. Pipeline Combinations (detailed examples)
 * 11. Running Pipelines
 * 12. Saving & Loading
 * 13. Keyboard Shortcuts
 * 14. Tips & Tricks
 * 15. Troubleshooting
 */
const Guide = (() => {

    function render(targetId) {
        const el = document.getElementById(targetId);
        if (!el) return;

        const lang = I18n.getLang();
        el.innerHTML = lang === 'zh' ? _zhContent() : _enContent();

        // Post-render: localize node names in <code data-node="xxx"> tags
        el.querySelectorAll('code[data-node]').forEach(code => {
            const nodeId = code.dataset.node;
            const localized = I18n.nodeName(nodeId);
            code.textContent = localized;
            // Add title tooltip showing the raw ID
            if (localized !== nodeId) {
                code.title = nodeId;
            }
        });
    }

    // ── Helper: node name tag ──────────────────────────────
    // Usage in templates: ${n('text-to-image')} → <code data-node="text-to-image">text-to-image</code>
    function n(nodeId) {
        return `<code data-node="${nodeId}">${nodeId}</code>`;
    }

    function _enContent() {
        return `
        <div class="guide-section">
            <h4>1. Overview</h4>
            <p>Mosaic Canvas is a visual pipeline editor for AI workflows. Compose multi-modal AI pipelines by dragging nodes onto a canvas, connecting them, configuring parameters, and running with one click.</p>
            <div class="guide-tip">17 domains, 76+ nodes: Image, Video, Text/LLM, Audio, Subtitle, Digital Human, Export, RAG, Consistency, Core, and 7 helper domains (Data Flow, Container, Control Flow, Processing, Cache, Monitoring, I/O).</div>
        </div>

        <div class="guide-section">
            <h4>2. Layout</h4>
            <table>
                <tr><th>Area</th><th>Description</th></tr>
                <tr><td>Left Sidebar</td><td>Node palette (Nodes tab) and prompt library (Prompts tab). Searchable, grouped by domain.</td></tr>
                <tr><td>Center Canvas</td><td>Main workspace. Drag nodes, connect them, pan and zoom. Hover a node to see its tooltip.</td></tr>
                <tr><td>Right Sidebar</td><td>Properties panel: parameters, I/O types, output data structure.</td></tr>
                <tr><td>Bottom Panel</td><td>Pipeline input (key-value pairs) and execution results (streamed per-node).</td></tr>
                <tr><td>Top Toolbar</td><td>Run, Save, Load, Auto-layout, Language, Templates, Shortcuts, Guide.</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. Adding Nodes</h4>
            <ul>
                <li><strong>From palette</strong>: Click a node in the left sidebar — it appears at canvas center.</li>
                <li><strong>Drag-to-create</strong>: Drag from a node's output port (right side) to empty canvas. A popup shows only <em>compatible</em> nodes.</li>
                <li><strong>Search</strong>: Type in the search box to filter by name or description.</li>
                <li><strong>Compatible only</strong>: Toggle to show only nodes compatible with the selected node's output type.</li>
            </ul>
            <div class="guide-tip">Hover over any node on the canvas to see a tooltip with its description, input types, and output types.</div>
        </div>

        <div class="guide-section">
            <h4>4. Connecting Nodes</h4>
            <p>Connections enforce type compatibility. Drag from output port (right circle) to input port (left circle).</p>
            <ul>
                <li><strong>Green port</strong> = compatible, connection allowed.</li>
                <li><strong>Red port</strong> = type mismatch, connection blocked.</li>
                <li><strong>Wildcard</strong>: Nodes with input type <code>mosaic</code> accept any connection.</li>
            </ul>
            <div class="guide-tip">Select a node, toggle "Compatible only" in the palette to see only connectable nodes.</div>
            <p>Compatible type pairs (partial):</p>
            <table>
                <tr><th>Output Type</th><th>Accepts Input</th></tr>
                <tr><td>text</td><td>text, image, audio, video, document, json, rag_query_result</td></tr>
                <tr><td>image</td><td>image, video, avatar, json</td></tr>
                <tr><td>audio</td><td>audio, text, subtitle, json</td></tr>
                <tr><td>video</td><td>video, image, json</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>5. Configuring Parameters</h4>
            <p>Click a node to open its properties in the right sidebar.</p>
            <ul>
                <li><strong>Required</strong> fields marked with <code>*</code> and red badge.</li>
                <li><strong>Advanced</strong> parameters collapsed by default — click to expand.</li>
                <li><strong>Modified</strong> values show blue <code>●</code>. Click reset (↺) to restore defaults.</li>
                <li><strong>JSON fields</strong> (messages, labels, mappings, etc.) use textarea with format hints.</li>
                <li><strong>Prompt fields</strong> (prompt, negative_prompt, instruction, text) have <code>⊞</code> button for prompt library.</li>
            </ul>
            <div class="guide-tip">Prompt fields use multi-line textarea. Click <code>⊞</code> to insert snippets from the prompt library at cursor position.</div>
        </div>

        <div class="guide-section">
            <h4>6. Output Data Structure</h4>
            <p>Each node's properties panel includes an <strong>"Output Data Structure"</strong> section describing what fields it produces. This is essential for understanding data flow between nodes.</p>
            <table>
                <tr><th>Node</th><th>Key Output Fields</th></tr>
                <tr><td>${n('text-to-image')}</td><td><code>image</code> (PIL Image)</td></tr>
                <tr><td>${n('chat')} / ${n('text-generator')}</td><td><code>text</code> (string), <code>response</code> (string)</td></tr>
                <tr><td>${n('tts')}</td><td><code>waveform</code> (numpy array), <code>sample_rate</code> (int)</td></tr>
                <tr><td>${n('text-to-video')}</td><td><code>frames</code> (list of Images), <code>fps</code> (int)</td></tr>
                <tr><td>${n('subtitle-generator')}</td><td><code>segments</code> (list of {start, end, text})</td></tr>
                <tr><td>${n('retriever')}</td><td><code>results</code> (list), <code>context</code> (string), <code>rag_query_result</code> (dict)</td></tr>
                <tr><td>${n('asr')}</td><td><code>text</code> (string), <code>segments</code> (list)</td></tr>
                <tr><td>${n('frame-extractor')}</td><td><code>frames</code> (list), <code>frame_count</code> (int)</td></tr>
                <tr><td>${n('field-mapper')}</td><td>Passes through all input fields with renamed keys</td></tr>
            </table>
            <div class="guide-tip">Downstream nodes receive all output fields from upstream via <strong>MosaicData</strong> (a key-value container). The downstream node reads fields by name.</div>
        </div>

        <div class="guide-section">
            <h4>7. Data Flow & Field Mapping</h4>
            <p>When nodes connect, data flows through <strong>MosaicData</strong>. The downstream node reads fields by name. When field names don't match, use helper nodes to bridge the gap.</p>
            <p><strong>Common mismatch examples:</strong></p>
            <ul>
                <li>${n('chat')} outputs <code>text</code>, but ${n('text-to-image')} expects <code>prompt</code></li>
                <li>${n('translator')} outputs <code>translation</code>, but ${n('tts')} expects <code>text</code></li>
                <li>${n('asr')} outputs <code>text</code>, but ${n('subtitle-generator')} may expect <code>segments</code></li>
            </ul>
            <p><strong>Solution</strong>: Use helper nodes between them:</p>
            <table>
                <tr><th>Helper Node</th><th>Use Case</th><th>Example</th></tr>
                <tr><td>${n('field-mapper')}</td><td>Rename fields</td><td><code>mappings = {"text": "prompt"}</code></td></tr>
                <tr><td>${n('value-injector')}</td><td>Inject static values</td><td><code>values = {"width": 512, "height": 512}</code></td></tr>
                <tr><td>${n('type-converter')}</td><td>Convert types</td><td><code>conversions = {"count": "int"}</code></td></tr>
                <tr><td>${n('json-builder')}</td><td>Build structured JSON</td><td><code>blueprint = {"query": "prompt"}</code></td></tr>
                <tr><td>${n('json-path')}</td><td>Extract via JSONPath</td><td><code>query = "$.items[0]"</code> or <code>"$.items[1:3]"</code></td></tr>
                <tr><td>${n('template-renderer')}</td><td>Render Jinja2 templates</td><td><code>A {{ field }} image</code></td></tr>
                <tr><td>${n('data-merger')}</td><td>Merge multiple inputs</td><td>Combines fields from multiple upstream nodes</td></tr>
                <tr><td>${n('text-chunker')}</td><td>Split long text</td><td>Break text into chunks for batch processing</td></tr>
            </table>
            <div class="guide-tip"><strong>Example</strong>: ${n('chat')} → ${n('field-mapper')} → ${n('text-to-image')}. Set ${n('field-mapper')}'s <code>mappings</code> to <code>{"text": "prompt"}</code>. The chat's <code>text</code> becomes <code>prompt</code> for text-to-image.</div>
        </div>

        <div class="guide-section">
            <h4>8. Prompt Library</h4>
            <p>The Prompts tab provides reusable prompt snippets. 11 categories, 59+ subcategories, 688+ items.</p>
            <ul>
                <li><strong>Panel mode</strong>: Switch to Prompts tab, click a category to expand, search or browse, click a chip to insert.</li>
                <li><strong>Inline mode</strong>: Click <code>⊞</code> next to any prompt/negative_prompt field for a compact searchable popover.</li>
                <li><strong>Negative prompts</strong>: Dedicated category with quality, anatomy, face, style, composition items.</li>
            </ul>
            <div class="guide-tip"><strong>Custom prompts</strong>: Add JSON files to <code>data/prompts/</code> — auto-discovered. Format:
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">{
  "id": "my_category",
  "name": "我的分类", "name_en": "My Category",
  "icon": "★", "version": "1.0",
  "subcategories": [{
    "id": "sub_id", "name": "子类", "name_en": "Subcategory",
    "items": [{ "text": "prompt", "label": "显示名", "label_en": "Label" }]
  }]
}</pre></div>
        </div>

        <div class="guide-section">
            <h4>9. Node Reference</h4>
            <p>Complete list of all available nodes, grouped by domain.</p>

            <p><strong>Image</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('text-to-image')}</td><td>Generate image from text prompt</td><td>image</td></tr>
                <tr><td>${n('image-to-image')}</td><td>Transform image with prompt</td><td>image</td></tr>
                <tr><td>${n('inpainting')}</td><td>Edit specific regions of an image</td><td>image</td></tr>
                <tr><td>${n('upscaler')}</td><td>Upscale to higher resolution</td><td>image</td></tr>
                <tr><td>${n('background-remover')}</td><td>Remove image background</td><td>image (transparent)</td></tr>
                <tr><td>${n('stylizer')}</td><td>Apply artistic style transfer</td><td>image</td></tr>
            </table>

            <p><strong>Video</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('text-to-video')}</td><td>Generate video from text</td><td>frames, fps</td></tr>
                <tr><td>${n('image-to-video')}</td><td>Animate a static image</td><td>frames, fps</td></tr>
                <tr><td>${n('hunyuan-video')}</td><td>Hunyuan video model</td><td>frames, fps</td></tr>
                <tr><td>${n('ltx-video')}</td><td>LTX video model</td><td>frames, fps</td></tr>
                <tr><td>${n('wan-video')}</td><td>Wan video model</td><td>frames, fps</td></tr>
                <tr><td>${n('video-continuation')}</td><td>Continue an existing video</td><td>frames, fps</td></tr>
                <tr><td>${n('frame-interpolation')}</td><td>Interpolate between frames</td><td>frames, fps</td></tr>
                <tr><td>${n('frame-extractor')}</td><td>Extract frames from video</td><td>frames, frame_count</td></tr>
            </table>

            <p><strong>Text / LLM</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('chat')}</td><td>Chat with an LLM (requires messages)</td><td>text, response, messages</td></tr>
                <tr><td>${n('text-generator')}</td><td>Generate text from instruction</td><td>text, response</td></tr>
                <tr><td>${n('text-summarizer')}</td><td>Summarize long text</td><td>summary, text</td></tr>
                <tr><td>${n('translator')}</td><td>Translate text</td><td>text, translation</td></tr>
                <tr><td>${n('text-classifier')}</td><td>Classify text into categories</td><td>label, scores</td></tr>
                <tr><td>${n('text-rewriter')}</td><td>Rewrite/paraphrase text</td><td>text</td></tr>
            </table>

            <p><strong>Audio</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('tts')}</td><td>Text-to-speech synthesis</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('asr')}</td><td>Speech-to-text recognition</td><td>text, segments</td></tr>
                <tr><td>${n('music-generator')}</td><td>Generate music</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('sound-effect-generator')}</td><td>Generate sound effects</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('voice-clone')}</td><td>Clone voice from sample</td><td>waveform, sample_rate</td></tr>
            </table>

            <p><strong>Subtitle</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('subtitle-generator')}</td><td>Generate subtitles from audio</td><td>segments</td></tr>
                <tr><td>${n('subtitle-aligner')}</td><td>Align subtitles to audio</td><td>segments</td></tr>
                <tr><td>${n('subtitle-translator')}</td><td>Translate subtitles</td><td>segments</td></tr>
            </table>

            <p><strong>Digital Human</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('lip-syncer')}</td><td>Lip-sync video to audio</td><td>frames, fps</td></tr>
                <tr><td>${n('avatar-driver')}</td><td>Drive avatar with motion</td><td>frames, fps</td></tr>
                <tr><td>${n('motion-generator')}</td><td>Generate motion data</td><td>motion, keypoints</td></tr>
                <tr><td>${n('realtime-renderer')}</td><td>Real-time avatar rendering</td><td>frames, fps</td></tr>
            </table>

            <p><strong>Consistency</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('identity-keeper')}</td><td>Preserve face identity</td><td>image, face_embedding</td></tr>
                <tr><td>${n('style-keeper')}</td><td>Preserve artistic style</td><td>image</td></tr>
                <tr><td>${n('cross-frame-consistency')}</td><td>Maintain consistency across frames</td><td>image, keypoints</td></tr>
            </table>

            <p><strong>Export</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('video-encoder')}</td><td>Encode frames to video file</td><td>video_path, video</td></tr>
                <tr><td>${n('multi-format-exporter')}</td><td>Export to multiple formats</td><td>path, content_type</td></tr>
                <tr><td>${n('livestreamer')}</td><td>Stream to live platform</td><td>url</td></tr>
            </table>

            <p><strong>RAG</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th><th>Output</th></tr>
                <tr><td>${n('document-parser')}</td><td>Parse PDF/docs to text</td><td>text, pages</td></tr>
                <tr><td>${n('vector-indexer')}</td><td>Index text into vector store</td><td>index, vectors</td></tr>
                <tr><td>${n('retriever')}</td><td>Retrieve relevant chunks</td><td>results, context, rag_query_result</td></tr>
                <tr><td>${n('citation-generator')}</td><td>Add citations to text</td><td>citations, text</td></tr>
            </table>

            <p><strong>Helper: Data Flow</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th></tr>
                <tr><td>${n('field-mapper')}</td><td>Rename/remap fields: <code>{"src": "dst"}</code></td></tr>
                <tr><td>${n('type-converter')}</td><td>Convert field types: <code>{"field": "int"}</code></td></tr>
                <tr><td>${n('data-merger')}</td><td>Merge multiple upstream inputs</td></tr>
                <tr><td>${n('data-splitter')}</td><td>Split data into chunks</td></tr>
                <tr><td>${n('value-injector')}</td><td>Inject static values</td></tr>
                <tr><td>${n('schema-validator')}</td><td>Validate data schema</td></tr>
            </table>

            <p><strong>Helper: Container</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th></tr>
                <tr><td>${n('json-parser')}</td><td>Parse JSON strings</td></tr>
                <tr><td>${n('json-builder')}</td><td>Build JSON from blueprint</td></tr>
                <tr><td>${n('json-path')}</td><td>JSONPath query: <code>$.field[0]</code>, <code>$.arr[1:3]</code>, <code>$.arr[1,3]</code></td></tr>
                <tr><td>${n('list-ops')}</td><td>List operations (sort, filter, slice)</td></tr>
                <tr><td>${n('dict-ops')}</td><td>Dict operations (get, set, rename)</td></tr>
                <tr><td>${n('string-ops')}</td><td>String operations</td></tr>
                <tr><td>${n('data-flattener')}</td><td>Flatten nested dict</td></tr>
                <tr><td>${n('data-grouper')}</td><td>Group data by key</td></tr>
                <tr><td>${n('text-chunker')}</td><td>Split text into chunks</td></tr>
            </table>

            <p><strong>Helper: Control Flow</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th></tr>
                <tr><td>${n('loop')}</td><td>Iterate over data</td></tr>
                <tr><td>${n('retry')}</td><td>Retry on failure</td></tr>
                <tr><td>${n('timeout')}</td><td>Add timeout to execution</td></tr>
                <tr><td>${n('switch')}</td><td>Route data by condition</td></tr>
                <tr><td>${n('parallel-map')}</td><td>Process in parallel</td></tr>
            </table>

            <p><strong>Helper: Processing</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th></tr>
                <tr><td>${n('filter')}</td><td>Filter data by condition</td></tr>
                <tr><td>${n('batcher')}</td><td>Split into batches</td></tr>
                <tr><td>${n('aggregator')}</td><td>Aggregate statistics</td></tr>
                <tr><td>${n('template-renderer')}</td><td>Render Jinja2 templates</td></tr>
                <tr><td>${n('throttler')}</td><td>Rate limiting</td></tr>
            </table>

            <p><strong>Helper: I/O</strong></p>
            <table>
                <tr><th>Node</th><th>Description</th></tr>
                <tr><td>${n('file-reader')}</td><td>Read files (text, image, audio, json)</td></tr>
                <tr><td>${n('file-writer')}</td><td>Write files</td></tr>
                <tr><td>${n('api-caller')}</td><td>Call external APIs</td></tr>
                <tr><td>${n('data-injector')}</td><td>Inject static data</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>10. Pipeline Combinations</h4>

            <p><strong>10.1 Simple Text-to-Image</strong></p>
            <ul>
                <li>Add ${n('text-to-image')} node</li>
                <li>Set pipeline input: <code>prompt</code> = "a cat on a windowsill"</li>
                <li>Optional: <code>negative_prompt</code> = "low quality, blurry"</li>
                <li>Click Run — image appears in Results</li>
            </ul>

            <p><strong>10.2 Chat → Field Mapper → Text-to-Image</strong></p>
            <p>Use LLM to generate a prompt, then pass to image generation.</p>
            <ul>
                <li>Add ${n('chat')} node → set <code>messages</code> field (required): <code>[{"role": "user", "content": "Describe a sunset over the ocean"}]</code></li>
                <li>Add ${n('field-mapper')} node → set <code>mappings</code>: <code>{"text": "prompt"}</code></li>
                <li>Add ${n('text-to-image')} node</li>
                <li>Connect: ${n('chat')} → ${n('field-mapper')} → ${n('text-to-image')}</li>
            </ul>
            <div class="guide-tip">${n('chat')} outputs <code>text</code>. ${n('field-mapper')} renames it to <code>prompt</code>. ${n('text-to-image')} reads <code>prompt</code>. Check each node's "Output Data Structure" in the properties panel.</div>

            <p><strong>10.3 TTS → Lip Syncer</strong></p>
            <ul>
                <li>Add ${n('tts')} → set <code>text</code>: "Hello, welcome!"</li>
                <li>Add ${n('lip-syncer')} → needs <code>waveform</code> (from tts) + face image</li>
                <li>Connect: ${n('tts')} → ${n('lip-syncer')}</li>
                <li>Set pipeline input <code>image</code> = path to face image</li>
            </ul>

            <p><strong>10.4 Video Processing Chain</strong></p>
            <ul>
                <li>${n('frame-extractor')} → extracts <code>frames</code> from input video</li>
                <li>${n('upscaler')} → processes each frame's <code>image</code></li>
                <li>${n('video-encoder')} → combines <code>frames</code> + <code>fps</code> into video</li>
                <li>Connect: ${n('frame-extractor')} → ${n('upscaler')} → ${n('video-encoder')}</li>
            </ul>

            <p><strong>10.5 RAG Pipeline</strong></p>
            <ul>
                <li>${n('document-parser')} → extracts <code>text</code> from PDF</li>
                <li>${n('vector-indexer')} → indexes text into vectors</li>
                <li>${n('retriever')} → retrieves relevant chunks, outputs <code>context</code></li>
                <li>${n('field-mapper')} → map <code>context</code> to <code>instruction</code></li>
                <li>${n('chat')} → uses context to answer questions</li>
            </ul>

            <p><strong>10.6 Image-to-Image with Negative Prompts</strong></p>
            <ul>
                <li>Add ${n('image-to-image')} node</li>
                <li>Set <code>prompt</code>: "oil painting style"</li>
                <li>Set <code>negative_prompt</code>: click ⊞ to pick "blurry", "low quality" from Negative Prompts</li>
                <li>Set pipeline input <code>image</code> = input image path</li>
            </ul>

            <p><strong>10.7 Audio → Subtitle → Translation</strong></p>
            <ul>
                <li>${n('asr')} → transcribes audio to <code>text</code> + <code>segments</code></li>
                <li>${n('subtitle-generator')} → generates <code>segments</code> with timestamps</li>
                <li>${n('subtitle-translator')} → translates subtitle segments</li>
                <li>Connect: ${n('asr')} → ${n('subtitle-translator')}</li>
            </ul>

            <p><strong>10.8 JSONPath Data Extraction</strong></p>
            <ul>
                <li>${n('api-caller')} → fetches data, outputs <code>response</code> (dict)</li>
                <li>${n('json-path')} → extract specific fields: <code>query = "$.data.users[*].name"</code></li>
                <li>${n('template-renderer')} → format: <code>"Hello, {{ result }}"</code></li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>11. Running Pipelines</h4>
            <ul>
                <li>Set pipeline input in the bottom-left panel (key-value pairs for source nodes).</li>
                <li>Click <strong>Run</strong> (▶) in the toolbar.</li>
                <li><strong>Results stream in real-time</strong>: each node's output appears when it completes.</li>
                <li>Node status: idle (gray), running (blue pulse), success (green ✓), error (red ✗).</li>
                <li>Click a result card header to collapse/expand.</li>
            </ul>
            <div class="guide-tip">If a node fails, the pipeline stops (fail-fast). Check the error in the red node's result card. Fix and re-run.</div>
        </div>

        <div class="guide-section">
            <h4>12. Saving & Loading</h4>
            <ul>
                <li><strong>Save</strong>: Download pipeline as JSON.</li>
                <li><strong>Load</strong>: Select a saved JSON file.</li>
                <li><strong>Templates</strong>: Pre-built example pipelines.</li>
                <li><strong>Export Python</strong>: Generate a standalone Python script.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>13. Keyboard Shortcuts</h4>
            <table>
                <tr><th>Key</th><th>Action</th></tr>
                <tr><td><code>Delete</code></td><td>Delete selected node</td></tr>
                <tr><td><code>Ctrl+C</code></td><td>Copy selected node</td></tr>
                <tr><td><code>Ctrl+V</code></td><td>Paste node</td></tr>
                <tr><td><code>Ctrl+Z</code></td><td>Undo</td></tr>
                <tr><td><code>Ctrl+Shift+Z</code></td><td>Redo</td></tr>
                <tr><td><code>Space+Drag</code></td><td>Pan canvas</td></tr>
                <tr><td><code>Scroll</code></td><td>Zoom</td></tr>
                <tr><td><code>Escape</code></td><td>Deselect / close popups</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>14. Tips & Tricks</h4>
            <ul>
                <li>Use <strong>drag-to-empty-canvas</strong> for fastest node chaining.</li>
                <li>Toggle <strong>"Compatible only"</strong> when unsure what connects next.</li>
                <li><strong>Check Output Data Structure</strong> before connecting nodes.</li>
                <li>Use ${n('field-mapper')} when field names don't match.</li>
                <li>Use ${n('value-injector')} to add defaults (width, height, seed) without source nodes.</li>
                <li>Use ${n('json-path')} for array indexing and slicing: <code>$.arr[2]</code>, <code>$.arr[1,3]</code>, <code>$.arr[1:3]</code>.</li>
                <li>Hover over a node on canvas to see its tooltip with description and I/O types.</li>
                <li>Switch language anytime with EN/中 button.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>15. Troubleshooting</h4>
            <table>
                <tr><th>Problem</th><th>Solution</th></tr>
                <tr><td>Node shows red error</td><td>Check error message in Results. Common: model not loaded, missing required input, type mismatch.</td></tr>
                <tr><td>Cannot connect two nodes</td><td>Types incompatible. Check I/O types in properties. Use ${n('type-converter')} if needed.</td></tr>
                <tr><td>Downstream gets empty input</td><td>Field name mismatch. Check upstream's Output Data Structure, use ${n('field-mapper')} to rename.</td></tr>
                <tr><td>${n('chat')} node fails</td><td><code>messages</code> is required. Set it to <code>[{"role": "user", "content": "your question"}]</code>.</td></tr>
                <tr><td>Model loading timeout</td><td>Try smaller model or check network. Timeout: 10 minutes.</td></tr>
                <tr><td>Low quality images</td><td>Add negative prompts: "low quality, blurry, worst quality". Increase resolution.</td></tr>
                <tr><td>Prompt picker (⊞) not inserting</td><td>Click the target field first, then ⊞, then select a prompt.</td></tr>
                <tr><td>Run button no response</td><td>Hard refresh browser (Ctrl+Shift+R) to clear cached JS.</td></tr>
            </table>
        </div>
        `;
    }

    function _zhContent() {
        return `
        <div class="guide-section">
            <h4>1. 概述</h4>
            <p>Mosaic Canvas 是一个可视化 AI 流水线编辑器。通过拖拽节点、连接节点、配置参数，一键运行多模态 AI 流水线。</p>
            <div class="guide-tip">17 个域，76+ 个节点：图像、视频、文本/LLM、音频、字幕、数字人、导出、RAG、一致性、核心，以及 7 个辅助域（数据流、容器、控制流、处理、缓存、监控、输入输出）。</div>
        </div>

        <div class="guide-section">
            <h4>2. 界面布局</h4>
            <table>
                <tr><th>区域</th><th>说明</th></tr>
                <tr><td>左侧栏</td><td>节点面板（节点标签）和提示词库（提示词标签）。可搜索，按域分组。</td></tr>
                <tr><td>中央画布</td><td>主工作区。拖入节点、连接节点、平移缩放。悬停节点可查看提示信息。</td></tr>
                <tr><td>右侧栏</td><td>属性面板：参数、I/O 类型、输出数据结构。</td></tr>
                <tr><td>底部面板</td><td>流水线输入（键值对）和执行结果（逐节点流式展示）。</td></tr>
                <tr><td>顶部工具栏</td><td>运行、保存、加载、自动布局、语言切换、模板、快捷键、指南。</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. 添加节点</h4>
            <ul>
                <li><strong>从面板添加</strong>：点击左侧栏中的节点 — 出现在画布中央。</li>
                <li><strong>拖拽创建</strong>：从节点输出端口（右侧）拖到空白画布。弹出菜单只显示<em>兼容</em>节点。</li>
                <li><strong>搜索</strong>：在搜索框输入关键词过滤。</li>
                <li><strong>仅显示兼容</strong>：勾选后只显示与选中节点兼容的节点。</li>
            </ul>
            <div class="guide-tip">在画布上悬停任意节点，可查看包含描述、输入输出类型的提示窗口。</div>
        </div>

        <div class="guide-section">
            <h4>4. 连接节点</h4>
            <p>连接遵循类型兼容规则。从输出端口（右侧圆点）拖到输入端口（左侧圆点）。</p>
            <ul>
                <li><strong>绿色端口</strong> = 兼容，允许连接。</li>
                <li><strong>红色端口</strong> = 类型不匹配，连接被阻止。</li>
                <li><strong>通配类型</strong>：输入类型为 <code>mosaic</code> 的节点接受任何连接。</li>
            </ul>
            <div class="guide-tip">选中节点后开启"仅显示兼容"，即可只看到可连接的节点。</div>
            <p>兼容类型对照（部分）：</p>
            <table>
                <tr><th>输出类型</th><th>可接受的输入类型</th></tr>
                <tr><td>text</td><td>text, image, audio, video, document, json, rag_query_result</td></tr>
                <tr><td>image</td><td>image, video, avatar, json</td></tr>
                <tr><td>audio</td><td>audio, text, subtitle, json</td></tr>
                <tr><td>video</td><td>video, image, json</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>5. 配置参数</h4>
            <p>点击节点打开右侧属性面板。</p>
            <ul>
                <li><strong>必填</strong>字段标记 <code>*</code> 和红色标签。</li>
                <li><strong>高级参数</strong>默认折叠 — 点击展开。</li>
                <li><strong>已修改</strong>的值显示蓝色 <code>●</code>。点击重置（↺）恢复默认。</li>
                <li><strong>JSON 字段</strong>（messages、labels、mappings 等）使用多行文本框。</li>
                <li><strong>提示词字段</strong>（prompt、negative_prompt、instruction、text）有 <code>⊞</code> 按钮打开提示词库。</li>
            </ul>
            <div class="guide-tip">提示词字段使用多行文本框。点击 <code>⊞</code> 在光标位置插入提示词库片段。</div>
        </div>

        <div class="guide-section">
            <h4>6. 输出数据结构</h4>
            <p>每个节点的属性面板都有<strong>"输出数据结构"</strong>部分，描述产出的字段。这对理解节点间的数据流至关重要。</p>
            <table>
                <tr><th>节点</th><th>关键输出字段</th></tr>
                <tr><td>${n('text-to-image')}</td><td><code>image</code>（PIL 图像）</td></tr>
                <tr><td>${n('chat')} / ${n('text-generator')}</td><td><code>text</code>（字符串），<code>response</code>（字符串）</td></tr>
                <tr><td>${n('tts')}</td><td><code>waveform</code>（numpy 数组），<code>sample_rate</code>（整数）</td></tr>
                <tr><td>${n('text-to-video')}</td><td><code>frames</code>（图像列表），<code>fps</code>（整数）</td></tr>
                <tr><td>${n('subtitle-generator')}</td><td><code>segments</code>（{start, end, text} 列表）</td></tr>
                <tr><td>${n('retriever')}</td><td><code>results</code>（列表），<code>context</code>（字符串），<code>rag_query_result</code>（字典）</td></tr>
                <tr><td>${n('asr')}</td><td><code>text</code>（字符串），<code>segments</code>（列表）</td></tr>
                <tr><td>${n('frame-extractor')}</td><td><code>frames</code>（列表），<code>frame_count</code>（整数）</td></tr>
                <tr><td>${n('field-mapper')}</td><td>透传所有输入字段，键名已重命名</td></tr>
            </table>
            <div class="guide-tip">下游节点通过 <strong>MosaicData</strong>（键值对容器）接收上游所有输出字段，按名称读取所需字段。</div>
        </div>

        <div class="guide-section">
            <h4>7. 数据流与字段映射</h4>
            <p>节点连接后，数据通过 <strong>MosaicData</strong> 流动，下游按名称读取字段。字段名不匹配时，用辅助节点桥接。</p>
            <p><strong>常见不匹配场景：</strong></p>
            <ul>
                <li>${n('chat')} 输出 <code>text</code>，但 ${n('text-to-image')} 期望 <code>prompt</code></li>
                <li>${n('translator')} 输出 <code>translation</code>，但 ${n('tts')} 期望 <code>text</code></li>
                <li>${n('asr')} 输出 <code>text</code>，但 ${n('subtitle-generator')} 可能需要 <code>segments</code></li>
            </ul>
            <p><strong>解决方案</strong>：在中间使用辅助节点：</p>
            <table>
                <tr><th>辅助节点</th><th>用途</th><th>示例</th></tr>
                <tr><td>${n('field-mapper')}</td><td>重命名字段</td><td><code>mappings = {"text": "prompt"}</code></td></tr>
                <tr><td>${n('value-injector')}</td><td>注入静态值</td><td><code>values = {"width": 512, "height": 512}</code></td></tr>
                <tr><td>${n('type-converter')}</td><td>类型转换</td><td><code>conversions = {"count": "int"}</code></td></tr>
                <tr><td>${n('json-builder')}</td><td>构建结构化 JSON</td><td><code>blueprint = {"query": "prompt"}</code></td></tr>
                <tr><td>${n('json-path')}</td><td>JSONPath 提取</td><td><code>query = "$.items[0]"</code> 或 <code>"$.items[1:3]"</code></td></tr>
                <tr><td>${n('template-renderer')}</td><td>渲染 Jinja2 模板</td><td><code>A {{ field }} image</code></td></tr>
                <tr><td>${n('data-merger')}</td><td>合并多个输入</td><td>合并多个上游节点的字段</td></tr>
                <tr><td>${n('text-chunker')}</td><td>长文本分块</td><td>将文本拆分为块，便于批处理</td></tr>
            </table>
            <div class="guide-tip"><strong>示例</strong>：${n('chat')} → ${n('field-mapper')} → ${n('text-to-image')}。设置 ${n('field-mapper')} 的 <code>mappings</code> 为 <code>{"text": "prompt"}</code>。对话输出的 <code>text</code> 会变成文生图需要的 <code>prompt</code>。</div>
        </div>

        <div class="guide-section">
            <h4>8. 提示词库</h4>
            <p>左侧栏"提示词"标签提供可复用提示词片段。11 个大类、59+ 个子类、688+ 条。</p>
            <ul>
                <li><strong>面板模式</strong>：切换到"提示词"标签，点击大类展开，搜索或浏览，点击标签插入。</li>
                <li><strong>内联模式</strong>：点击属性面板中 prompt/negative_prompt 字段旁的 <code>⊞</code> 按钮。</li>
                <li><strong>负面提示词</strong>：专用分类，含画质、人体、面部、风格、构图等子类。</li>
            </ul>
            <div class="guide-tip"><strong>自定义提示词</strong>：将 JSON 文件放入 <code>data/prompts/</code> — 自动发现。格式：
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">{
  "id": "my_category",
  "name": "我的分类", "name_en": "My Category",
  "icon": "★", "version": "1.0",
  "subcategories": [{
    "id": "sub_id", "name": "子类", "name_en": "Subcategory",
    "items": [{ "text": "提示词", "label": "显示名", "label_en": "Label" }]
  }]
}</pre></div>
        </div>

        <div class="guide-section">
            <h4>9. 节点参考</h4>
            <p>所有可用节点的完整列表，按域分组。</p>

            <p><strong>图像</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('text-to-image')}</td><td>文本生成图像</td><td>image</td></tr>
                <tr><td>${n('image-to-image')}</td><td>根据提示词变换图像</td><td>image</td></tr>
                <tr><td>${n('inpainting')}</td><td>局部重绘图像</td><td>image</td></tr>
                <tr><td>${n('upscaler')}</td><td>图像放大</td><td>image</td></tr>
                <tr><td>${n('background-remover')}</td><td>移除背景</td><td>image（透明）</td></tr>
                <tr><td>${n('stylizer')}</td><td>风格迁移</td><td>image</td></tr>
            </table>

            <p><strong>视频</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('text-to-video')}</td><td>文本生成视频</td><td>frames, fps</td></tr>
                <tr><td>${n('image-to-video')}</td><td>静态图像转视频</td><td>frames, fps</td></tr>
                <tr><td>${n('hunyuan-video')}</td><td>混元视频模型</td><td>frames, fps</td></tr>
                <tr><td>${n('ltx-video')}</td><td>LTX 视频模型</td><td>frames, fps</td></tr>
                <tr><td>${n('wan-video')}</td><td>Wan 视频模型</td><td>frames, fps</td></tr>
                <tr><td>${n('video-continuation')}</td><td>视频续写</td><td>frames, fps</td></tr>
                <tr><td>${n('frame-interpolation')}</td><td>帧间插值</td><td>frames, fps</td></tr>
                <tr><td>${n('frame-extractor')}</td><td>视频抽帧</td><td>frames, frame_count</td></tr>
            </table>

            <p><strong>文本 / LLM</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('chat')}</td><td>LLM 对话（需要 messages）</td><td>text, response, messages</td></tr>
                <tr><td>${n('text-generator')}</td><td>根据指令生成文本</td><td>text, response</td></tr>
                <tr><td>${n('text-summarizer')}</td><td>文本摘要</td><td>summary, text</td></tr>
                <tr><td>${n('translator')}</td><td>翻译</td><td>text, translation</td></tr>
                <tr><td>${n('text-classifier')}</td><td>文本分类</td><td>label, scores</td></tr>
                <tr><td>${n('text-rewriter')}</td><td>文本改写</td><td>text</td></tr>
            </table>

            <p><strong>音频</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('tts')}</td><td>语音合成</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('asr')}</td><td>语音识别</td><td>text, segments</td></tr>
                <tr><td>${n('music-generator')}</td><td>音乐生成</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('sound-effect-generator')}</td><td>音效生成</td><td>waveform, sample_rate</td></tr>
                <tr><td>${n('voice-clone')}</td><td>声音克隆</td><td>waveform, sample_rate</td></tr>
            </table>

            <p><strong>字幕</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('subtitle-generator')}</td><td>从音频生成字幕</td><td>segments</td></tr>
                <tr><td>${n('subtitle-aligner')}</td><td>字幕对齐</td><td>segments</td></tr>
                <tr><td>${n('subtitle-translator')}</td><td>字幕翻译</td><td>segments</td></tr>
            </table>

            <p><strong>数字人</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('lip-syncer')}</td><td>唇形同步</td><td>frames, fps</td></tr>
                <tr><td>${n('avatar-driver')}</td><td>虚拟人驱动</td><td>frames, fps</td></tr>
                <tr><td>${n('motion-generator')}</td><td>动作生成</td><td>motion, keypoints</td></tr>
                <tr><td>${n('realtime-renderer')}</td><td>实时渲染</td><td>frames, fps</td></tr>
            </table>

            <p><strong>一致性</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('identity-keeper')}</td><td>身份保持</td><td>image, face_embedding</td></tr>
                <tr><td>${n('style-keeper')}</td><td>风格保持</td><td>image</td></tr>
                <tr><td>${n('cross-frame-consistency')}</td><td>跨帧一致性</td><td>image, keypoints</td></tr>
            </table>

            <p><strong>导出</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('video-encoder')}</td><td>帧编码为视频</td><td>video_path, video</td></tr>
                <tr><td>${n('multi-format-exporter')}</td><td>多格式导出</td><td>path, content_type</td></tr>
                <tr><td>${n('livestreamer')}</td><td>直播推流</td><td>url</td></tr>
            </table>

            <p><strong>RAG</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th><th>输出</th></tr>
                <tr><td>${n('document-parser')}</td><td>解析 PDF/文档</td><td>text, pages</td></tr>
                <tr><td>${n('vector-indexer')}</td><td>文本向量化索引</td><td>index, vectors</td></tr>
                <tr><td>${n('retriever')}</td><td>检索相关内容</td><td>results, context, rag_query_result</td></tr>
                <tr><td>${n('citation-generator')}</td><td>生成引用</td><td>citations, text</td></tr>
            </table>

            <p><strong>辅助：数据流</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th></tr>
                <tr><td>${n('field-mapper')}</td><td>重命名/映射字段：<code>{"src": "dst"}</code></td></tr>
                <tr><td>${n('type-converter')}</td><td>转换字段类型：<code>{"field": "int"}</code></td></tr>
                <tr><td>${n('data-merger')}</td><td>合并多个上游输入</td></tr>
                <tr><td>${n('data-splitter')}</td><td>拆分数据</td></tr>
                <tr><td>${n('value-injector')}</td><td>注入静态值</td></tr>
                <tr><td>${n('schema-validator')}</td><td>校验数据结构</td></tr>
            </table>

            <p><strong>辅助：容器</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th></tr>
                <tr><td>${n('json-parser')}</td><td>解析 JSON 字符串</td></tr>
                <tr><td>${n('json-builder')}</td><td>按蓝图构建 JSON</td></tr>
                <tr><td>${n('json-path')}</td><td>JSONPath 查询：<code>$.field[0]</code>、<code>$.arr[1:3]</code>、<code>$.arr[1,3]</code></td></tr>
                <tr><td>${n('list-ops')}</td><td>列表操作（排序、过滤、切片）</td></tr>
                <tr><td>${n('dict-ops')}</td><td>字典操作（获取、设置、重命名）</td></tr>
                <tr><td>${n('string-ops')}</td><td>字符串操作</td></tr>
                <tr><td>${n('data-flattener')}</td><td>扁平化嵌套字典</td></tr>
                <tr><td>${n('data-grouper')}</td><td>按键分组</td></tr>
                <tr><td>${n('text-chunker')}</td><td>文本分块</td></tr>
            </table>

            <p><strong>辅助：控制流</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th></tr>
                <tr><td>${n('loop')}</td><td>循环遍历</td></tr>
                <tr><td>${n('retry')}</td><td>失败重试</td></tr>
                <tr><td>${n('timeout')}</td><td>超时控制</td></tr>
                <tr><td>${n('switch')}</td><td>条件路由</td></tr>
                <tr><td>${n('parallel-map')}</td><td>并行处理</td></tr>
            </table>

            <p><strong>辅助：处理</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th></tr>
                <tr><td>${n('filter')}</td><td>条件过滤</td></tr>
                <tr><td>${n('batcher')}</td><td>批次切片</td></tr>
                <tr><td>${n('aggregator')}</td><td>聚合统计</td></tr>
                <tr><td>${n('template-renderer')}</td><td>渲染 Jinja2 模板</td></tr>
                <tr><td>${n('throttler')}</td><td>速率限制</td></tr>
            </table>

            <p><strong>辅助：输入输出</strong></p>
            <table>
                <tr><th>节点</th><th>说明</th></tr>
                <tr><td>${n('file-reader')}</td><td>读取文件（文本、图像、音频、JSON）</td></tr>
                <tr><td>${n('file-writer')}</td><td>写入文件</td></tr>
                <tr><td>${n('api-caller')}</td><td>调用外部 API</td></tr>
                <tr><td>${n('data-injector')}</td><td>注入静态数据</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>10. 流水线组合示例</h4>

            <p><strong>10.1 简单文生图</strong></p>
            <ul>
                <li>添加 ${n('text-to-image')} 节点</li>
                <li>设置流水线输入：<code>prompt</code> = "一只猫坐在窗台上"</li>
                <li>可选：<code>negative_prompt</code> = "low quality, blurry"</li>
                <li>点击运行 — 图片出现在结果面板</li>
            </ul>

            <p><strong>10.2 对话 → 字段映射 → 文生图</strong></p>
            <p>用 LLM 生成提示词，再传给图像生成。</p>
            <ul>
                <li>添加 ${n('chat')} 节点 → 设置 <code>messages</code>（必填）：<code>[{"role": "user", "content": "描述海上日落"}]</code></li>
                <li>添加 ${n('field-mapper')} 节点 → 设置 <code>mappings</code>：<code>{"text": "prompt"}</code></li>
                <li>添加 ${n('text-to-image')} 节点</li>
                <li>连接：${n('chat')} → ${n('field-mapper')} → ${n('text-to-image')}</li>
            </ul>
            <div class="guide-tip">${n('chat')} 输出 <code>text</code>，${n('field-mapper')} 将其重命名为 <code>prompt</code>，${n('text-to-image')} 读取 <code>prompt</code>。在属性面板查看每个节点的"输出数据结构"。</div>

            <p><strong>10.3 语音合成 → 唇形同步</strong></p>
            <ul>
                <li>${n('tts')} → 设置 <code>text</code>："你好，欢迎！"</li>
                <li>${n('lip-syncer')} → 需要 <code>waveform</code>（来自 tts）+ 人脸图像</li>
                <li>连接：${n('tts')} → ${n('lip-syncer')}</li>
                <li>流水线输入 <code>image</code> = 人脸图像路径</li>
            </ul>

            <p><strong>10.4 视频处理链</strong></p>
            <ul>
                <li>${n('frame-extractor')} → 从视频提取 <code>frames</code></li>
                <li>${n('upscaler')} → 处理每帧的 <code>image</code></li>
                <li>${n('video-encoder')} → 将 <code>frames</code> + <code>fps</code> 编码为视频</li>
                <li>连接：${n('frame-extractor')} → ${n('upscaler')} → ${n('video-encoder')}</li>
            </ul>

            <p><strong>10.5 RAG 流水线</strong></p>
            <ul>
                <li>${n('document-parser')} → 从 PDF 提取 <code>text</code></li>
                <li>${n('vector-indexer')} → 文本向量化索引</li>
                <li>${n('retriever')} → 检索相关内容，输出 <code>context</code></li>
                <li>${n('field-mapper')} → 将 <code>context</code> 映射为 <code>instruction</code></li>
                <li>${n('chat')} → 使用上下文回答问题</li>
            </ul>

            <p><strong>10.6 图生图 + 负面提示词</strong></p>
            <ul>
                <li>添加 ${n('image-to-image')} 节点</li>
                <li>设置 <code>prompt</code>："油画风格"</li>
                <li>设置 <code>negative_prompt</code>：点击 ⊞ 从"负面提示词"选择"模糊"、"低质量"等</li>
                <li>流水线输入 <code>image</code> = 输入图像路径</li>
            </ul>

            <p><strong>10.7 音频 → 字幕 → 翻译</strong></p>
            <ul>
                <li>${n('asr')} → 转录音频为 <code>text</code> + <code>segments</code></li>
                <li>${n('subtitle-generator')} → 生成带时间戳的 <code>segments</code></li>
                <li>${n('subtitle-translator')} → 翻译字幕</li>
                <li>连接：${n('asr')} → ${n('subtitle-translator')}</li>
            </ul>

            <p><strong>10.8 JSONPath 数据提取</strong></p>
            <ul>
                <li>${n('api-caller')} → 获取数据，输出 <code>response</code>（字典）</li>
                <li>${n('json-path')} → 提取字段：<code>query = "$.data.users[*].name"</code></li>
                <li>${n('template-renderer')} → 格式化：<code>"你好，{{ result }}"</code></li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>11. 运行流水线</h4>
            <ul>
                <li>在底部左侧面板设置流水线输入值（源节点的键值对）。</li>
                <li>点击工具栏 <strong>运行</strong>（▶）。</li>
                <li><strong>结果实时流式展示</strong>：每个节点完成后立即显示输出。</li>
                <li>节点状态：空闲（灰色）、运行中（蓝色脉冲）、成功（绿色 ✓）、错误（红色 ✗）。</li>
                <li>点击结果卡片标题可折叠/展开。</li>
            </ul>
            <div class="guide-tip">节点失败时流水线停止（快速失败）。在红色节点的结果卡片查看错误，修复后重试。</div>
        </div>

        <div class="guide-section">
            <h4>12. 保存与加载</h4>
            <ul>
                <li><strong>保存</strong>：下载流水线为 JSON 文件。</li>
                <li><strong>加载</strong>：选择已保存的 JSON 文件。</li>
                <li><strong>模板</strong>：预置示例流水线。</li>
                <li><strong>导出 Python</strong>：生成可独立运行的 Python 脚本。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>13. 键盘快捷键</h4>
            <table>
                <tr><th>按键</th><th>功能</th></tr>
                <tr><td><code>Delete</code></td><td>删除选中节点</td></tr>
                <tr><td><code>Ctrl+C</code></td><td>复制节点</td></tr>
                <tr><td><code>Ctrl+V</code></td><td>粘贴节点</td></tr>
                <tr><td><code>Ctrl+Z</code></td><td>撤销</td></tr>
                <tr><td><code>Ctrl+Shift+Z</code></td><td>重做</td></tr>
                <tr><td><code>空格+拖拽</code></td><td>平移画布</td></tr>
                <tr><td><code>滚轮</code></td><td>缩放</td></tr>
                <tr><td><code>Escape</code></td><td>取消选择/关闭弹窗</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>14. 使用技巧</h4>
            <ul>
                <li>使用<strong>拖拽到空白画布</strong>最快构建节点链。</li>
                <li>不确定能连什么时，开启<strong>"仅显示兼容"</strong>。</li>
                <li>连接节点前先查看<strong>输出数据结构</strong>。</li>
                <li>字段名不匹配时用 ${n('field-mapper')} 重命名。</li>
                <li>用 ${n('value-injector')} 添加默认值（width、height、seed）。</li>
                <li>用 ${n('json-path')} 做数组索引和切片：<code>$.arr[2]</code>、<code>$.arr[1,3]</code>、<code>$.arr[1:3]</code>。</li>
                <li>悬停画布上的节点可查看描述和 I/O 类型的提示窗口。</li>
                <li>随时用 EN/中 按钮切换语言。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>15. 常见问题</h4>
            <table>
                <tr><th>问题</th><th>解决方案</th></tr>
                <tr><td>节点显示红色错误</td><td>在结果面板查看错误。常见：模型未加载、缺少必填输入、类型不匹配。</td></tr>
                <tr><td>两个节点无法连接</td><td>类型不兼容。在属性面板查看 I/O 类型。需要时用 ${n('type-converter')}。</td></tr>
                <tr><td>下游收到空输入</td><td>字段名不匹配。查看上游"输出数据结构"，用 ${n('field-mapper')} 重命名。</td></tr>
                <tr><td>${n('chat')} 节点失败</td><td><code>messages</code> 是必填字段。设置为 <code>[{"role": "user", "content": "你的问题"}]</code>。</td></tr>
                <tr><td>模型加载超时</td><td>尝试更小模型或检查网络。超时限制 10 分钟。</td></tr>
                <tr><td>图片质量低</td><td>添加负面提示词："low quality, blurry, worst quality"。提高分辨率。</td></tr>
                <tr><td>提示词选择器（⊞）不插入</td><td>先点击目标输入框，再点击 ⊞，然后选择提示词。</td></tr>
                <tr><td>运行按钮无反应</td><td>强制刷新浏览器（Ctrl+Shift+R）清除缓存的 JS。</td></tr>
            </table>
        </div>
        `;
    }

    return { render };
})();
