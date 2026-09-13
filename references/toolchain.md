# 绘图工具链：作用、用法与验证

将“编写SVG → 结构检查 → 渲染 → 导出 → 视觉复查”视为能力流程。下面的Python、Sharp与浏览器方案是已执行过的可选实现，不是skill的前置环境。没有Node、浏览器或某个桌面应用时，仍可使用其他SVG编辑/渲染工具完成相同步骤；缺少实际渲染能力时只能交付已完成部分并说明未验证项。

版式和端口根据设计规范规划，并写成可复现参数；这些工具本身不负责决定漂亮的布局，也没有自动完成布线优化。

## 工具分工

| 工具 | 作用 | 输入 → 输出 | 使用边界 |
| --- | --- | --- | --- |
| Python标准库 `xml.etree.ElementTree` | 创建图元、文字、分组、marker；内嵌图标；保存SVG | 布局参数、关系记录、图标 → SVG | 不测量真实字体，不自动布局 |
| Node.js + Sharp | 实际渲染SVG，按物理尺寸和DPI导出PNG | SVG → PNG | 导出成功不代表布局正确 |
| Playwright + Chromium系列浏览器 | 浏览器渲染、文字与图标测量、矢量PDF导出 | SVG → PDF、浏览器截图、JSON | 该可选适配器使用Chromium；其他渲染路径不需要它。包围盒不等于字形轮廓 |
| `scripts/check_svg.py` | XML、ID、内部引用和常见外部依赖检查 | SVG → 终端/JSON报告 | 不检查布局和科学关系 |
| 按图编写的Python关系检查 | 检查边与端口、模块树、直角路径避障及压线 | 关系记录、SVG、测量JSON → 报告 | 需要按该图的数据结构实现；当前未提供通用自动布局/拓扑验证器 |
| Poppler `pdftoppm` / `pdfinfo` | 将PDF重新渲染，读取页数与页面尺寸 | PDF → 页面PNG、尺寸信息 | 页面图像还需实际查看 |
| Python Pillow / pypdf | 裁切放大、灰度和缩小预览；读取PNG密度、PDF文本和图像对象 | PNG/PDF → 检查图、统计 | 供验证使用，不用于把可编辑主图栅格化 |
| 图像查看工具 | 实际观察整图、局部和最终显示尺寸 | PNG → 视觉判断与修订 | 不能以统计报告替代这一步 |

## 1. 查找现有依赖

先检查用户指定工具、命令搜索路径和项目依赖。解释器、Node包、浏览器、字体和PDF检查工具分别探测，不能因为其中一项存在就假设其他项已安装。环境提供的依赖清单可以辅助查找，但不要求任何宿主专属接口。

以下命令示例使用POSIX shell；Windows可用PowerShell直接调用相同脚本与参数，解释器也可用 `py -3`。脚本以传入路径和当前项目为依据，不拼接系统特定的目录。Python脚本和示例使用Python 3.9及以上；Node适配器须使用所安装Sharp/Playwright版本支持的Node版本，不假定任意旧Node都可运行。

以下命令使用任务局部变量。把示意路径替换成实际发现的路径；不改写用户的HOME、CODEX_HOME或全局配置。

```bash
export FIGURE_SKILL="/path/to/paper-figure-generate-skill"
export FIGURE_PYTHON="/path/to/python3"
export FIGURE_NODE="/path/to/node"
export FIGURE_BROWSER="/path/to/installed/browser"
# 仅当包在其他位置时，给脚本传入 --node-modules "$FIGURE_NODE_MODULES"。
export FIGURE_NODE_MODULES="/path/to/node_modules"

"$FIGURE_PYTHON" -c 'import xml.etree.ElementTree; print("SVG builder ready")'
"$FIGURE_NODE" -e 'for (const m of ["sharp", "playwright"]) console.log(m, require.resolve(m))'
"$FIGURE_PYTHON" -c 'import PIL, pypdf; print("Optional QA libraries ready")'
```

