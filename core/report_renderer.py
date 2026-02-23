from __future__ import annotations

from dataclasses import dataclass
import html
import re
from datetime import datetime
from typing import Iterable

from bs4 import BeautifulSoup
import markdown as md


@dataclass(frozen=True)
class TocItem:
    level: int
    text: str
    anchor: str


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^```")


def _split_title_and_inject_anchors(markdown_text: str) -> tuple[str | None, str, list[TocItem]]:
    """
    - 抽取第一个 H1 作为标题（若存在）
    - 对 H2-H4 注入稳定 anchor（sec-1, sec-2...），并生成 TOC
    - 仅处理“非代码块”区域（``` fenced code 内跳过）
    """
    lines = markdown_text.splitlines()
    in_fence = False
    title: str | None = None
    out_lines: list[str] = []
    toc: list[TocItem] = []
    sec = 0

    for line in lines:
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        m = _HEADING_RE.match(line)
        if not m:
            out_lines.append(line)
            continue

        level = len(m.group(1))
        text = m.group(2).strip()

        # 抽取首个 H1 作为标题，并从正文移除（避免 HTML 里重复 Hero+H1）
        if level == 1 and title is None:
            title = text
            continue

        # 只为 H2-H4 生成目录与 anchor
        if 2 <= level <= 4:
            # 避免重复注入：若用户/模型已经写了 {#xxx}，就不覆盖
            if re.search(r"\s\{#[-_a-zA-Z0-9]+\}\s*$", line):
                anchor = re.search(r"\{#([-_a-zA-Z0-9]+)\}\s*$", line).group(1)  # type: ignore[union-attr]
                toc.append(TocItem(level=level, text=text, anchor=anchor))
                out_lines.append(line)
                continue

            sec += 1
            anchor = f"sec-{sec}"
            toc.append(TocItem(level=level, text=text, anchor=anchor))
            out_lines.append(f"{m.group(1)} {text} {{#{anchor}}}")
            continue

        out_lines.append(line)

    return title, "\n".join(out_lines).strip() + "\n", toc


def _render_markdown_to_html(markdown_text: str) -> str:
    # fenced_code 会给 code 加上 language-xxx class，便于后处理 Mermaid
    return md.markdown(
        markdown_text,
        extensions=[
            "fenced_code",
            "tables",
            "attr_list",
            "sane_lists",
        ],
        output_format="html5",
    )


def _decorate_html(content_html: str) -> str:
    soup = BeautifulSoup(content_html, "html.parser")

    # 链接：统一为可点击引用样式（参考 demo.html 的 citation-link）
    for a in soup.find_all("a"):
        a["class"] = (a.get("class", []) + ["citation-link"])

    # 图片：统一排版
    for img in soup.find_all("img"):
        img["class"] = (img.get("class", []) + ["w-full", "rounded-xl", "border", "border-base-300", "my-6"])

    # 标题层级
    for h1 in soup.find_all("h1"):
        h1["class"] = (h1.get("class", []) + ["font-serif", "text-4xl", "font-semibold", "text-primary", "mb-6"])
    for h2 in soup.find_all("h2"):
        h2["class"] = (h2.get("class", []) + ["font-serif", "text-3xl", "font-semibold", "text-primary", "mt-12", "mb-6"])
    for h3 in soup.find_all("h3"):
        h3["class"] = (h3.get("class", []) + ["font-serif", "text-2xl", "font-semibold", "text-primary", "mt-10", "mb-4"])
    for h4 in soup.find_all("h4"):
        h4["class"] = (h4.get("class", []) + ["font-semibold", "text-neutral", "mt-8", "mb-3"])

    # 段落/列表
    for p in soup.find_all("p"):
        p["class"] = (p.get("class", []) + ["leading-relaxed", "text-neutral", "mb-4"])
    for ul in soup.find_all("ul"):
        ul["class"] = (ul.get("class", []) + ["list-disc", "pl-6", "space-y-2", "mb-4"])
    for ol in soup.find_all("ol"):
        ol["class"] = (ol.get("class", []) + ["list-decimal", "pl-6", "space-y-2", "mb-4"])
    for li in soup.find_all("li"):
        li["class"] = (li.get("class", []) + ["text-neutral"])

    # 引用块
    for bq in soup.find_all("blockquote"):
        bq["class"] = (bq.get("class", []) + ["quote-highlight", "p-6", "rounded-xl", "mb-6"])

    # 表格
    for table in soup.find_all("table"):
        table["class"] = (table.get("class", []) + ["w-full", "bg-white", "rounded-lg", "overflow-hidden", "border", "border-base-300"])
        thead = table.find("thead")
        if thead:
            thead["class"] = (thead.get("class", []) + ["bg-primary", "text-white"])
        for th in table.find_all("th"):
            th["class"] = (th.get("class", []) + ["px-4", "py-3", "text-left", "text-sm", "font-semibold"])
        for td in table.find_all("td"):
            td["class"] = (td.get("class", []) + ["px-4", "py-3", "text-sm", "text-neutral"])
        for tr in table.find_all("tr"):
            tr["class"] = (tr.get("class", []) + ["border-b", "border-base-300", "last:border-b-0"])

    # 行内 code / 代码块
    for code in soup.find_all("code"):
        # fenced_code 的 code 通常包在 pre 里；这里统一加一点样式
        code["class"] = (code.get("class", []) + ["bg-base-200", "px-1.5", "py-0.5", "rounded", "text-sm"])
    for pre in soup.find_all("pre"):
        pre["class"] = (pre.get("class", []) + ["bg-base-200", "p-4", "rounded-xl", "overflow-x-auto", "mb-6", "border", "border-base-300"])

    # Mermaid：把 ```mermaid``` 转换为 demo.html 里的可缩放容器
    for pre in list(soup.find_all("pre")):
        code = pre.find("code")
        if not code:
            continue
        classes = code.get("class", [])
        is_mermaid = any(c in ("language-mermaid", "mermaid") for c in classes)
        if not is_mermaid:
            continue

        mermaid_src = code.get_text()
        container = soup.new_tag("div")
        container["class"] = ["mermaid-container"]

        controls = soup.new_tag("div")
        controls["class"] = ["mermaid-controls"]
        controls.append(_btn(soup, "zoom-in", "+"))
        controls.append(_btn(soup, "zoom-out", "−"))
        controls.append(_btn(soup, "reset-zoom", "⟲"))
        controls.append(_btn(soup, "fullscreen", "⛶"))
        container.append(controls)

        mermaid_div = soup.new_tag("div")
        mermaid_div["class"] = ["mermaid"]
        mermaid_div.string = mermaid_src
        container.append(mermaid_div)

        pre.replace_with(container)

    return str(soup)


def _btn(soup: BeautifulSoup, cls: str, text: str):
    b = soup.new_tag("button")
    b["class"] = ["mermaid-control-btn", cls]
    b.string = text
    return b


def _build_toc_html(toc: Iterable[TocItem]) -> str:
    items = []
    for it in toc:
        # demo.html 的 TOC 是左侧固定导航；这里用缩进模拟层级
        indent = ""
        if it.level == 3:
            indent = ' style="margin-left: 1rem;"'
        elif it.level == 4:
            indent = ' style="margin-left: 2rem;"'

        items.append(
            f'<a href="#{html.escape(it.anchor)}" class="toc-link"{indent}>{html.escape(it.text)}</a>'
        )
    return "\n".join(items)


def render_deep_research_html(
    markdown_text: str,
    *,
    title_fallback: str,
    subtitle: str,
    generated_at: datetime | None = None,
) -> str:
    """
    将深度调研 Markdown 报告渲染为参考 data/demo.html 风格的 HTML。
    """
    generated_at = generated_at or datetime.now()
    title, md_with_anchors, toc = _split_title_and_inject_anchors(markdown_text)
    title = title or title_fallback

    content_html = _render_markdown_to_html(md_with_anchors)
    content_html = _decorate_html(content_html)
    toc_html = _build_toc_html(toc)

    # 参考 demo.html：固定 TOC + Hero + 主体内容 + Mermaid 初始化与控制
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
  <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          colors: {{
            primary: '#1e3a8a',
            secondary: '#64748b',
            accent: '#f59e0b',
            neutral: '#374151',
            'base-100': '#ffffff',
            'base-200': '#f8fafc',
            'base-300': '#e2e8f0'
          }},
          fontFamily: {{
            'serif': ['Crimson Text', 'serif'],
            'sans': ['Inter', 'sans-serif']
          }}
        }}
      }}
    }};
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'base',
      themeVariables: {{
        primaryColor: '#1e3a8a',
        primaryTextColor: '#1f2937',
        primaryBorderColor: '#1e3a8a',
        lineColor: '#64748b',
        secondaryColor: '#f8fafc',
        tertiaryColor: '#64748b',
        background: '#ffffff',
        mainBkg: '#ffffff',
        nodeBkg: '#f8fafc',
        clusterBkg: '#f1f5f9',
        edgeLabelBackground: '#ffffff'
      }},
      flowchart: {{ htmlLabels: true, curve: 'basis' }},
      fontFamily: 'Inter, sans-serif',
      fontSize: 14
    }});
  </script>
  <style>
    .hero-gradient {{
      background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 50%, #1e40af 100%);
    }}
    .text-shadow {{ text-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .citation-link {{
      color: #1e3a8a;
      text-decoration: none;
      border-bottom: 1px dotted #1e3a8a;
      transition: all 0.2s ease;
    }}
    .citation-link:hover {{
      background-color: #eff6ff;
      border-bottom: 1px solid #1e3a8a;
    }}
    #toc {{
      position: fixed;
      left: 0;
      top: 0;
      height: 100vh;
      width: 280px;
      background: #f8fafc;
      border-right: 1px solid #e2e8f0;
      z-index: 1000;
      overflow-y: auto;
      padding: 2rem 1.5rem;
    }}
    .main-content {{ margin-left: 280px; min-height: 100vh; }}
    .toc-link {{
      display: block;
      padding: 0.5rem 0;
      color: #64748b;
      text-decoration: none;
      font-size: 0.875rem;
      transition: color 0.2s ease;
      border-left: 2px solid transparent;
      padding-left: 0.75rem;
    }}
    .toc-link:hover, .toc-link.active {{
      color: #1e3a8a;
      border-left-color: #1e3a8a;
      background-color: #eff6ff;
    }}
    .section-divider {{
      height: 1px;
      background: linear-gradient(to right, transparent, #e2e8f0, transparent);
      margin: 3rem 0;
    }}
    .quote-highlight {{
      border-left: 4px solid #1e3a8a;
      background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    }}
    .mermaid-container {{
      display: flex;
      justify-content: center;
      min-height: 240px;
      max-height: 900px;
      background: #ffffff;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      padding: 30px;
      margin: 24px 0;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
      position: relative;
      overflow: hidden;
    }}
    .mermaid-container .mermaid {{
      width: 100%;
      max-width: 100%;
      height: 100%;
      cursor: grab;
      transition: transform 0.3s ease;
      transform-origin: center center;
      display: flex;
      justify-content: center;
      align-items: center;
      touch-action: none;
      user-select: none;
    }}
    .mermaid-controls {{
      position: absolute;
      top: 15px;
      right: 15px;
      display: flex;
      gap: 10px;
      z-index: 20;
      background: rgba(255, 255, 255, 0.95);
      padding: 8px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }}
    .mermaid-control-btn {{
      background: #ffffff;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      color: #374151;
      font-size: 14px;
      min-width: 36px;
      height: 36px;
      text-align: center;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .mermaid-control-btn:hover {{
      background: #f8fafc;
      border-color: #3b82f6;
      color: #3b82f6;
      transform: translateY(-1px);
    }}
    @media (max-width: 1024px) {{
      #toc {{ transform: translateX(-100%); transition: transform 0.3s ease; }}
      #toc.open {{ transform: translateX(0); }}
      .main-content {{ margin-left: 0; }}
      #toc-toggle {{ display: block; }}
      .mermaid-controls {{ top: auto; bottom: 15px; right: 15px; }}
    }}
    @media (min-width: 1025px) {{ #toc-toggle {{ display: none; }} }}
    body {{ overflow-x: hidden; }}
  </style>
  <base target="_blank">
</head>
<body class="bg-base-100 font-sans text-neutral">
  <nav id="toc" class="bg-base-200">
    <div class="mb-8">
      <h3 class="font-serif font-semibold text-lg text-primary mb-4">目录</h3>
      {toc_html}
    </div>
  </nav>

  <div class="main-content">
    <button id="toc-toggle" class="fixed top-4 left-4 z-50 bg-primary text-white p-2 rounded-lg shadow-lg lg:hidden">
      <i class="fas fa-bars"></i>
    </button>

    <section class="hero-gradient text-white relative overflow-hidden">
      <div class="relative z-10 max-w-7xl mx-auto px-6 py-14">
        <div class="flex flex-col lg:flex-row gap-8 items-start">
          <div class="flex-1">
            <h1 class="font-serif text-5xl lg:text-6xl font-semibold mb-4 leading-tight text-shadow italic">
              {html.escape(title)}
            </h1>
            <p class="text-xl lg:text-2xl font-light mb-6 leading-relaxed opacity-90">
              {html.escape(subtitle)}
            </p>
            <div class="flex items-center gap-4 text-sm opacity-90">
              <span class="bg-white/20 px-4 py-2 rounded-full"><i class="fas fa-calendar mr-2"></i>{generated_at.strftime("%Y-%m-%d %H:%M")}</span>
              <span class="bg-white/20 px-4 py-2 rounded-full"><i class="fas fa-file-alt mr-2"></i>深度调研报告</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="max-w-7xl mx-auto px-6 py-14">
      <div class="bg-white border border-base-300 rounded-2xl p-8">
        {content_html}
      </div>
    </section>

    <footer class="bg-base-200 border-t border-base-300 py-10">
      <div class="max-w-7xl mx-auto px-6 text-center">
        <p class="text-secondary text-sm">由 SiliconMomo 深度调研工作流自动生成</p>
      </div>
    </footer>
  </div>

  <script>
    document.getElementById('toc-toggle')?.addEventListener('click', function() {{
      document.getElementById('toc')?.classList.toggle('open');
    }});

    document.addEventListener('click', function(event) {{
      const toc = document.getElementById('toc');
      const tocToggle = document.getElementById('toc-toggle');
      if (!toc || !tocToggle) return;
      if (window.innerWidth <= 1024 &&
          !toc.contains(event.target) &&
          event.target !== tocToggle &&
          toc.classList.contains('open')) {{
        toc.classList.remove('open');
      }}
    }});

    function initializeMermaidControls() {{
      const containers = document.querySelectorAll('.mermaid-container');
      containers.forEach(container => {{
        const mermaidElement = container.querySelector('.mermaid');
        if (!mermaidElement) return;

        let scale = 1;
        let isDragging = false;
        let startX = 0, startY = 0, translateX = 0, translateY = 0;

        const zoomInBtn = container.querySelector('.zoom-in');
        const zoomOutBtn = container.querySelector('.zoom-out');
        const resetBtn = container.querySelector('.reset-zoom');
        const fullscreenBtn = container.querySelector('.fullscreen');

        function updateTransform() {{
          mermaidElement.style.transform = `translate(${{translateX}}px, ${{translateY}}px) scale(${{scale}})`;
          mermaidElement.style.cursor = isDragging ? 'grabbing' : 'grab';
          if (scale <= 1) {{ translateX = 0; translateY = 0; }}
        }}

        zoomInBtn?.addEventListener('click', () => {{
          scale = Math.min(scale * 1.25, 4);
          updateTransform();
        }});
        zoomOutBtn?.addEventListener('click', () => {{
          scale = Math.max(scale / 1.25, 0.3);
          updateTransform();
        }});
        resetBtn?.addEventListener('click', () => {{
          scale = 1; translateX = 0; translateY = 0;
          updateTransform();
        }});
        fullscreenBtn?.addEventListener('click', () => {{
          if (container.requestFullscreen) container.requestFullscreen();
        }});

        mermaidElement.addEventListener('mousedown', (e) => {{
          isDragging = true;
          startX = e.clientX - translateX;
          startY = e.clientY - translateY;
          updateTransform();
          e.preventDefault();
        }});
        document.addEventListener('mousemove', (e) => {{
          if (!isDragging) return;
          translateX = e.clientX - startX;
          translateY = e.clientY - startY;
          updateTransform();
        }});
        document.addEventListener('mouseup', () => {{
          isDragging = false;
          updateTransform();
        }});

        container.addEventListener('wheel', (e) => {{
          e.preventDefault();
          const delta = e.deltaY > 0 ? 0.9 : 1.1;
          scale = Math.min(Math.max(scale * delta, 0.3), 4);
          updateTransform();
        }});

        updateTransform();
      }});
    }}

    // Mermaid 渲染完成后再挂控制器
    window.addEventListener('load', () => {{
      setTimeout(initializeMermaidControls, 800);
    }});

    // 平滑滚动 + active 高亮
    document.querySelectorAll('.toc-link').forEach(link => {{
      link.addEventListener('click', function(e) {{
        e.preventDefault();
        const targetId = this.getAttribute('href');
        const target = document.querySelector(targetId);
        if (target) {{
          target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
      }});
    }});
    function updateActiveTOCLink() {{
      const headings = document.querySelectorAll('h2[id], h3[id], h4[id]');
      const tocLinks = document.querySelectorAll('.toc-link');
      let current = '';
      headings.forEach(h => {{
        const rect = h.getBoundingClientRect();
        if (rect.top <= 120 && rect.bottom >= 120) current = h.id;
      }});
      tocLinks.forEach(l => {{
        l.classList.remove('active');
        if (l.getAttribute('href') === '#' + current) l.classList.add('active');
      }});
    }}
    window.addEventListener('scroll', updateActiveTOCLink);
    updateActiveTOCLink();
  </script>
</body>
</html>
"""

