/**
 * Guide — comprehensive user guide rendered into a modal.
 * Content is bilingual, switching based on the active language.
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
 *  9. Pipeline Combinations (detailed examples)
 * 10. Running Pipelines
 * 11. Saving & Loading
 * 12. Keyboard Shortcuts
 * 13. Tips & Tricks
 * 14. Troubleshooting
 */
const Guide = (() => {

    function render(targetId) {
        const el = document.getElementById(targetId);
        if (!el) return;

        const lang = I18n.getLang();
        el.innerHTML = lang === 'zh' ? _zhContent() : _enContent();
    }

    function _enContent() {
        return `
        <div class="guide-section">
            <h4>1. Overview</h4>
            <p>Mosaic Canvas is a visual pipeline editor for AI workflows. You compose multi-modal AI pipelines by dragging nodes onto a canvas, connecting them, configuring parameters, and running the entire pipeline with one click.</p>
            <div class="guide-tip">Supported node types: Image, Video, Text, Audio, Subtitle, Digital Human, Export, RAG, Consistency, and 7 helper domains (75+ nodes total).</div>
        </div>

        <div class="guide-section">
            <h4>2. Layout</h4>
            <table>
                <tr><th>Area</th><th>Description</th></tr>
                <tr><td>Left Sidebar</td><td>Node palette (tab: Nodes) and prompt library (tab: Prompts). Searchable, grouped by domain.</td></tr>
                <tr><td>Center Canvas</td><td>Main workspace. Drag nodes here, connect them, pan and zoom.</td></tr>
                <tr><td>Right Sidebar</td><td>Properties panel for the selected node. Shows all parameters, I/O types, and output data structure.</td></tr>
                <tr><td>Bottom Panel</td><td>Pipeline input (key-value pairs for source nodes) and execution results (streamed per-node).</td></tr>
                <tr><td>Top Toolbar</td><td>Run, Save, Load, Auto-layout, Language switch, Templates, Shortcuts, Guide.</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. Adding Nodes</h4>
            <ul>
                <li><strong>From palette</strong>: Click a node in the left sidebar — it appears at the center of the canvas.</li>
                <li><strong>Drag-to-create</strong>: Drag from a node's output port (right side) to empty canvas. A popup shows only <em>compatible</em> nodes. Click one to create it and auto-connect.</li>
                <li><strong>Search</strong>: Type in the search box to filter nodes by name or description.</li>
                <li><strong>Compatible only</strong>: Toggle this checkbox to show only nodes compatible with the selected node's output type.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>4. Connecting Nodes</h4>
            <p>Connections enforce type compatibility. Drag from an output port (right circle) to an input port (left circle).</p>
            <ul>
                <li><strong>Green port</strong> = compatible, connection allowed.</li>
                <li><strong>Red port</strong> = type mismatch, connection blocked.</li>
                <li><strong>Wildcard</strong>: Nodes with input type <code>mosaic</code> accept any connection.</li>
            </ul>
            <div class="guide-tip">Tip: Select a node, then toggle "Compatible only" in the palette to see only nodes it can connect to.</div>
            <p>Compatible type pairs (partial list):</p>
            <table>
                <tr><th>Output</th><th>Accepts Input</th></tr>
                <tr><td>text</td><td>text, image, audio, video, document, json, rag_query_result</td></tr>
                <tr><td>image</td><td>image, video, avatar, json</td></tr>
                <tr><td>audio</td><td>audio, text, subtitle, json</td></tr>
                <tr><td>video</td><td>video, image, json</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>5. Configuring Parameters</h4>
            <p>Click a node to open its properties in the right sidebar. Parameters are unified — both constructor and runtime fields appear in one list.</p>
            <ul>
                <li><strong>Required</strong> fields are marked with <code>*</code> and a red badge.</li>
                <li><strong>Advanced</strong> parameters are collapsed by default — click "Advanced Parameters" to expand.</li>
                <li><strong>Modified</strong> values show a blue <code>●</code> badge. Click the reset button (↺) to restore defaults.</li>
                <li><strong>JSON fields</strong> (messages, labels, prompts, etc.) use a textarea with format hints.</li>
                <li><strong>Prompt fields</strong> (prompt, negative_prompt, instruction, text) have a <code>⊞</code> button to open the prompt library picker.</li>
            </ul>
            <div class="guide-tip">Prompt fields use a multi-line textarea for easy editing of long prompts. Click <code>⊞</code> to insert snippets from the prompt library at cursor position.</div>
        </div>

        <div class="guide-section">
            <h4>6. Output Data Structure</h4>
            <p>Each node's properties panel includes an <strong>"Output Data Structure"</strong> section that describes what fields the node produces. This is essential for understanding how to connect nodes.</p>
            <table>
                <tr><th>Node</th><th>Key Output Fields</th></tr>
                <tr><td>text-to-image</td><td><code>image</code> (PIL Image)</td></tr>
                <tr><td>chat / text-generator</td><td><code>text</code> (string), <code>response</code> (string)</td></tr>
                <tr><td>tts</td><td><code>waveform</code> (numpy array), <code>sample_rate</code> (int)</td></tr>
                <tr><td>text-to-video</td><td><code>frames</code> (list of Images), <code>fps</code> (int)</td></tr>
                <tr><td>subtitle-generator</td><td><code>segments</code> (list of {start, end, text})</td></tr>
                <tr><td>retriever</td><td><code>results</code> (list), <code>context</code> (string), <code>rag_query_result</code> (dict)</td></tr>
            </table>
            <div class="guide-tip">When connecting nodes, the downstream node receives all output fields from upstream nodes via <strong>MosaicData</strong> (a key-value container). The downstream node reads the fields it needs by name.</div>
        </div>

        <div class="guide-section">
            <h4>7. Data Flow & Field Mapping</h4>
            <p>When nodes are connected, data flows through <strong>MosaicData</strong> — a dictionary-like container that carries all fields from upstream to downstream. The downstream node reads the fields it needs by name.</p>
            <p><strong>Problem</strong>: Sometimes the upstream node's output field name doesn't match what the downstream node expects. For example:</p>
            <ul>
                <li><code>chat</code> outputs <code>text</code>, but <code>text-to-video</code> expects <code>prompt</code></li>
                <li><code>translator</code> outputs <code>translation</code>, but <code>tts</code> expects <code>text</code></li>
            </ul>
            <p><strong>Solution</strong>: Use the <strong>Field Mapper</strong> helper node between them to rename/alias fields.</p>
            <table>
                <tr><th>Helper Node</th><th>Use Case</th></tr>
                <tr><td><code>field-mapper</code></td><td>Rename fields: <code>{"text": "prompt"}</code> maps <code>text</code> → <code>prompt</code></td></tr>
                <tr><td><code>value-injector</code></td><td>Inject additional static values (e.g., default width/height)</td></tr>
                <tr><td><code>type-converter</code></td><td>Convert types: <code>{"count": "int"}</code> forces string→int</td></tr>
                <tr><td><code>json-builder</code></td><td>Build structured JSON from fields: <code>{"query": "prompt"}</code></td></tr>
                <tr><td><code>template-renderer</code></td><td>Render Jinja2 templates: <code>A {{ field }} image</code></td></tr>
            </table>
            <div class="guide-tip"><strong>Example</strong>: To connect <code>chat</code> → <code>text-to-image</code>, add a <code>field-mapper</code> between them with <code>mappings = {"text": "prompt"}</code>. The chat's <code>text</code> output becomes <code>prompt</code> input for text-to-image.</div>
        </div>

        <div class="guide-section">
            <h4>8. Prompt Library</h4>
            <p>The Prompts tab provides reusable prompt snippets organized by category. Each category is a separate JSON file, loaded on demand when expanded.</p>
            <p>Available categories: Characters, Scenes, Objects, Styles, Mood, Animals, Architecture, Effects, Photography, Fantasy/Sci-Fi, and <strong>Negative Prompts</strong>.</p>
            <ul>
                <li><strong>Panel mode</strong>: Switch to the "Prompts" tab, click a category to expand and load, search or browse, click a chip to insert into the focused input field.</li>
                <li><strong>Inline mode</strong>: Click the <code>⊞</code> button next to any prompt/negative_prompt field. A compact popover appears with searchable prompts.</li>
                <li><strong>Negative prompts</strong>: The "Negative Prompts" category provides common items like <code>low quality</code>, <code>bad anatomy</code>, <code>blurry</code>, <code>extra fingers</code>, etc. Use these in the <code>negative_prompt</code> field.</li>
            </ul>
            <div class="guide-tip"><strong>Custom prompts</strong>: Add JSON files to <code>data/prompts/</code> — one file per category. Auto-discovered, loaded on demand. Format:
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">{
  "id": "my_category",
  "name": "我的分类", "name_en": "My Category",
  "icon": "★", "version": "1.0",
  "subcategories": [{
    "id": "sub_id",
    "name": "子类", "name_en": "Subcategory",
    "items": [
      { "text": "prompt text", "label": "显示名", "label_en": "Label" }
    ]
  }]
}</pre>
            </div>
        </div>

        <div class="guide-section">
            <h4>9. Pipeline Combinations</h4>
            <p>Here are common pipeline patterns with step-by-step instructions.</p>

            <p><strong>9.1 Simple Text-to-Image</strong></p>
            <ul>
                <li>Add <code>text-to-image</code> node</li>
                <li>In the bottom panel, set pipeline input: <code>prompt</code> = "a cat sitting on a windowsill"</li>
                <li>Optionally set <code>negative_prompt</code> = "low quality, blurry, deformed"</li>
                <li>Click Run — the generated image appears in the Results panel</li>
            </ul>

            <p><strong>9.2 Chat → Field Mapper → Text-to-Image</strong></p>
            <p>This pipeline uses an LLM to generate a prompt, then passes it to image generation.</p>
            <ul>
                <li>Add <code>chat</code> node → set <code>instruction</code>: "Describe a beautiful sunset over the ocean in one sentence"</li>
                <li>Add <code>field-mapper</code> node → set <code>mappings</code>: <code>{"text": "prompt"}</code></li>
                <li>Add <code>text-to-image</code> node</li>
                <li>Connect: <code>chat</code> → <code>field-mapper</code> → <code>text-to-image</code></li>
                <li>The chat outputs <code>text</code>, the mapper renames it to <code>prompt</code>, which text-to-image reads</li>
            </ul>
            <div class="guide-tip">Check each node's "Output Data Structure" section in the properties panel to see what fields it produces. This helps you determine the correct mapping.</div>

            <p><strong>9.3 TTS → Lip Syncer (Audio-driven Video)</strong></p>
            <ul>
                <li>Add <code>tts</code> node → set <code>text</code>: "Hello, welcome to Mosaic Canvas"</li>
                <li>Add <code>lip-syncer</code> node → it needs <code>waveform</code> (from tts) and an avatar image</li>
                <li>Connect: <code>tts</code> → <code>lip-syncer</code></li>
                <li>Set lip-syncer's <code>method</code> (e.g., wav2lip) and provide a face image via pipeline input <code>image</code></li>
            </ul>

            <p><strong>9.4 Video Processing: Extract → Process → Encode</strong></p>
            <ul>
                <li>Add <code>frame-extractor</code> → outputs <code>frames</code> (list of images)</li>
                <li>Add <code>upscaler</code> → processes each frame's <code>image</code></li>
                <li>Add <code>video-encoder</code> → combines <code>frames</code> + <code>fps</code> into a video file</li>
                <li>Connect: <code>frame-extractor</code> → <code>upscaler</code> → <code>video-encoder</code></li>
            </ul>

            <p><strong>9.5 RAG Pipeline: Document → Retrieve → Chat</strong></p>
            <ul>
                <li>Add <code>document-parser</code> → outputs <code>text</code> from a PDF/document</li>
                <li>Add <code>vector-indexer</code> → indexes the text into a vector store</li>
                <li>Add <code>retriever</code> → outputs <code>context</code> + <code>rag_query_result</code></li>
                <li>Add <code>field-mapper</code> → map <code>context</code> to <code>instruction</code> or use template-renderer</li>
                <li>Add <code>chat</code> → uses the retrieved context to answer questions</li>
            </ul>

            <p><strong>9.6 Image-to-Image with Negative Prompts</strong></p>
            <ul>
                <li>Add <code>image-to-image</code> node</li>
                <li>Set <code>prompt</code>: "transform into oil painting style"</li>
                <li>Set <code>negative_prompt</code>: use the ⊞ button to pick "blurry", "low quality", "cartoon" from the Negative Prompts category</li>
                <li>Provide input image via pipeline input <code>image</code></li>
                <li>Click Run</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>10. Running Pipelines</h4>
            <ul>
                <li>Set pipeline input values in the bottom-left panel (key-value pairs for source nodes).</li>
                <li>Click the <strong>Run</strong> button (▶) in the toolbar.</li>
                <li><strong>Results stream in real-time</strong>: each node's output appears immediately when it completes — no need to wait for the entire pipeline.</li>
                <li>Node status indicators on the canvas show: idle (gray), running (blue pulse), success (green ✓), error (red ✗).</li>
                <li>The status bar shows the current executing node and elapsed time.</li>
                <li>Click a result card's header to collapse/expand its output.</li>
            </ul>
            <div class="guide-tip">If a node fails, the pipeline stops (fail-fast). Check the error message in the red node's result card. Fix the issue and re-run.</div>
        </div>

        <div class="guide-section">
            <h4>11. Saving & Loading</h4>
            <ul>
                <li><strong>Save</strong>: Click the Save button to download the pipeline as a JSON file.</li>
                <li><strong>Load</strong>: Click Load and select a previously saved JSON file.</li>
                <li><strong>Templates</strong>: Click the Templates button for pre-built example pipelines.</li>
                <li><strong>Export Python</strong>: Click Export to generate a standalone Python script that runs the same pipeline.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>12. Keyboard Shortcuts</h4>
            <table>
                <tr><th>Key</th><th>Action</th></tr>
                <tr><td><code>Delete</code></td><td>Delete selected node</td></tr>
                <tr><td><code>Ctrl+C</code></td><td>Copy selected node</td></tr>
                <tr><td><code>Ctrl+V</code></td><td>Paste copied node</td></tr>
                <tr><td><code>Ctrl+Z</code></td><td>Undo</td></tr>
                <tr><td><code>Ctrl+Shift+Z</code></td><td>Redo</td></tr>
                <tr><td><code>Space+Drag</code></td><td>Pan canvas</td></tr>
                <tr><td><code>Scroll</code></td><td>Zoom in/out</td></tr>
                <tr><td><code>Escape</code></td><td>Deselect / close popups</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>13. Tips & Tricks</h4>
            <ul>
                <li>Use <strong>drag-to-empty-canvas</strong> for the fastest way to build a chain of compatible nodes.</li>
                <li>Toggle <strong>"Compatible only"</strong> when you're not sure what can connect next.</li>
                <li>Use the <strong>Prompt Library</strong> ⊞ button to quickly compose rich prompts — including negative prompts.</li>
                <li><strong>Check the Output Data Structure</strong> in the properties panel to understand what each node produces before connecting.</li>
                <li>Use <strong>field-mapper</strong> whenever field names don't match between upstream and downstream nodes.</li>
                <li><strong>Hover</strong> over a parameter's ⓘ icon to see its help text.</li>
                <li>Switch language anytime with the EN/中 button in the toolbar.</li>
                <li>Use <strong>value-injector</strong> to add default values (like width, height, seed) without source nodes.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>14. Troubleshooting</h4>
            <table>
                <tr><th>Problem</th><th>Solution</th></tr>
                <tr><td>Node shows red error after running</td><td>Check the error message in the Results panel. Common causes: model not loaded, missing required input, type mismatch.</td></tr>
                <tr><td>Cannot connect two nodes</td><td>Types are incompatible. Check I/O types in the properties panel. Use <code>type-converter</code> or check the compatibility table above.</td></tr>
                <tr><td>Downstream node gets empty input</td><td>Field name mismatch. Check upstream node's "Output Data Structure" and use <code>field-mapper</code> to rename fields.</td></tr>
                <tr><td>Model loading timeout</td><td>The model may be too large or network is slow. Try a smaller model or check your connection. Timeout is 10 minutes.</td></tr>
                <tr><td>Generated image is low quality</td><td>Add negative prompts: "low quality, blurry, worst quality". Increase resolution if possible.</td></tr>
                <tr><td>Prompt picker (⊞) not inserting text</td><td>Make sure the target input field is focused. Click the field first, then click ⊞, then select a prompt.</td></tr>
            </table>
        </div>
        `;
    }

    function _zhContent() {
        return `
        <div class="guide-section">
            <h4>1. 概述</h4>
            <p>Mosaic Canvas 是一个可视化 AI 流水线编辑器。通过拖拽节点到画布、连接节点、配置参数，一键运行整个多模态 AI 流水线。</p>
            <div class="guide-tip">支持的节点类型：图像、视频、文本、音频、字幕、数字人、导出、RAG、一致性，以及 7 个辅助工具域（共 75+ 个节点）。</div>
        </div>

        <div class="guide-section">
            <h4>2. 界面布局</h4>
            <table>
                <tr><th>区域</th><th>说明</th></tr>
                <tr><td>左侧栏</td><td>节点面板（标签：节点）和提示词库（标签：提示词）。可搜索，按域分组。</td></tr>
                <tr><td>中央画布</td><td>主工作区。在此拖入节点、连接节点、平移和缩放。</td></tr>
                <tr><td>右侧栏</td><td>选中节点的属性面板。显示所有参数、I/O 类型和输出数据结构。</td></tr>
                <tr><td>底部面板</td><td>流水线输入（源节点的键值对）和执行结果（逐节点流式展示）。</td></tr>
                <tr><td>顶部工具栏</td><td>运行、保存、加载、自动布局、语言切换、模板、快捷键、使用指南。</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. 添加节点</h4>
            <ul>
                <li><strong>从面板添加</strong>：点击左侧栏中的节点 — 它会出现在画布中央。</li>
                <li><strong>拖拽创建</strong>：从节点的输出端口（右侧）拖拽到空白画布。弹出菜单只显示<em>兼容</em>节点。点击即可创建节点并自动连线。</li>
                <li><strong>搜索</strong>：在搜索框中输入关键词，按名称或描述过滤节点。</li>
                <li><strong>仅显示兼容</strong>：勾选此选项，只显示与选中节点输出类型兼容的节点。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>4. 连接节点</h4>
            <p>连接遵循类型兼容规则。从输出端口（右侧圆点）拖拽到输入端口（左侧圆点）。</p>
            <ul>
                <li><strong>绿色端口</strong> = 兼容，允许连接。</li>
                <li><strong>红色端口</strong> = 类型不匹配，连接被阻止。</li>
                <li><strong>通配类型</strong>：输入类型为 <code>mosaic</code> 的节点接受任何连接。</li>
            </ul>
            <div class="guide-tip">提示：选中节点后，在面板中开启"仅显示兼容"，即可只看到它可以连接的节点。</div>
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
            <p>点击节点打开右侧属性面板。参数已统一 — 构造参数和运行时字段在同一个列表中。</p>
            <ul>
                <li><strong>必填</strong>字段标记 <code>*</code> 和红色标签。</li>
                <li><strong>高级参数</strong>默认折叠 — 点击"高级参数"展开。</li>
                <li><strong>已修改</strong>的值显示蓝色 <code>●</code> 标签。点击重置按钮（↺）恢复默认值。</li>
                <li><strong>JSON 字段</strong>（messages、labels、prompts 等）使用多行文本框，带格式提示。</li>
                <li><strong>提示词字段</strong>（prompt、negative_prompt、instruction、text）有 <code>⊞</code> 按钮可打开提示词库选择器。</li>
            </ul>
            <div class="guide-tip">提示词字段使用多行文本框，方便编辑长提示词。点击 <code>⊞</code> 可在光标位置插入提示词库中的片段。</div>
        </div>

        <div class="guide-section">
            <h4>6. 输出数据结构</h4>
            <p>每个节点的属性面板中都有一个<strong>"输出数据结构"</strong>部分，描述该节点产出的字段。这对理解如何连接节点至关重要。</p>
            <table>
                <tr><th>节点</th><th>关键输出字段</th></tr>
                <tr><td>text-to-image</td><td><code>image</code>（PIL 图像）</td></tr>
                <tr><td>chat / text-generator</td><td><code>text</code>（字符串），<code>response</code>（字符串）</td></tr>
                <tr><td>tts</td><td><code>waveform</code>（numpy 数组），<code>sample_rate</code>（整数）</td></tr>
                <tr><td>text-to-video</td><td><code>frames</code>（图像列表），<code>fps</code>（整数）</td></tr>
                <tr><td>subtitle-generator</td><td><code>segments</code>（{start, end, text} 列表）</td></tr>
                <tr><td>retriever</td><td><code>results</code>（列表），<code>context</code>（字符串），<code>rag_query_result</code>（字典）</td></tr>
            </table>
            <div class="guide-tip">连接节点时，下游节点通过 <strong>MosaicData</strong>（键值对容器）接收上游节点的所有输出字段。下游节点按名称读取所需字段。</div>
        </div>

        <div class="guide-section">
            <h4>7. 数据流与字段映射</h4>
            <p>节点连接后，数据通过 <strong>MosaicData</strong> 流动 — 这是一个类似字典的容器，携带所有字段从上游传递到下游。下游节点按名称读取所需字段。</p>
            <p><strong>问题</strong>：有时上游节点的输出字段名与下游节点期望的名称不匹配。例如：</p>
            <ul>
                <li><code>chat</code> 输出 <code>text</code>，但 <code>text-to-video</code> 期望 <code>prompt</code></li>
                <li><code>translator</code> 输出 <code>translation</code>，但 <code>tts</code> 期望 <code>text</code></li>
            </ul>
            <p><strong>解决方案</strong>：在两者之间使用 <strong>字段映射（field-mapper）</strong> 辅助节点来重命名/别名字段。</p>
            <table>
                <tr><th>辅助节点</th><th>用途</th></tr>
                <tr><td><code>field-mapper</code></td><td>重命名字段：<code>{"text": "prompt"}</code> 将 <code>text</code> → <code>prompt</code></td></tr>
                <tr><td><code>value-injector</code></td><td>注入额外静态值（如默认 width/height）</td></tr>
                <tr><td><code>type-converter</code></td><td>类型转换：<code>{"count": "int"}</code> 将字符串→整数</td></tr>
                <tr><td><code>json-builder</code></td><td>从字段构建结构化 JSON：<code>{"query": "prompt"}</code></td></tr>
                <tr><td><code>template-renderer</code></td><td>渲染 Jinja2 模板：<code>A {{ field }} image</code></td></tr>
            </table>
            <div class="guide-tip"><strong>示例</strong>：要连接 <code>chat</code> → <code>text-to-image</code>，在中间加一个 <code>field-mapper</code>，设置 <code>mappings = {"text": "prompt"}</code>。chat 的 <code>text</code> 输出就会变成 text-to-image 的 <code>prompt</code> 输入。</div>
        </div>

        <div class="guide-section">
            <h4>8. 提示词库</h4>
            <p>左侧栏"提示词"标签提供可复用的提示词片段，按分类组织。每个大类是一个独立的 JSON 文件，展开时按需加载。</p>
            <p>可用分类：人物、场景、物体、风格、氛围、动物、建筑、特效、摄影、奇幻科幻，以及<strong>负面提示词</strong>。</p>
            <ul>
                <li><strong>面板模式</strong>：切换到"提示词"标签，点击大类展开并加载内容，搜索或浏览，点击标签将文本插入当前聚焦的输入框。</li>
                <li><strong>内联模式</strong>：点击属性面板中 prompt/negative_prompt 字段旁的 <code>⊞</code> 按钮，弹出可搜索的提示词选择器。</li>
                <li><strong>负面提示词</strong>：在"负面提示词"分类中提供常用项，如 <code>low quality</code>（低质量）、<code>bad anatomy</code>（解剖错误）、<code>blurry</code>（模糊）、<code>extra fingers</code>（多余手指）等。在 <code>negative_prompt</code> 字段中使用。</li>
            </ul>
            <div class="guide-tip"><strong>自定义提示词</strong>：将 JSON 文件放入 <code>data/prompts/</code> — 每个文件对应一个大类。系统自动发现并按需加载。格式：
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">{
  "id": "my_category",
  "name": "我的分类", "name_en": "My Category",
  "icon": "★", "version": "1.0",
  "subcategories": [{
    "id": "sub_id",
    "name": "子类", "name_en": "Subcategory",
    "items": [
      { "text": "提示词文本", "label": "显示名", "label_en": "Label" }
    ]
  }]
}</pre>
            </div>
        </div>

        <div class="guide-section">
            <h4>9. 流水线组合示例</h4>
            <p>以下是常见流水线模式的详细操作步骤。</p>

            <p><strong>9.1 简单文生图</strong></p>
            <ul>
                <li>添加 <code>text-to-image</code> 节点</li>
                <li>在底部面板设置流水线输入：<code>prompt</code> = "一只猫坐在窗台上"</li>
                <li>可选设置 <code>negative_prompt</code> = "low quality, blurry, deformed"</li>
                <li>点击运行 — 生成的图片会出现在结果面板</li>
            </ul>

            <p><strong>9.2 Chat → 字段映射 → 文生图</strong></p>
            <p>这个流水线用 LLM 生成提示词，再传给图像生成。</p>
            <ul>
                <li>添加 <code>chat</code> 节点 → 设置 <code>instruction</code>："用一句话描述海上美丽的日落"</li>
                <li>添加 <code>field-mapper</code> 节点 → 设置 <code>mappings</code>：<code>{"text": "prompt"}</code></li>
                <li>添加 <code>text-to-image</code> 节点</li>
                <li>连接：<code>chat</code> → <code>field-mapper</code> → <code>text-to-image</code></li>
                <li>chat 输出 <code>text</code>，映射器将其重命名为 <code>prompt</code>，text-to-image 读取该字段</li>
            </ul>
            <div class="guide-tip">在属性面板中查看每个节点的"输出数据结构"，了解它产出的字段，从而确定正确的映射关系。</div>

            <p><strong>9.3 TTS → 唇形同步（音频驱动视频）</strong></p>
            <ul>
                <li>添加 <code>tts</code> 节点 → 设置 <code>text</code>："你好，欢迎来到 Mosaic Canvas"</li>
                <li>添加 <code>lip-syncer</code> 节点 → 它需要 <code>waveform</code>（来自 tts）和一张人脸图像</li>
                <li>连接：<code>tts</code> → <code>lip-syncer</code></li>
                <li>设置 lip-syncer 的 <code>method</code>（如 wav2lip），通过流水线输入 <code>image</code> 提供人脸图</li>
            </ul>

            <p><strong>9.4 视频处理：抽取 → 处理 → 编码</strong></p>
            <ul>
                <li>添加 <code>frame-extractor</code> → 输出 <code>frames</code>（图像列表）</li>
                <li>添加 <code>upscaler</code> → 处理每帧的 <code>image</code></li>
                <li>添加 <code>video-encoder</code> → 将 <code>frames</code> + <code>fps</code> 合成为视频文件</li>
                <li>连接：<code>frame-extractor</code> → <code>upscaler</code> → <code>video-encoder</code></li>
            </ul>

            <p><strong>9.5 RAG 流水线：文档 → 检索 → 对话</strong></p>
            <ul>
                <li>添加 <code>document-parser</code> → 从 PDF/文档中提取 <code>text</code></li>
                <li>添加 <code>vector-indexer</code> → 将文本索引到向量存储</li>
                <li>添加 <code>retriever</code> → 输出 <code>context</code> + <code>rag_query_result</code></li>
                <li>添加 <code>field-mapper</code> → 将 <code>context</code> 映射为 <code>instruction</code>，或用 template-renderer 组合</li>
                <li>添加 <code>chat</code> → 使用检索到的上下文回答问题</li>
            </ul>

            <p><strong>9.6 图生图 + 负面提示词</strong></p>
            <ul>
                <li>添加 <code>image-to-image</code> 节点</li>
                <li>设置 <code>prompt</code>："转换为油画风格"</li>
                <li>设置 <code>negative_prompt</code>：点击 ⊞ 从"负面提示词"分类选择 "模糊"、"低质量"、"卡通风格" 等</li>
                <li>通过流水线输入 <code>image</code> 提供输入图像</li>
                <li>点击运行</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>10. 运行流水线</h4>
            <ul>
                <li>在底部左侧面板设置流水线输入值（源节点的键值对）。</li>
                <li>点击工具栏的 <strong>运行</strong> 按钮（▶）。</li>
                <li><strong>结果实时流式展示</strong>：每个节点完成后立即显示其输出 — 无需等待整个流水线完成。</li>
                <li>画布上的节点状态指示：空闲（灰色）、运行中（蓝色脉冲）、成功（绿色 ✓）、错误（红色 ✗）。</li>
                <li>状态栏显示当前执行的节点和已用时间。</li>
                <li>点击结果卡片标题可折叠/展开其输出内容。</li>
            </ul>
            <div class="guide-tip">如果节点失败，流水线会停止（快速失败机制）。在红色节点的结果卡片中查看错误信息，修复后重新运行。</div>
        </div>

        <div class="guide-section">
            <h4>11. 保存与加载</h4>
            <ul>
                <li><strong>保存</strong>：点击保存按钮，将流水线下载为 JSON 文件。</li>
                <li><strong>加载</strong>：点击加载按钮，选择之前保存的 JSON 文件。</li>
                <li><strong>模板</strong>：点击模板按钮，选择预置的示例流水线。</li>
                <li><strong>导出 Python</strong>：点击导出按钮，生成可独立运行的 Python 脚本。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>12. 键盘快捷键</h4>
            <table>
                <tr><th>按键</th><th>功能</th></tr>
                <tr><td><code>Delete</code></td><td>删除选中节点</td></tr>
                <tr><td><code>Ctrl+C</code></td><td>复制选中节点</td></tr>
                <tr><td><code>Ctrl+V</code></td><td>粘贴已复制的节点</td></tr>
                <tr><td><code>Ctrl+Z</code></td><td>撤销</td></tr>
                <tr><td><code>Ctrl+Shift+Z</code></td><td>重做</td></tr>
                <tr><td><code>空格+拖拽</code></td><td>平移画布</td></tr>
                <tr><td><code>滚轮</code></td><td>缩放</td></tr>
                <tr><td><code>Escape</code></td><td>取消选择 / 关闭弹窗</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>13. 使用技巧</h4>
            <ul>
                <li>使用<strong>拖拽到空白画布</strong>是构建兼容节点链最快的方式。</li>
                <li>不确定下一步能连接什么时，开启<strong>"仅显示兼容"</strong>。</li>
                <li>使用<strong>提示词库</strong>的 ⊞ 按钮快速组合丰富提示词 — 包括负面提示词。</li>
                <li>连接节点前，先查看属性面板中的<strong>输出数据结构</strong>，了解每个节点产出什么字段。</li>
                <li>当上下游字段名不匹配时，使用 <strong>field-mapper</strong> 进行重命名。</li>
                <li><strong>悬停</strong>参数的 ⓘ 图标查看帮助文本。</li>
                <li>随时用工具栏的 EN/中 按钮切换语言。</li>
                <li>使用 <strong>value-injector</strong> 添加默认值（如 width、height、seed），无需源节点。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>14. 常见问题</h4>
            <table>
                <tr><th>问题</th><th>解决方案</th></tr>
                <tr><td>节点运行后显示红色错误</td><td>在结果面板查看错误信息。常见原因：模型未加载、缺少必填输入、类型不匹配。</td></tr>
                <tr><td>两个节点无法连接</td><td>类型不兼容。在属性面板查看 I/O 类型。使用 <code>type-converter</code> 或查看上方兼容性表。</td></tr>
                <tr><td>下游节点收到的输入为空</td><td>字段名不匹配。查看上游节点的"输出数据结构"，使用 <code>field-mapper</code> 重命名字段。</td></tr>
                <tr><td>模型加载超时</td><td>模型可能太大或网络慢。尝试更小的模型或检查网络连接。超时限制为 10 分钟。</td></tr>
                <tr><td>生成的图片质量低</td><td>添加负面提示词："low quality, blurry, worst quality"。如可能，提高分辨率。</td></tr>
                <tr><td>提示词选择器（⊞）不插入文本</td><td>确保目标输入框已聚焦。先点击输入框，再点击 ⊞，然后选择提示词。</td></tr>
            </table>
        </div>
        `;
    }

    return { render };
})();