Python标准库绘制不需要Pillow或pypdf；后两者只用于对应检查。Node适配器优先解析**调用者当前项目**已安装的包，再尝试skill目录的常规模块解析；`--node-modules DIR` 则明确指定包含包的目录，无需设置NODE_PATH。显式目录无所需包时直接报错，不偷偷转用本机其他缓存。上面的 `require.resolve` 命令用于检查当前项目依赖，外置包可通过对应脚本的显式目录参数验证。

Playwright包可导入不代表浏览器已安装：可通过 `--browser` 指定可执行文件，或通过 `--channel` 选择已安装的浏览器通道；省略时可读取调用者提供的 `FIGURE_BROWSER`，再尝试Playwright默认浏览器。没有品牌或系统路径假设，通道名由当前Playwright安装支持的范围决定。

缺少依赖时先检查已有运行时和替代工具，不默认全局安装软件。不把用户机器的绝对路径写进skill脚本。浏览器进程受执行环境权限控制，需要时按环境机制申请启动权限。

## 2. Python生成可编辑SVG

将每张图的生成程序保存为输出目录中的 `build_figure.py`。先确定设计说明，再集中定义画布、行列、模块、端口和颜色参数。节点调整后从参数重算边，避免只修改最终SVG中的单个坐标而使生成程序过时。

下面是可执行的语法示例，展示分组、文本和箭头；不是论文框架的版式模板：

```python
from pathlib import Path
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
root = ET.Element(f"{{{NS}}}svg", {
    "viewBox": "0 0 1200 400", "width": "180mm", "height": "60mm",
    "font-family": "sans-serif",
})

def add(parent, tag, **attrs):
    return ET.SubElement(parent, f"{{{NS}}}{tag}",
        {key.replace("_", "-"): str(value) for key, value in attrs.items()})

add(root, "rect", width=1200, height=400, fill="white")
defs = add(root, "defs")
marker = add(defs, "marker", id="arrow", viewBox="0 0 16 16",
    refX=13, refY=8, markerWidth=16, markerHeight=16,
    markerUnits="userSpaceOnUse", orient="auto")
add(marker, "path", d="M 1 2 L 13 8 L 1 14 Z", fill="#50646E")

for key, x, title in [("input", 80, "Input"), ("method", 720, "Method")]:
    group = add(root, "g", id=f"module-{key}", transform=f"translate({x} 120)")
    add(group, "rect", width=400, height=160, rx=12,
        fill="#E8EFF5", stroke="#607F98", stroke_width=2,
        data_role="node-boundary")
    add(group, "text", x=200, y=92, text_anchor="middle",
        font_size=32, fill="#29323A").text = title

add(root, "path", id="edge-input-method", d="M 480 200 L 720 200",
    fill="none", stroke="#50646E", stroke_width=3, marker_end="url(#arrow)")
ET.indent(root)
ET.ElementTree(root).write(Path("figure.svg"), encoding="utf-8", xml_declaration=True)
```

使用 `"$FIGURE_PYTHON" build_figure.py` 生成。ElementTree负责XML转义，文字放在 `.text` 中；不要将未经转义的标签拼接为XML字符串。

