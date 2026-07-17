/**
 * Guide — comprehensive user guide rendered into a modal.
 * Content is bilingual, switching based on the active language.
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
                <tr><td>Right Sidebar</td><td>Properties panel for the selected node. Shows all parameters with type badges, defaults, and help text.</td></tr>
                <tr><td>Bottom Panel</td><td>Pipeline input (key-value pairs for source nodes) and execution results (logs, outputs).</td></tr>
                <tr><td>Top Toolbar</td><td>Run, Save, Load, Auto-layout, Language switch, Templates, Shortcuts, Guide.</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. Adding Nodes</h4>
            <ul>
                <li><strong>From palette</strong>: Click a node in the left sidebar — it appears at the center of the canvas.</li>
                <li><strong>Drag-to-create</strong>: Drag from a node's output port (right side) to empty canvas. A popup shows only <em>compatible</em> nodes. Click one to create it and auto-connect.</li>
                <li><strong>Search</strong>: Type in the search box to filter nodes by name or description.</li>
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
            </ul>
        </div>

        <div class="guide-section">
            <h4>6. Prompt Library</h4>
            <p>The Prompts tab in the left sidebar provides reusable prompt snippets organized by category (Characters, Scenes, Objects, Styles, Mood). Each category is a separate JSON file, loaded on demand when expanded.</p>
            <ul>
                <li><strong>Panel mode</strong>: Switch to the "Prompts" tab, click a category to expand and load its content, search or browse, click a chip to insert it into the currently focused input field.</li>
                <li><strong>Inline mode</strong>: Click the <code>⊞</code> button next to any prompt field in the properties panel. A compact popover appears with searchable prompts.</li>
            </ul>
            <div class="guide-tip"><strong>Custom prompts</strong>: Add JSON files to <code>data/prompts/</code> — one file per category. Each file is auto-discovered and loaded on demand. File format:
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">// data/prompts/my_category.json
{
  "id": "my_category",
  "name": "我的分类",
  "name_en": "My Category",
  "icon": "★",
  "version": "1.0",
  "subcategories": [{
    "id": "my_sub",
    "name": "子类",
    "name_en": "Subcategory",
    "items": [
      { "text": "actual prompt text", "label": "显示名", "label_en": "Label" }
    ]
  }]
}</pre>
            </div>
        </div>

        <div class="guide-section">
            <h4>7. Running Pipelines</h4>
            <ul>
                <li>Set pipeline input values in the bottom-left panel (key-value pairs for source nodes).</li>
                <li>Click the <strong>Run</strong> button (▶) in the toolbar.</li>
                <li>Watch the Results panel for real-time logs and outputs.</li>
                <li>Node status indicators show: idle (gray), running (blue pulse), success (green ✓), error (red ✗).</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>8. Saving & Loading</h4>
            <ul>
                <li><strong>Save</strong>: Click the Save button to download the pipeline as a JSON file.</li>
                <li><strong>Load</strong>: Click Load and select a previously saved JSON file.</li>
                <li><strong>Templates</strong>: Click the Templates button for pre-built example pipelines.</li>
                <li><strong>Export Python</strong>: Click Export to generate a standalone Python script.</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>9. Keyboard Shortcuts</h4>
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
            <h4>10. Tips & Tricks</h4>
            <ul>
                <li>Use <strong>drag-to-empty-canvas</strong> for the fastest way to build a chain of compatible nodes.</li>
                <li>Toggle <strong>"Compatible only"</strong> when you're not sure what can connect next.</li>
                <li>Use the <strong>Prompt Library</strong> to quickly compose rich prompts from reusable snippets.</li>
                <li><strong>Hover</strong> over a parameter's ⓘ icon to see its help text.</li>
                <li>Switch language anytime with the EN/中 button in the toolbar.</li>
            </ul>
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
                <tr><td>右侧栏</td><td>选中节点的属性面板。显示所有参数，含类型标签、默认值和帮助文本。</td></tr>
                <tr><td>底部面板</td><td>流水线输入（源节点的键值对）和执行结果（日志、输出）。</td></tr>
                <tr><td>顶部工具栏</td><td>运行、保存、加载、自动布局、语言切换、模板、快捷键、使用指南。</td></tr>
            </table>
        </div>

        <div class="guide-section">
            <h4>3. 添加节点</h4>
            <ul>
                <li><strong>从面板添加</strong>：点击左侧栏中的节点 — 它会出现在画布中央。</li>
                <li><strong>拖拽创建</strong>：从节点的输出端口（右侧）拖拽到空白画布。弹出菜单只显示<em>兼容</em>节点。点击即可创建节点并自动连线。</li>
                <li><strong>搜索</strong>：在搜索框中输入关键词，按名称或描述过滤节点。</li>
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
            </ul>
        </div>

        <div class="guide-section">
            <h4>6. 提示词库</h4>
            <p>左侧栏的"提示词"标签提供可复用的提示词片段，按分类组织（人物、场景、物体、风格、氛围）。每个大类是一个独立的 JSON 文件，展开时按需加载。</p>
            <ul>
                <li><strong>面板模式</strong>：切换到"提示词"标签，点击大类展开并加载内容，搜索或浏览，点击标签将文本插入当前聚焦的输入框。</li>
                <li><strong>内联模式</strong>：点击属性面板中提示词字段旁的 <code>⊞</code> 按钮，弹出可搜索的提示词选择器。</li>
            </ul>
            <div class="guide-tip"><strong>自定义提示词</strong>：将 JSON 文件放入 <code>data/prompts/</code> — 每个文件对应一个大类。系统自动发现并按需加载。文件格式：
            <pre style="margin-top:6px;font-size:11px;background:var(--bg-2);padding:8px;border-radius:4px;overflow-x:auto">// data/prompts/my_category.json
{
  "id": "my_category",
  "name": "我的分类",
  "name_en": "My Category",
  "icon": "★",
  "version": "1.0",
  "subcategories": [{
    "id": "my_sub",
    "name": "子类",
    "name_en": "Subcategory",
    "items": [
      { "text": "实际提示词文本", "label": "显示名", "label_en": "Label" }
    ]
  }]
}</pre>
            </div>
        </div>

        <div class="guide-section">
            <h4>7. 运行流水线</h4>
            <ul>
                <li>在底部左侧面板设置流水线输入值（源节点的键值对）。</li>
                <li>点击工具栏的 <strong>运行</strong> 按钮（▶）。</li>
                <li>在结果面板查看实时日志和输出。</li>
                <li>节点状态指示：空闲（灰色）、运行中（蓝色脉冲）、成功（绿色 ✓）、错误（红色 ✗）。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>8. 保存与加载</h4>
            <ul>
                <li><strong>保存</strong>：点击保存按钮，将流水线下载为 JSON 文件。</li>
                <li><strong>加载</strong>：点击加载按钮，选择之前保存的 JSON 文件。</li>
                <li><strong>模板</strong>：点击模板按钮，选择预置的示例流水线。</li>
                <li><strong>导出 Python</strong>：点击导出按钮，生成可独立运行的 Python 脚本。</li>
            </ul>
        </div>

        <div class="guide-section">
            <h4>9. 键盘快捷键</h4>
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
            <h4>10. 使用技巧</h4>
            <ul>
                <li>使用<strong>拖拽到空白画布</strong>是构建兼容节点链最快的方式。</li>
                <li>不确定下一步能连接什么时，开启<strong>"仅显示兼容"</strong>。</li>
                <li>使用<strong>提示词库</strong>快速从可复用片段组合丰富提示词。</li>
                <li><strong>悬停</strong>参数的 ⓘ 图标查看帮助文本。</li>
                <li>随时用工具栏的 EN/中 按钮切换语言。</li>
            </ul>
        </div>
        `;
    }

    return { render };
})();
