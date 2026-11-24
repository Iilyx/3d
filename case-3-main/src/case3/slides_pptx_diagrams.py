"""Native PPTX vector shapes and connectors for Liber diagrams."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt

from case3.diagram_style import role_colors_for_palette

log = logging.getLogger("case3.slides_pptx_diagrams")

_RE_FLOWCHART = re.compile(r"^\s*(?:flowchart|graph)\s+([A-Za-z]+)", re.IGNORECASE)
_RE_CLASS_ASSIGN = re.compile(r"^\s*class\s+([A-Za-z0-9_,\s]+?)\s+([A-Za-z0-9_]+)\s*$", re.MULTILINE)
_RE_EDGE = re.compile(
    r"([A-Za-z0-9_]+)"                           # src
    r"(?:\s*(?:\[\(.*?\)\]|\(\[.*?\]\)|\{.*?\}|\[.*?\]|\(.*?\)|\(\(\(.*?\)|\(\(.*?\)|\>.*?\]))?" # optional src def
    r"(?:\s*:::\s*([A-Za-z0-9_]+))?"             # optional src class
    r"\s*(?:-->|-.->|==>|--\s*>\s*)"              # arrow
    r"(?:\|(.*?)\|)?"                             # optional edge label
    r"\s*([A-Za-z0-9_]+)"                         # dst
    r"(?:\s*(?:\[\(.*?\)\]|\(\[.*?\]\)|\{.*?\}|\[.*?\]|\(.*?\)|\(\(\(.*?\)|\(\(.*?\)|\>.*?\]))?" # optional dst def
    r"(?:\s*:::\s*([A-Za-z0-9_]+))?"             # optional dst class
)

# Extract node definition tokens: id([label]), id[label], id{label}, id[(label)], id(label) with optional :::role
_RE_NODE_DEF = re.compile(
    r"\b([A-Za-z0-9_]+)\s*(?:\[\((.*?)\)\]|\(\[(.*?)\]\)|\{(.*?)\}|\[(.*?)\]|\((.*?)\))(?:\s*:::\s*([A-Za-z0-9_]+))?"
)


@dataclass
class DiagramNode:
    id: str
    label: str
    shape: str = "rect"  # "rect" | "capsule" | "diamond" | "cylinder"
    role: str = "process"  # "start" | "process" | "decision" | "ok" | "warn" | "data"


@dataclass
class DiagramEdge:
    src: str
    dst: str
    label: str = ""


@dataclass
class DiagramSubgraph:
    id: str
    title: str
    node_ids: list[str] = field(default_factory=list)


@dataclass
class TimelinePeriod:
    period: str
    events: list[str] = field(default_factory=list)


@dataclass
class TimelineSpec:
    title: str = ""
    periods: list[TimelinePeriod] = field(default_factory=list)


@dataclass
class MindmapNode:
    id: str
    label: str
    level: int = 0
    children: list[MindmapNode] = field(default_factory=list)


@dataclass
class DiagramGraph:
    direction: str  # "TD" | "LR"
    nodes: dict[str, DiagramNode] = field(default_factory=dict)
    edges: list[DiagramEdge] = field(default_factory=list)
    subgraphs: list[DiagramSubgraph] = field(default_factory=list)


@dataclass
class NodeBox:
    node: DiagramNode
    x: float  # inches
    y: float  # inches
    w: float  # inches
    h: float  # inches


@dataclass
class DiagramLayout:
    direction: str
    boxes: dict[str, NodeBox] = field(default_factory=dict)
    edges: list[DiagramEdge] = field(default_factory=list)


def compute_diagram_layout(
    graph: DiagramGraph,
    left: float,
    top: float,
    width: float,
    height: float,
) -> DiagramLayout:
    """Assign 2D positions (in inches) to diagram nodes using a layered DAG layout."""
    nodes = graph.nodes
    if not nodes:
        return DiagramLayout(direction=graph.direction, boxes={}, edges=graph.edges)

    # 1. Cycle detection & forward DAG edges extraction
    adj: dict[str, list[str]] = {nid: [] for nid in nodes}
    for e in graph.edges:
        if e.src in nodes and e.dst in nodes and e.dst not in adj[e.src]:
            adj[e.src].append(e.dst)

    # DFS to find back-edges (cycles)
    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
    back_edges: set[tuple[str, str]] = set()

    def dfs(u: str):
        visited[u] = 1
        for v in adj[u]:
            if visited.get(v, 0) == 1:
                back_edges.add((u, v))
            elif visited.get(v, 0) == 0:
                dfs(v)
        visited[u] = 2

    for nid in nodes:
        if visited.get(nid, 0) == 0:
            dfs(nid)

    # 2. Compute layer ranks via longest path on forward DAG
    ranks: dict[str, int] = {nid: 0 for nid in nodes}
    for _ in range(len(nodes)):
        changed = False
        for e in graph.edges:
            if (e.src, e.dst) in back_edges:
                continue
            if e.src in nodes and e.dst in nodes:
                if ranks[e.dst] < ranks[e.src] + 1:
                    ranks[e.dst] = ranks[e.src] + 1
                    changed = True
        if not changed:
            break

    # Group by layer
    num_layers = max(ranks.values()) + 1
    layers: dict[int, list[str]] = {layer_idx: [] for layer_idx in range(num_layers)}
    for nid, r in ranks.items():
        layers[r].append(nid)

    max_layer_size = max(len(layer_nodes) for layer_nodes in layers.values()) if layers else 1

    # 3. Geometry placement in target rectangle [left, top, width, height]
    pad = 0.15
    avail_w = max(0.5, width - 2 * pad)
    avail_h = max(0.5, height - 2 * pad)

    is_td = graph.direction in ("TD", "TB")
    boxes: dict[str, NodeBox] = {}

    if is_td:
        # TD: Primary axis is Y (layers), Secondary axis is X
        # Node dimensions
        node_h = min(0.85, avail_h / (num_layers * 1.45))
        node_w = min(1.9, avail_w / (max_layer_size * 1.25))

        # Ensure bounds fit
        if num_layers * node_h > avail_h:
            node_h = avail_h / max(1, num_layers * 1.1)
        if max_layer_size * node_w > avail_w:
            node_w = avail_w / max(1, max_layer_size * 1.1)

        # Gap between layers
        if num_layers > 1:
            gap_y = (avail_h - num_layers * node_h) / (num_layers - 1)
        else:
            gap_y = 0.0

        for layer_idx, layer_nodes in layers.items():
            if num_layers == 1:
                y = top + pad + (avail_h - node_h) / 2.0
            else:
                y = top + pad + layer_idx * (node_h + gap_y)

            k = len(layer_nodes)
            if k == 1:
                gap_x = 0.0
                layer_w = node_w
                start_x = left + pad + (avail_w - layer_w) / 2.0
            else:
                gap_x = min(0.6, (avail_w - k * node_w) / (k - 1))
                layer_w = k * node_w + (k - 1) * gap_x
                start_x = left + pad + (avail_w - layer_w) / 2.0

            for i, nid in enumerate(layer_nodes):
                x = start_x + i * (node_w + gap_x)
                boxes[nid] = NodeBox(node=nodes[nid], x=round(x, 4), y=round(y, 4), w=round(node_w, 4), h=round(node_h, 4))
    else:
        # LR: Primary axis is X (layers), Secondary axis is Y
        node_w = min(1.75, avail_w / (num_layers * 1.45))
        node_h = min(0.85, avail_h / (max_layer_size * 1.25))

        if num_layers * node_w > avail_w:
            node_w = avail_w / max(1, num_layers * 1.1)
        if max_layer_size * node_h > avail_h:
            node_h = avail_h / max(1, max_layer_size * 1.1)

        if num_layers > 1:
            gap_x = (avail_w - num_layers * node_w) / (num_layers - 1)
        else:
            gap_x = 0.0

        for layer_idx, layer_nodes in layers.items():
            if num_layers == 1:
                x = left + pad + (avail_w - node_w) / 2.0
            else:
                x = left + pad + layer_idx * (node_w + gap_x)

            k = len(layer_nodes)
            if k == 1:
                gap_y = 0.0
                layer_h = node_h
                start_y = top + pad + (avail_h - layer_h) / 2.0
            else:
                gap_y = min(0.6, (avail_h - k * node_h) / (k - 1))
                layer_h = k * node_h + (k - 1) * gap_y
                start_y = top + pad + (avail_h - layer_h) / 2.0

            for i, nid in enumerate(layer_nodes):
                y = start_y + i * (node_h + gap_y)
                boxes[nid] = NodeBox(node=nodes[nid], x=round(x, 4), y=round(y, 4), w=round(node_w, 4), h=round(node_h, 4))

    return DiagramLayout(direction=graph.direction, boxes=boxes, edges=graph.edges)



def _parse_subgraph_header(line: str) -> tuple[str, str] | None:
    """Parse subgraph declaration like 'subgraph id [Title]' or 'subgraph Title'."""
    stripped = line.strip()
    if not stripped.lower().startswith("subgraph"):
        return None
    rest = stripped[8:].strip()
    if not rest:
        return None
    # Check id [title] or id ["title"]
    m = re.match(r'^([A-Za-z0-9_]+)\s*(?:\[\s*(?:\"(.*?)\"|(.*?))\s*\]|\"\s*(.*?)\s*\")?$', rest)
    if m:
        sg_id = m.group(1)
        title = m.group(2) or m.group(3) or m.group(4) or sg_id
        return sg_id, title.strip()
    # Check [title] or "title" or raw title
    m = re.match(r'^(?:\[\s*(?:\"(.*?)\"|(.*?))\s*\]|\"\s*(.*?)\s*\"|(.*))$', rest)
    if m:
        title = (m.group(1) or m.group(2) or m.group(3) or m.group(4) or "").strip()
        sg_id = re.sub(r"[^A-Za-z0-9_]", "_", title) or "subgraph"
        return sg_id, title
    return None


def _clean_mermaid_label(text: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.IGNORECASE)
    s = s.replace("#quot;", '"').replace("&quot;", '"').replace("#39;", "'").replace("&amp;", "&")
    return s.strip()


def parse_mermaid_flowchart(mermaid: str) -> DiagramGraph | None:
    """Parse a Mermaid flowchart string into a structured DiagramGraph.

    Returns None if text is not a flowchart or cannot be parsed.
    """
    if not mermaid or not isinstance(mermaid, str):
        return None
    from case3.diagrams import first_meaningful_line

    raw = mermaid.strip()
    first_line = first_meaningful_line(raw)
    head_match = _RE_FLOWCHART.match(first_line)
    if not head_match:
        return None

    direction = head_match.group(1).upper()
    if direction not in ("TD", "TB", "LR", "RL", "BT"):
        direction = "TD"
    if direction == "TB":
        direction = "TD"

    # Extract roles from class assignments
    node_roles: dict[str, str] = {}
    for match in _RE_CLASS_ASSIGN.finditer(raw):
        node_ids_str, role_name = match.group(1), match.group(2).lower()
        for nid in node_ids_str.split(","):
            cleaned = nid.strip()
            if cleaned:
                node_roles[cleaned] = role_name

    nodes: dict[str, DiagramNode] = {}
    edges: list[DiagramEdge] = []

    # First pass: find all explicit node shapes & labels
    for match in _RE_NODE_DEF.finditer(raw):
        nid = match.group(1)
        cyl_lbl = match.group(2)
        capsule_lbl = match.group(3)
        diamond_lbl = match.group(4)
        rect_lbl = match.group(5)
        round_lbl = match.group(6)
        inline_role = (match.group(7) or "").lower()

        shape = "rect"
        label = nid
        if cyl_lbl is not None:
            shape = "cylinder"
            label = cyl_lbl.strip()
        elif capsule_lbl is not None:
            shape = "capsule"
            label = capsule_lbl.strip()
        elif diamond_lbl is not None:
            shape = "diamond"
            label = diamond_lbl.strip()
        elif rect_lbl is not None:
            shape = "rect"
            label = rect_lbl.strip()
        elif round_lbl is not None:
            shape = "capsule"
            label = round_lbl.strip()

        # Determine role: inline :::role takes precedence over class assignment, then fallback
        role = inline_role or node_roles.get(nid)
        if not role:
            if shape == "capsule":
                role = "start"
            elif shape == "diamond":
                role = "decision"
            elif shape == "cylinder":
                role = "data"
            else:
                role = "process"

        nodes[nid] = DiagramNode(id=nid, label=_clean_mermaid_label(label), shape=shape, role=role)

    # Second pass: parse edges, implicit nodes, and subgraphs
    subgraphs: list[DiagramSubgraph] = []
    current_subgraph: DiagramSubgraph | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("%%") or line.startswith("class"):
            continue

        sg_header = _parse_subgraph_header(line)
        if sg_header:
            sg_id, sg_title = sg_header
            current_subgraph = DiagramSubgraph(id=sg_id, title=sg_title, node_ids=[])
            subgraphs.append(current_subgraph)
            continue

        if re.match(r"^end\b", line, re.IGNORECASE):
            current_subgraph = None
            continue

        # Split chained edges (A --> B --> C) and ampersand fan-out (A & B --> C & D)
        arrow_re = re.compile(r"\s*(?:-->|-.->|==>|--\s*>)\s*(?:\|(.*?)\|)?\s*")
        node_tok_re = re.compile(
            r"^\s*([A-Za-z0-9_]+)"
            r"(?:\s*(?:\[\(.*?\)\]|\(\[.*?\]\)|\{.*?\}|\[.*?\]|\(.*?\)|\(\(\(.*?\)|\(\(.*?\)|\>.*?\]))?"
            r"(?:\s*:::\s*([A-Za-z0-9_]+))?\s*$"
        )
        edge_matches: list[tuple[str, str, str]] = []
        if arrow_re.search(line):
            parts: list[str] = []
            edge_labels: list[str] = []
            last_idx = 0
            for am in arrow_re.finditer(line):
                parts.append(line[last_idx : am.start()])
                edge_labels.append(_clean_mermaid_label(am.group(1) or ""))
                last_idx = am.end()
            parts.append(line[last_idx:])
            chain_groups: list[list[str]] = []
            for p in parts:
                group_ids: list[str] = []
                for sub in p.split("&"):
                    tm = node_tok_re.match(sub)
                    if tm:
                        group_ids.append(tm.group(1))
                    else:
                        idm = re.search(r"\b([A-Za-z0-9_]+)\b", sub)
                        if idm:
                            group_ids.append(idm.group(1))
                chain_groups.append(group_ids)
            for idx_g in range(len(chain_groups) - 1):
                elbl = edge_labels[idx_g] if idx_g < len(edge_labels) else ""
                for s_id in chain_groups[idx_g]:
                    for d_id in chain_groups[idx_g + 1]:
                        edge_matches.append((s_id, d_id, elbl))
        for src, dst, edge_lbl in edge_matches:
            edges.append(DiagramEdge(src=src, dst=dst, label=edge_lbl))
            if src not in nodes:
                nodes[src] = DiagramNode(id=src, label=src, shape="rect", role=node_roles.get(src, "process"))
            if dst not in nodes:
                nodes[dst] = DiagramNode(id=dst, label=dst, shape="rect", role=node_roles.get(dst, "process"))

        if current_subgraph is not None:
            # Collect node IDs mentioned in this line inside the subgraph
            for nm in _RE_NODE_DEF.finditer(line):
                nid = nm.group(1)
                if nid not in current_subgraph.node_ids:
                    current_subgraph.node_ids.append(nid)
            for src, dst, _elbl in edge_matches:
                for nid in (src, dst):
                    if nid not in current_subgraph.node_ids:
                        current_subgraph.node_ids.append(nid)
            m_simple = re.match(r"^([A-Za-z0-9_]+)$", line)
            if m_simple:
                nid = m_simple.group(1)
                if nid not in current_subgraph.node_ids:
                    current_subgraph.node_ids.append(nid)
                if nid not in nodes:
                    nodes[nid] = DiagramNode(id=nid, label=nid, shape="rect", role=node_roles.get(nid, "process"))

    if not nodes:
        return None

    return DiagramGraph(direction=direction, nodes=nodes, edges=edges, subgraphs=subgraphs)


def parse_mermaid_timeline(mermaid: str) -> TimelineSpec | None:
    """Parse Mermaid timeline diagram syntax into TimelineSpec."""
    if not mermaid or not isinstance(mermaid, str):
        return None
    from case3.diagrams import first_meaningful_line

    first_line = first_meaningful_line(mermaid)
    if not re.match(r"^timeline\b", first_line, re.IGNORECASE):
        return None
    lines = [ln.strip() for ln in mermaid.strip().splitlines() if ln.strip()]

    spec = TimelineSpec()
    curr_period: TimelinePeriod | None = None

    for line in lines[1:]:
        if line.startswith("%%"):
            continue
        m_title = re.match(r"^title\s+(.*)$", line, re.IGNORECASE)
        if m_title:
            spec.title = m_title.group(1).strip()
            continue
        if re.match(r"^section\b", line, re.IGNORECASE):
            continue
        if ":" in line:
            parts = [p.strip() for p in line.split(":") if p.strip()]
            if not parts:
                continue
            if line.startswith(":"):
                if curr_period is not None:
                    curr_period.events.extend(parts)
            else:
                period_name = parts[0]
                events = parts[1:]
                curr_period = TimelinePeriod(period=period_name, events=events)
                spec.periods.append(curr_period)
        else:
            curr_period = TimelinePeriod(period=line, events=[])
            spec.periods.append(curr_period)

    spec.periods = [p for p in spec.periods if p.period or p.events]
    return spec if spec.periods else None


def parse_mermaid_mindmap(mermaid: str) -> MindmapNode | None:
    """Parse Mermaid mindmap indentation tree into MindmapNode."""
    if not mermaid or not isinstance(mermaid, str):
        return None
    raw_lines = mermaid.splitlines()
    non_empty = [ln for ln in raw_lines if ln.strip() and not ln.strip().startswith("%%")]
    if not non_empty or not re.match(r"^mindmap\b", non_empty[0].strip(), re.IGNORECASE):
        return None

    def clean_label(text: str) -> str:
        s = text.strip()
        m = re.match(r"^(?:[A-Za-z0-9_]+\s*)?(?:\(\((.*?)\)\)|\((.*?)\)|\[(.*?)\]|\)(.*?)\()$", s)
        if m:
            lbl = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
            return lbl.strip()
        if s.lower().startswith("root"):
            s = s[4:].strip()
        return s or text.strip()

    nodes_with_indent: list[tuple[int, str]] = []
    for line in non_empty[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        nodes_with_indent.append((indent, clean_label(stripped)))

    if not nodes_with_indent:
        return None

    root_indent, root_label = nodes_with_indent[0]
    root_node = MindmapNode(id="root", label=root_label or "Root", level=0)
    stack: list[tuple[int, MindmapNode]] = [(root_indent, root_node)]

    for ind, lbl in nodes_with_indent[1:]:
        while stack and stack[-1][0] >= ind:
            stack.pop()
        parent = stack[-1][1] if stack else root_node

        child_node = MindmapNode(
            id=f"n_{len(stack)}_{len(parent.children)}",
            label=lbl,
            level=parent.level + 1,
        )
        parent.children.append(child_node)
        stack.append((ind, child_node))

    return root_node


def _to_inches(val: Any) -> float:
    if hasattr(val, "inches"):
        return float(val.inches)
    return float(val)


def _hex_to_rgb(hex_str: str) -> RGBColor:
    s = hex_str.lstrip("#")
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    return RGBColor(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _set_arrowhead(connector: Any) -> None:
    """Inject drawingML triangle arrowhead at connector end."""
    try:
        spPr = connector._element.spPr
        ln = spPr.ln
        if ln is None:
            ln = spPr._add_ln()
        tailEnd = OxmlElement("a:tailEnd")
        tailEnd.set("type", "triangle")
        tailEnd.set("w", "med")
        tailEnd.set("len", "med")
        ln.append(tailEnd)
    except Exception:
        pass


def _set_shape_alpha(shape: Any, alpha: float) -> None:
    """Set solid fill transparency (0=opaque, 1=invisible)."""
    try:
        solid = shape.fill._xPr.solidFill
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is None:
            return
        for child in list(srgb):
            if "alpha" in child.tag:
                srgb.remove(child)
        alpha_el = parse_xml(
            f'<a:alpha {nsdecls("a")} val="{int(max(0, min(1, alpha)) * 100000)}"/>'
        )
        srgb.append(alpha_el)
    except Exception:
        pass


def _draw_native_flowchart(
    slide: Any,
    dia_spec: dict[str, Any],
    graph: DiagramGraph,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    colors: dict[str, Any],
    palette: str,
    font_name: str,
) -> bool:
    try:
        layout = compute_diagram_layout(graph, left, top, width, height)
    except Exception as exc:
        log.warning("diagram layout failed for %s: %s", dia_spec.get("id"), exc)
        return False

    role_colors = role_colors_for_palette(palette)
    line_rgb = _hex_to_rgb(str(colors.get("muted") or "#5c6570"))
    text_default_rgb = _hex_to_rgb(str(colors.get("ink") or "#1a2e22"))
    deck_font = font_name

    is_td = graph.direction in ("TD", "TB")
    shapes_by_id: dict[str, Any] = {}

    try:
        # 0. Place subgraph container frames (behind nodes)
        for sg in graph.subgraphs:
            sg_boxes = [layout.boxes[nid] for nid in sg.node_ids if nid in layout.boxes]
            if not sg_boxes:
                continue

            min_x = min(b.x for b in sg_boxes)
            min_y = min(b.y for b in sg_boxes)
            max_x = max(b.x + b.w for b in sg_boxes)
            max_y = max(b.y + b.h for b in sg_boxes)

            pad_x = 0.12
            pad_top = 0.28
            pad_bottom = 0.10

            box_x = max(left, min_x - pad_x)
            box_y = max(top, min_y - pad_top)
            box_w = min(left + width - box_x, (max_x - min_x) + 2 * pad_x)
            box_h = min(top + height - box_y, (max_y - min_y) + pad_top + pad_bottom)

            sg_shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(box_x),
                Inches(box_y),
                Inches(box_w),
                Inches(box_h),
            )
            sg_shape.fill.solid()
            sg_fill_rgb = _hex_to_rgb(str(colors.get("card") or "#f7f9f8"))
            sg_shape.fill.fore_color.rgb = sg_fill_rgb
            sg_shape.line.color.rgb = line_rgb
            sg_shape.line.width = Pt(1.0)
            _set_shape_alpha(sg_shape, 0.45)

            # Header text
            tf = sg_shape.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.TOP
            tf.margin_top = Inches(0.06)
            tf.margin_left = Inches(0.08)
            p = tf.paragraphs[0]
            p.text = sg.title.upper() if sg.title else sg.id
            p.alignment = PP_ALIGN.LEFT
            p.font.name = deck_font
            p.font.size = Pt(8.5)
            p.font.bold = True
            p.font.color.rgb = line_rgb

        # 1. Place nodes as shapes
        for nid, box in layout.boxes.items():
            shape_type = MSO_SHAPE.DIAMOND if box.node.shape == "diamond" else MSO_SHAPE.ROUNDED_RECTANGLE

            shape = slide.shapes.add_shape(
                shape_type,
                Inches(box.x),
                Inches(box.y),
                Inches(box.w),
                Inches(box.h),
            )
            shapes_by_id[nid] = shape

            # Color styling
            role_token = role_colors.get(box.node.role) or role_colors.get("process")
            fill_rgb = _hex_to_rgb(role_token["fill"]) if role_token else _hex_to_rgb("#e8eaed")
            stroke_rgb = _hex_to_rgb(role_token["stroke"]) if role_token else line_rgb
            text_rgb = _hex_to_rgb(role_token["color"]) if role_token else text_default_rgb

            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_rgb
            shape.line.color.rgb = stroke_rgb
            shape.line.width = Pt(1.5)

            # Text framing
            tf = shape.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.text = box.node.label
            p.alignment = PP_ALIGN.CENTER
            p.font.name = deck_font
            p.font.size = Pt(10) if len(box.node.label) > 28 else Pt(11)
            p.font.bold = box.node.shape in ("capsule", "diamond")
            p.font.color.rgb = text_rgb

        # 2. Place connectors
        for edge in layout.edges:
            s_src = shapes_by_id.get(edge.src)
            s_dst = shapes_by_id.get(edge.dst)
            b_src = layout.boxes.get(edge.src)
            b_dst = layout.boxes.get(edge.dst)
            if not s_src or not s_dst or not b_src or not b_dst:
                continue

            if is_td:
                x1, y1 = b_src.x + b_src.w / 2.0, b_src.y + b_src.h
                x2, y2 = b_dst.x + b_dst.w / 2.0, b_dst.y
                is_elbow = abs(b_src.x - b_dst.x) > 0.1
            else:
                x1, y1 = b_src.x + b_src.w, b_src.y + b_src.h / 2.0
                x2, y2 = b_dst.x, b_dst.y + b_dst.h / 2.0
                is_elbow = abs(b_src.y - b_dst.y) > 0.1

            conn_type = MSO_CONNECTOR.ELBOW if is_elbow else MSO_CONNECTOR.STRAIGHT
            conn = slide.shapes.add_connector(
                conn_type,
                Inches(x1),
                Inches(y1),
                Inches(x2),
                Inches(y2),
            )

            # Connect to shape ports
            try:
                if is_td:
                    conn.begin_connect(s_src, 2)  # bottom port
                    conn.end_connect(s_dst, 0)    # top port
                else:
                    conn.begin_connect(s_src, 3)  # right port
                    conn.end_connect(s_dst, 1)    # left port
            except Exception:
                pass

            conn.line.color.rgb = stroke_rgb if edge.src == edge.dst else line_rgb
            conn.line.width = Pt(1.5)
            _set_arrowhead(conn)

            # Optional edge label
            if edge.label:
                mid_x = (x1 + x2) / 2.0
                mid_y = (y1 + y2) / 2.0
                tb = slide.shapes.add_textbox(
                    Inches(mid_x - 0.45),
                    Inches(mid_y - 0.15),
                    Inches(0.9),
                    Inches(0.3),
                )
                p = tb.text_frame.paragraphs[0]
                p.text = edge.label
                p.alignment = PP_ALIGN.CENTER
                p.font.name = deck_font
                p.font.size = Pt(9)
                p.font.color.rgb = line_rgb

        return True
    except Exception as exc:
        log.warning("failed to draw native flowchart shapes: %s", exc)
        return False


def _draw_native_timeline(
    slide: Any,
    dia_spec: dict[str, Any],
    spec: TimelineSpec,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    colors: dict[str, Any],
    palette: str,
    font_name: str,
) -> bool:
    num_p = len(spec.periods)
    if num_p < 1 or num_p > 8:
        return False
    total_events = sum(len(p.events) for p in spec.periods)
    if total_events > 16:
        return False

    deck_font = font_name
    role_colors = role_colors_for_palette(palette)
    accent_rgb = _hex_to_rgb(str(colors.get("accent") or role_colors.get("process", {}).get("fill") or "#275035"))
    line_rgb = _hex_to_rgb(str(colors.get("muted") or "#5c6570"))
    text_default_rgb = _hex_to_rgb(str(colors.get("ink") or "#1a2e22"))
    card_bg_rgb = _hex_to_rgb(str(colors.get("card") or "#f7f9f8"))

    curr_top = top
    curr_height = height

    try:
        # 1. Optional diagram title
        if spec.title:
            title_box = slide.shapes.add_textbox(Inches(left), Inches(curr_top), Inches(width), Inches(0.35))
            tf = title_box.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = spec.title
            p.font.name = deck_font
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = text_default_rgb
            curr_top += 0.40
            curr_height -= 0.40

        # 2. Horizontal timeline spine
        spine_y = curr_top + curr_height * 0.35
        spine_margin = 0.4
        spine_start_x = left + spine_margin
        spine_end_x = left + width - spine_margin
        spine_w = spine_end_x - spine_start_x

        spine = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            Inches(spine_start_x),
            Inches(spine_y),
            Inches(spine_end_x),
            Inches(spine_y),
        )
        spine.line.color.rgb = accent_rgb
        spine.line.width = Pt(2.5)

        # 3. Period badges and event cards
        badge_w = min(1.3, (spine_w / num_p) * 0.80)
        badge_h = 0.36
        step_x = spine_w / max(1, num_p - 1) if num_p > 1 else 0

        for i, per in enumerate(spec.periods):
            cx = spine_start_x + i * step_x if num_p > 1 else spine_start_x + spine_w / 2.0
            bx = cx - badge_w / 2.0
            by = spine_y - badge_h / 2.0

            badge = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(bx),
                Inches(by),
                Inches(badge_w),
                Inches(badge_h),
            )
            badge.fill.solid()
            badge.fill.fore_color.rgb = accent_rgb
            badge.line.color.rgb = accent_rgb
            badge.line.width = Pt(1.0)

            tf = badge.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.text = per.period
            p.alignment = PP_ALIGN.CENTER
            p.font.name = deck_font
            p.font.size = Pt(9.5)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)

            if per.events:
                card_w = min(1.6, max(badge_w, (spine_w / num_p) * 0.90))
                card_x = cx - card_w / 2.0
                start_event_y = spine_y + badge_h / 2.0 + 0.12

                for j, ev_text in enumerate(per.events):
                    card_h = 0.42 if len(ev_text) > 25 else 0.32
                    card_y = start_event_y + j * (card_h + 0.08)
                    if card_y + card_h > top + height:
                        break

                    conn_y1 = by + badge_h if j == 0 else card_y - 0.08
                    conn = slide.shapes.add_connector(
                        MSO_CONNECTOR.STRAIGHT,
                        Inches(cx),
                        Inches(conn_y1),
                        Inches(cx),
                        Inches(card_y),
                    )
                    conn.line.color.rgb = line_rgb
                    conn.line.width = Pt(1.0)

                    ev_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(card_x),
                        Inches(card_y),
                        Inches(card_w),
                        Inches(card_h),
                    )
                    ev_shape.fill.solid()
                    ev_shape.fill.fore_color.rgb = card_bg_rgb
                    ev_shape.line.color.rgb = line_rgb
                    ev_shape.line.width = Pt(1.0)

                    tf = ev_shape.text_frame
                    tf.word_wrap = True
                    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    tf.margin_left = Inches(0.06)
                    tf.margin_right = Inches(0.06)
                    p = tf.paragraphs[0]
                    p.text = ev_text
                    p.alignment = PP_ALIGN.CENTER
                    p.font.name = deck_font
                    p.font.size = Pt(8.5)
                    p.font.color.rgb = text_default_rgb

        return True
    except Exception as exc:
        log.warning("failed to draw native timeline shapes: %s", exc)
        return False


def _draw_native_mindmap(
    slide: Any,
    dia_spec: dict[str, Any],
    root_node: MindmapNode,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    colors: dict[str, Any],
    palette: str,
    font_name: str,
) -> bool:
    def count_nodes(n: MindmapNode) -> int:
        return 1 + sum(count_nodes(c) for c in n.children)

    total_nodes = count_nodes(root_node)
    if total_nodes > 14:
        return False

    deck_font = font_name
    role_colors = role_colors_for_palette(palette)
    accent_rgb = _hex_to_rgb(str(colors.get("accent") or role_colors.get("process", {}).get("fill") or "#275035"))
    line_rgb = _hex_to_rgb(str(colors.get("muted") or "#5c6570"))
    text_default_rgb = _hex_to_rgb(str(colors.get("ink") or "#1a2e22"))
    card_bg_rgb = _hex_to_rgb(str(colors.get("card") or "#f7f9f8"))

    root_w = min(1.8, width * 0.25)
    root_h = 0.65
    root_x = left + 0.2
    root_y = top + (height - root_h) / 2.0

    try:
        # Draw root shape
        root_shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(root_x),
            Inches(root_y),
            Inches(root_w),
            Inches(root_h),
        )
        root_shape.fill.solid()
        root_shape.fill.fore_color.rgb = accent_rgb
        root_shape.line.color.rgb = accent_rgb
        root_shape.line.width = Pt(1.5)

        tf = root_shape.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.text = root_node.label
        p.alignment = PP_ALIGN.CENTER
        p.font.name = deck_font
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

        branches = root_node.children
        if not branches:
            return True

        num_branches = len(branches)
        branch_w = min(1.7, width * 0.26)
        branch_h = min(0.55, height / (num_branches * 1.5))
        branch_x = left + width * 0.34

        branch_gap_y = (height - num_branches * branch_h) / (num_branches + 1)

        for bi, branch in enumerate(branches):
            by = top + branch_gap_y * (bi + 1) + bi * branch_h
            b_shape = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE,
                Inches(branch_x),
                Inches(by),
                Inches(branch_w),
                Inches(branch_h),
            )
            b_shape.fill.solid()
            b_shape.fill.fore_color.rgb = card_bg_rgb
            b_shape.line.color.rgb = accent_rgb
            b_shape.line.width = Pt(1.5)

            tf = b_shape.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            p.text = branch.label
            p.alignment = PP_ALIGN.CENTER
            p.font.name = deck_font
            p.font.size = Pt(10)
            p.font.bold = True
            p.font.color.rgb = text_default_rgb

            # Connector root -> branch
            rx = root_x + root_w
            ry = root_y + root_h / 2.0
            bx_mid = branch_x
            by_mid = by + branch_h / 2.0
            conn = slide.shapes.add_connector(
                MSO_CONNECTOR.ELBOW,
                Inches(rx),
                Inches(ry),
                Inches(bx_mid),
                Inches(by_mid),
            )
            conn.line.color.rgb = accent_rgb
            conn.line.width = Pt(1.5)

            # Leaves for this branch
            leaves = branch.children
            if leaves:
                num_leaves = len(leaves)
                leaf_w = min(1.8, width * 0.28)
                leaf_h = min(0.42, height / max(1, total_nodes * 0.9))
                leaf_x = left + width * 0.68

                sub_span = max(branch_h, (num_leaves - 1) * (leaf_h + 0.10) + leaf_h)
                leaf_start_y = by_mid - sub_span / 2.0
                for li, leaf in enumerate(leaves):
                    ly = leaf_start_y + li * (leaf_h + 0.10)
                    ly = max(top + 0.05, min(top + height - leaf_h - 0.05, ly))
                    l_shape = slide.shapes.add_shape(
                        MSO_SHAPE.ROUNDED_RECTANGLE,
                        Inches(leaf_x),
                        Inches(ly),
                        Inches(leaf_w),
                        Inches(leaf_h),
                    )
                    l_shape.fill.solid()
                    l_shape.fill.fore_color.rgb = card_bg_rgb
                    l_shape.line.color.rgb = line_rgb
                    l_shape.line.width = Pt(1.0)

                    tf = l_shape.text_frame
                    tf.word_wrap = True
                    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                    p = tf.paragraphs[0]
                    p.text = leaf.label
                    p.alignment = PP_ALIGN.CENTER
                    p.font.name = deck_font
                    p.font.size = Pt(9)
                    p.font.color.rgb = text_default_rgb

                    l_conn = slide.shapes.add_connector(
                        MSO_CONNECTOR.ELBOW,
                        Inches(branch_x + branch_w),
                        Inches(by_mid),
                        Inches(leaf_x),
                        Inches(ly + leaf_h / 2.0),
                    )
                    l_conn.line.color.rgb = line_rgb
                    l_conn.line.width = Pt(1.0)

        return True
    except Exception as exc:
        log.warning("failed to draw native mindmap shapes: %s", exc)
        return False


def add_native_diagram(
    slide: Any,
    dia_spec: dict[str, Any],
    *,
    left: Any,
    top: Any,
    width: Any,
    height: Any,
    colors: dict[str, Any] | None = None,
    palette: str = "atelier",
    font_name: str | None = None,
) -> bool:
    """Render a diagram into native PowerPoint vector shapes and connectors.

    Supported types: 'flowchart', 'timeline', 'mindmap'.
    Returns True if successfully drawn; False if unsupported or density exceeded (triggers fallback).
    """
    if not dia_spec or not isinstance(dia_spec, dict):
        return False
    dtype = str(dia_spec.get("type", "")).strip().lower()
    mermaid = str(dia_spec.get("mermaid", "")).strip()
    if not mermaid:
        return False

    l_in = _to_inches(left)
    t_in = _to_inches(top)
    w_in = _to_inches(width)
    h_in = _to_inches(height)
    colors_dict = colors or {}
    font = font_name or "Calibri"

    if dtype == "flowchart":
        graph = parse_mermaid_flowchart(mermaid)
        if not graph or not graph.nodes:
            return False
        if len(graph.nodes) > 10:
            log.info("flowchart %s has %d nodes (>10) — falling back to raster PNG", dia_spec.get("id"), len(graph.nodes))
            return False
        return _draw_native_flowchart(
            slide, dia_spec, graph,
            left=l_in, top=t_in, width=w_in, height=h_in,
            colors=colors_dict, palette=palette, font_name=font,
        )
    elif dtype == "timeline":
        tl_spec = parse_mermaid_timeline(mermaid)
        if not tl_spec or not tl_spec.periods:
            return False
        return _draw_native_timeline(
            slide, dia_spec, tl_spec,
            left=l_in, top=t_in, width=w_in, height=h_in,
            colors=colors_dict, palette=palette, font_name=font,
        )
    elif dtype == "mindmap":
        root_node = parse_mermaid_mindmap(mermaid)
        if not root_node:
            return False
        return _draw_native_mindmap(
            slide, dia_spec, root_node,
            left=l_in, top=t_in, width=w_in, height=h_in,
            colors=colors_dict, palette=palette, font_name=font,
        )

    return False

