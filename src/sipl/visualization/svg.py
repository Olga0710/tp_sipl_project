"""SVG-малюнок дерева виводу без зовнішніх залежностей (Graphviz не потрібен).

Розкладка: листки займають послідовні місця зліва направо, батько центрується над дітьми.
Кожен вузол — <g class="node"> з атрибутами data-* (правило, зсуви в тексті) і <title>
із фрагментом вихідного коду (підказка при наведенні).
"""
from __future__ import annotations

from typing import Optional
from xml.sax.saxutils import escape, quoteattr

from ..parse_tree import ParseNode
from .parse_tree_view import leaf_numbers, span_str

CHAR_W = 8.4
PAD_X = 12
NODE_H = 40
V_GAP = 44
H_GAP = 10
MARGIN = 20
FONT = 14


def _node_width(node: ParseNode) -> float:
    longest = len(node.symbol) if node.terminal else max(len(node.symbol), len(node.rule or ""))
    return longest * CHAR_W + 2 * PAD_X


def _measure(node: ParseNode) -> float:
    own = _node_width(node)
    if not node.children:
        return own
    kids = sum(_measure(c) for c in node.children) + H_GAP * (len(node.children) - 1)
    return max(own, kids)


def _place(node: ParseNode, left: float, depth: int, out: dict[int, tuple[float, int]]) -> float:
    """Розставити піддерево в смузі, що починається з left; повертає x центру вузла."""
    block = _measure(node)
    if not node.children:
        cx = left + block / 2
    else:
        kids_total = sum(_measure(c) for c in node.children) + H_GAP * (len(node.children) - 1)
        x = left + (block - kids_total) / 2
        centers = []
        for child in node.children:
            centers.append(_place(child, x, depth + 1, out))
            x += _measure(child) + H_GAP
        cx = (centers[0] + centers[-1]) / 2
    out[id(node)] = (cx, depth)
    return cx


def layout(root: ParseNode) -> dict[int, tuple[float, int]]:
    """id(вузла) -> (x центру, глибина). Корінь займає смугу з x = MARGIN."""
    out: dict[int, tuple[float, int]] = {}
    _place(root, MARGIN, 0, out)
    return out


def to_svg(root: ParseNode, source: Optional[str] = None) -> str:
    pos = layout(root)
    numbers = leaf_numbers(root)
    max_depth = max(d for _, d in pos.values())
    width = _measure(root) + 2 * MARGIN
    height = (max_depth + 1) * NODE_H + max_depth * V_GAP + 2 * MARGIN

    def y_top(depth: int) -> float:
        return MARGIN + depth * (NODE_H + V_GAP)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{FONT}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#555"/>'
        "</marker></defs>",
        f'<rect width="{width:.0f}" height="{height:.0f}" fill="#ffffff"/>',
    ]

    # ребра
    def edges(node: ParseNode) -> None:
        px, pd = pos[id(node)]
        for child in node.children:
            cx, cd = pos[id(child)]
            parts.append(
                f'<line class="edge" x1="{px:.1f}" y1="{y_top(pd) + NODE_H:.1f}" '
                f'x2="{cx:.1f}" y2="{y_top(cd) - 1:.1f}" stroke="#555" stroke-width="1.2" '
                'marker-end="url(#arrow)"/>'
            )
            edges(child)

    edges(root)

    # вузли
    node_id = 0

    def draw(node: ParseNode) -> None:
        nonlocal node_id
        node_id += 1
        cx, depth = pos[id(node)]
        w, top = _node_width(node), y_top(depth)
        s, e = node.span.start, node.span.end
        tip = span_str(node.span)
        if source is not None:
            tip = f"{node.span.text(source)}\n({tip})"
        order = f' data-order="{numbers[id(node)]}"' if node.terminal else ""
        attrs = (
            f'class="node" data-id="{node_id}"{order} data-rule={quoteattr(node.rule or "")} '
            f'data-start="{s.offset}" data-end="{e.offset}" data-line="{s.line}" data-column="{s.column}"'
        )
        parts.append(f"<g {attrs}>")
        parts.append(f"<title>{escape(tip)}</title>")
        if node.terminal:
            parts.append(
                f'<rect x="{cx - w / 2:.1f}" y="{top:.1f}" width="{w:.1f}" height="{NODE_H}" rx="{NODE_H / 2}" '
                'fill="#fff4cc" stroke="#b8860b"/>'
            )
            parts.append(
                f'<text x="{cx:.1f}" y="{top + NODE_H / 2 + 5:.1f}" text-anchor="middle" '
                f'font-style="italic" fill="#222">{escape(node.symbol)}</text>'
            )
            parts.append(                                   # номер листка в порядку обходу (як на рис. 1)
                f'<text class="order" x="{cx - w / 2 + 1:.1f}" y="{top - 2:.1f}" text-anchor="end" '
                f'font-size="11" font-weight="bold" fill="#d62828">{numbers[id(node)]}</text>'
            )
        else:
            parts.append(
                f'<rect x="{cx - w / 2:.1f}" y="{top:.1f}" width="{w:.1f}" height="{NODE_H}" rx="6" '
                'fill="#e6f0ff" stroke="#3b6fb6"/>'
            )
            parts.append(
                f'<text x="{cx:.1f}" y="{top + 17:.1f}" text-anchor="middle" fill="#222">{escape(node.symbol)}</text>'
            )
            parts.append(
                f'<text x="{cx:.1f}" y="{top + 33:.1f}" text-anchor="middle" font-size="11" '
                f'fill="#3b6fb6">{escape(node.rule or "")}</text>'
            )
        parts.append("</g>")
        for child in node.children:
            draw(child)

    draw(root)
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