复用图标时用 `ET.parse(icon_path)` 读取，再复制图元到当前图的 `<g>`。按照 [SVG内嵌规范](svg-and-export.md#内嵌复用图标) 处理viewBox、缩放、颜色及所有ID引用；不能只保留文件路径。可用透明背景的Sharp渲染与alpha边界辅助计算视觉尺度，最终保留原始矢量path。复杂图标必须完整处理样式和定义，或明确拒绝不支持的结构。

## 3. 静态检查

```bash
"$FIGURE_PYTHON" "$FIGURE_SKILL/scripts/check_svg.py" figure.svg --output structure-check.json
```

退出码 `0`：支持范围内通过；`1`：有错误；`2`：存在需进一步检查的结构。修复失效引用、重复ID等问题，再渲染。完整边界见 [结构检查说明](svg-and-export.md#结构检查)。

## 4. Sharp导出PNG

使用随skill提供的 [render_png.cjs](../scripts/render_png.cjs)：

```bash
"$FIGURE_NODE" "$FIGURE_SKILL/scripts/render_png.cjs" figure.svg figure.png --width-mm 180 --dpi 300
```

- `--width-mm`：目标物理宽度；脚本按 `mm / 25.4 × DPI` 计算像素宽，按SVG自身比例保留高度。
- `--dpi`：默认为300，同时用于渲染和PNG密度元数据。
- 也可使用 `--width 1600` 直接指定像素宽，不能与 `--width-mm` 同时提供。用于临时预览时，物理尺寸不一定对应论文尺寸。
- 脚本创建输出父目录并打印实际像素尺寸；重新使用同一输出路径会更新该PNG。错误退出码为1。
- 两个Node适配器都接受 `--node-modules DIR`；不传时使用当前项目依赖。模块解析辅助文件 `scripts/node_support.cjs` 需与脚本一起携带。

显式像素尺寸、DPI和最终物理宽度必须一致。字体由环境实际提供；通用字体族也不能保证跨机器字形完全相同。按所用语言选择可用字体并实测，不能要求某一系统必然有Arial、Helvetica或特定中文字体。需要完全一致时按字体许可嵌入或另外提供文字轮廓副本，保留可编辑主文件。

## 5. 浏览器导出PDF并测量

使用 [export_browser.cjs](../scripts/export_browser.cjs)：

```bash
"$FIGURE_NODE" "$FIGURE_SKILL/scripts/export_browser.cjs" figure.svg \
  --out-dir qa --width-mm 180 --browser "$FIGURE_BROWSER" --padding 16
```

脚本读取SVG的viewBox，按目标宽度推算PDF高度，不固定画布比例。输出：

- `qa/figure.pdf`：零边距、无页眉页脚的浏览器PDF，开启背景打印。
- `qa/figure-browser.png`：浏览器对照截图，像素尺寸按viewBox，供对照，不是300DPI出版PNG。
- `qa/figure-geometry.json`：源SVG的SHA256、画布、浏览器版本、目标尺寸、模块及所有文字的包围盒、违规和覆盖不足信息。

同一路径会更新这些输出。`--browser` 与 `--channel` 二选一；两者省略时尝试调用者设置的 `FIGURE_BROWSER` 或Playwright默认浏览器。脚本不会下载浏览器或安装包。渲染时阻止外部网络请求，SVG本身仍须先通过静态检查；脚本按XML解析SVG，支持带命名空间前缀的根元素并拒绝动态内容。关键加载、测量和导出步骤具有30秒超时，超时会说明失败阶段。

先在内存中完成截图和PDF，再保存本轮输出；报告包含 `export_complete` 和 `status`。渲染失败时可能保留上次文件，应以本轮退出状态、源哈希和报告为准。所有脚本拒绝将输出写回输入文件，包括符号链接或硬链接别名。

### 测量约定

为了让模块检查生效，生成SVG时使用：

- 模块分组：`<g id="module-name">`。
- 模块边界：该分组直接子元素上的 `data-role="node-boundary"`。
- 特意接入边界的内部连接：`data-role="port-connection"`，单独做端口验证，豁免普通内容内边距检查。

脚本在字体加载完成后调用 `getBoundingClientRect()`，转换回根viewBox坐标，检查其余直接子元素与模块边界的距离。`--padding` 单位为**根SVG坐标单位**，按本图尺寸选择；标题、图标等可通过嵌套g作为一个内容单元。

输出中的 `textBoxes` 收集所有 `<text>`，包括分区标题、边标签与图例，供后续路径压线检查。脚本本身只测量模块包围盒，不自动检查文字与连线相交，也不推断分区标题应对齐在哪条基线。

退出码 `0`：已测量项目无违规；`1`：测量违规或执行错误；`2`：没有模块标记、非矩形/旋转边界、空模块或外部资源被阻止等覆盖不足，需要另行检查。即使存在测量违规也会保存已完成渲染的结果供查看；输出落盘失败可能留下部分文件，应检查命令状态。marker、描边、字形间隙与实际美观程度必须另检。

## 6. 复杂框架的关系检查

为具体图保留 `graph.json` 或等价的独立关系记录，包括模块树、边ID、源/目标端口、路径拐点与语义类型。按该图的结构编写检查程序，依次验证：

1. 关系表的边能与实际SVG路径一一对应，源目标及SVG父子分组正确。
2. 起止点落在声明端口，路径没有穿入无关节点。
3. 对直角折线检查线段交叉与共线覆盖，区分有意汇合和误连。
4. 读取浏览器 `textBoxes`，在统一的坐标系检查路径与所有文字的间距。

消费测量报告前，将当前SVG的SHA256与 `source_sha256` 比较；文件已修改时重新测量。报告中明确是否检查完整线段、描边和箭头，不能用中心线检查替代视觉检查。当前skill没有通用的自动布线引擎，不直接套用某一次示例的节点名称和坐标。

## 7. 实际查看PNG和PDF

用当前环境提供的图像查看能力或图像应用打开PNG，查看整图与关键局部；不依赖特定接口名称，不要只阅读JSON报告。可用Pillow生成不修改主文件的QA图：

```python
from PIL import Image, ImageOps
from pathlib import Path
Path("qa").mkdir(exist_ok=True)
im = Image.open("figure.png")
print(im.size, im.info.get("dpi"))
width = 680  # 约对应180mm在名义96ppi下的屏幕模拟；实际显示缩放可能不同。
small = im.resize((width, round(im.height * width / im.width)), Image.Resampling.LANCZOS)
small.save("qa/figure-small.png")
ImageOps.grayscale(small).save("qa/figure-gray.png")
# 按需要用 im.crop((left, top, right, bottom)) 导出端口、交叉处和内部机制的局部。
```

PDF重新渲染和读取页面尺寸：

```bash
pdftoppm -png -singlefile -scale-to 1800 qa/figure.pdf qa/figure-pdf
pdfinfo qa/figure.pdf
```

`-singlefile` 只适用于已确认单页的图；如果出现多页，先检查打印尺寸和边距，并检查所有页，不得漏掉溢出页。用pypdf补充验证：

```python
from pypdf import PdfReader
reader = PdfReader("qa/figure.pdf")
print("pages:", len(reader.pages))
for page in reader.pages:
    print("mm:", float(page.mediabox.width) * 25.4 / 72,
          float(page.mediabox.height) * 25.4 / 72)
    print("image objects:", len(page.images))
    print("text:", page.extract_text())
```

文字可提取和图像对象少是辅助证据，不单独证明渲染正确或全部内容为矢量。实际查看重新渲染的PDF页，检查缺字、线条、裁切及与SVG的一致性。通过后交付主SVG、最终PNG及用户需要的PDF，保留生成脚本和绘图说明。

## 替代路径

Sharp、浏览器不可用时，可使用环境中已有的Inkscape、CairoSVG或resvg完成其支持的导出步骤，参见 [导出规范](svg-and-export.md#导出与视觉复查)。绘制数值实验图时可由本地绘图库输出SVG，再进入相同检查链。可选布局引擎只辅助排序和路由；仍需执行方正版式与实际视觉验收。

更换字体、渲染器或导出实现后，重新检查实际文字包围盒、图标与文字间距、页面大小和裁切。不能仅按字号推断字高，也不能把一个渲染器的测量报告用于另一个环境。通用字体族能减少指定字体的依赖，但不能保证跨系统字形、字宽和排版完全一致。

维护此skill时，按 [验证与可移植性](validation.md) 运行分层回归和复杂框架实绘；记录已运行的环境与未覆盖项。
