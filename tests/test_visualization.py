"""VIS-01: дерево синтаксичного виводу — текст, JSON, DOT, SVG."""
import json
import xml.etree.ElementTree as ET
from collections import Counter

import pytest

from sipl.parser import parse_tree
from sipl.source import SiplSyntaxError
from sipl.visualization import ParseTreeView, export_parse_tree
from sipl.visualization import svg as svg_mod
from sipl.visualization.parse_tree_view import dot_escape, walk

EUCLID = "begin\n  while ¬ M = N do\n    if M > N then M := M - N\n    else N := N - M\nend"
SIMPLE = "begin x := 1 end"


def view(src=EUCLID):
    return ParseTreeView(src)


def nodes_of(src):
    return [n for _, n, _, _ in walk(parse_tree(src))]


# ---------- приймальний тест: приклад із посібника ----------
def test_euclid_tree_has_the_shape_of_the_course_figure():
    counts = Counter(n.symbol for n in nodes_of(EUCLID) if not n.terminal)
    assert counts == {"<програма>": 1, "<оператор>": 4, "<умова>": 3, "<вираз>": 10, "<змінна>": 10}
    leaves = [n.symbol for n in nodes_of(EUCLID) if n.terminal]
    assert len(leaves) == 24


# ---------- текст ----------
def test_text_has_one_line_per_node_and_rule_names():
    v = view()
    lines = v.to_text().splitlines()
    assert len(lines) == v.node_count()
    assert lines[0].startswith("<програма> [NP1]")
    assert any("<оператор> [NS4]" in line for line in lines)
    assert any("<змінна> [NV]" in line for line in lines)


def test_text_shows_source_positions():
    lines = view(SIMPLE).to_text().splitlines()
    assert lines[0].endswith("1:1-1:17")          # вся програма
    assert any(line.strip().endswith("1:7-1:8") and " x " in line + " " for line in lines)


def test_text_uses_tree_drawing_characters():
    text = view().to_text()
    assert "├── " in text and "└── " in text and "│   " in text


# ---------- JSON ----------
def test_json_is_valid_and_has_stable_keys():
    data = json.loads(view().to_json())
    assert set(data) == {"id", "symbol", "terminal", "rule", "span", "text", "children"}
    assert data["symbol"] == "<програма>" and data["rule"] == "NP1"
    assert set(data["span"]) == {"start", "end"}
    assert set(data["span"]["start"]) == {"offset", "line", "column"}


def test_json_nodes_link_to_exact_source_fragments():
    src = EUCLID

    def check(d):
        s, e = d["span"]["start"]["offset"], d["span"]["end"]["offset"]
        assert d["text"] == src[s:e]
        for c in d.get("children", []):
            check(c)

    check(json.loads(view(src).to_json()))


def test_json_ids_are_unique_and_sequential():
    ids = []

    def collect(d):
        ids.append(d["id"])
        for c in d.get("children", []):
            collect(c)

    collect(view().to_dict())
    assert ids == list(range(1, len(ids) + 1))


def test_json_leaves_are_terminals_without_children():
    def leaves(d):
        if d["terminal"]:
            assert "children" not in d and d["rule"] is None
            yield d["symbol"]
        else:
            for c in d["children"]:
                yield from leaves(c)

    assert "".join(leaves(view("begin x := 1 end").to_dict())) == "beginx:=1end"


# ---------- DOT ----------
def test_dot_structure_and_counts():
    v = view()
    dot = v.to_dot()
    n = v.node_count()
    assert dot.startswith("digraph SIPL_ParseTree {") and dot.rstrip().endswith("}")
    assert dot.count("[label=") == n
    assert dot.count(" -> ") == n - 1


def test_dot_keeps_cyrillic_readable():
    dot = view().to_dot()
    assert "<оператор>" in dot and "<програма>" in dot
    assert "\\u04" not in dot


def test_dot_escape():
    assert dot_escape('a"b\\c\nd') == 'a\\"b\\\\c\\nd'


def test_dot_tooltips_contain_source_fragment():
    assert "x := 1" in view(SIMPLE).to_dot()


# ---------- SVG ----------
def svg_root(src=EUCLID):
    return ET.fromstring(view(src).to_svg())


NS = {"s": "http://www.w3.org/2000/svg"}


def test_svg_is_well_formed_xml_with_size():
    root = svg_root()
    assert root.tag.endswith("svg")
    assert float(root.get("width")) > 0 and float(root.get("height")) > 0


def test_svg_has_a_group_per_node_and_an_edge_per_link():
    v = view()
    root = ET.fromstring(v.to_svg())
    groups = [g for g in root.iter("{http://www.w3.org/2000/svg}g") if g.get("class") == "node"]
    lines = [e for e in root.iter("{http://www.w3.org/2000/svg}line") if e.get("class") == "edge"]
    assert len(groups) == v.node_count()
    assert len(lines) == v.node_count() - 1


def test_svg_nodes_carry_source_offsets_and_tooltip():
    src = SIMPLE
    root = ET.fromstring(view(src).to_svg())
    titles = {}
    for g in root.iter("{http://www.w3.org/2000/svg}g"):
        if g.get("class") != "node":
            continue
        s, e = int(g.get("data-start")), int(g.get("data-end"))
        title = g.find("{http://www.w3.org/2000/svg}title").text
        assert title.startswith(src[s:e])
        titles[g.get("data-id")] = title
    assert any(t.startswith("x := 1") for t in titles.values())


def test_svg_contains_cyrillic_labels():
    assert "&lt;оператор&gt;" in view().to_svg()


def test_svg_nodes_on_same_level_do_not_overlap():
    root = parse_tree(EUCLID)
    pos = svg_mod.layout(root)
    by_depth = {}
    for _, node, _, depth in walk(root):
        cx, _ = pos[id(node)]
        w = svg_mod._node_width(node)
        by_depth.setdefault(depth, []).append((cx - w / 2, cx + w / 2))
    for boxes in by_depth.values():
        boxes.sort()
        for (_, right), (left, _) in zip(boxes, boxes[1:]):
            assert right <= left


def test_svg_parent_is_centered_over_its_children():
    root = parse_tree(EUCLID)
    pos = svg_mod.layout(root)
    first, last = root.children[0], root.children[-1]
    assert pos[id(root)][0] == pytest.approx((pos[id(first)][0] + pos[id(last)][0]) / 2)


# ---------- експорт та помилки ----------
def test_export_writes_four_utf8_files(tmp_path):
    paths = export_parse_tree(EUCLID, tmp_path / "out" / "tree")
    assert sorted(p.suffix for p in paths) == [".dot", ".json", ".svg", ".txt"]
    assert "<програма>" in (tmp_path / "out" / "tree.txt").read_text(encoding="utf-8")
    json.loads((tmp_path / "out" / "tree.json").read_text(encoding="utf-8"))


def test_invalid_program_raises_syntax_error():
    with pytest.raises(SiplSyntaxError):
        ParseTreeView("begin x := end")


def test_example_files_can_be_visualized():
    from pathlib import Path
    examples = Path(__file__).resolve().parent.parent / "examples"
    files = sorted(examples.glob("*.sipl"))
    assert len(files) >= 3
    for f in files:
        ParseTreeView(f.read_text(encoding="utf-8")).to_svg()


# ---------- нумерація листків (порядок обходу, рис. 1 практикуму) ----------
POWER = """begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end"""

TEXTBOOK_LEAVES = ("1 begin 2 R 3 := 4 1 5 ; 6 while 7 Y 8 > 9 0 10 do 11 begin 12 R 13 := 14 R "
                   "15 * 16 X 17 ; 18 Y 19 := 20 Y 21 - 22 1 23 end 24 end")


def test_leaf_sequence_matches_the_textbook_figure():
    assert view(POWER).leaf_sequence() == TEXTBOOK_LEAVES


def test_text_marks_leaves_with_their_order_number():
    lines = view(POWER).to_text().splitlines()
    assert any(line.lstrip(" │├└─").startswith("[1] begin") for line in lines)
    assert any(line.lstrip(" │├└─").startswith("[24] end") for line in lines)
    assert lines[0].startswith("<програма> [NP1]")                  # нетермінали без номера


def test_text_with_leaves_appends_the_traversal_line():
    text = view(POWER).to_text(leaves=True)
    assert text.rstrip().splitlines()[-1] == "Обхід листків зліва направо: " + TEXTBOOK_LEAVES
    assert "Обхід листків" not in view(POWER).to_text()


def test_json_leaves_have_sequential_order_and_nonterminals_have_none():
    orders = []

    def collect(d):
        if d["terminal"]:
            orders.append(d["order"])
        else:
            assert "order" not in d
            for c in d["children"]:
                collect(c)

    collect(view(POWER).to_dict())
    assert orders == list(range(1, 25))


def test_dot_labels_leaves_with_order_number():
    dot = view(POWER).to_dot()
    assert 'label="[1] begin"' in dot and 'label="[24] end"' in dot
    assert 'label="[13] :="' in dot


def test_svg_has_one_red_number_per_leaf_in_order():
    root = ET.fromstring(view(POWER).to_svg())
    ns = "{http://www.w3.org/2000/svg}"
    numbers = [t.text for t in root.iter(ns + "text") if t.get("class") == "order"]
    assert numbers == [str(i) for i in range(1, 25)]
    leaves = [g for g in root.iter(ns + "g") if g.get("data-order")]
    assert [g.get("data-order") for g in leaves] == numbers


def test_svg_order_numbers_do_not_overlap_any_node():
    root = parse_tree(POWER)
    pos = svg_mod.layout(root)
    numbers = {id(leaf): n for n, leaf in enumerate(root.leaves(), start=1)}

    def top_of(depth):
        return svg_mod.MARGIN + depth * (svg_mod.NODE_H + svg_mod.V_GAP)

    boxes = []
    for _, node, _, depth in walk(root):
        cx, _ = pos[id(node)]
        w = svg_mod._node_width(node)
        boxes.append((cx - w / 2, top_of(depth), cx + w / 2, top_of(depth) + svg_mod.NODE_H))
    for _, node, _, depth in walk(root):
        if not node.terminal:
            continue
        cx, _ = pos[id(node)]
        w = svg_mod._node_width(node)
        right = cx - w / 2 + 1
        left = right - 7 * len(str(numbers[id(node)]))          # ~7 пікселів на цифру
        label_box = (left, top_of(depth) - 13, right, top_of(depth) - 2)
        for (x1, y1, x2, y2) in boxes:
            assert label_box[2] <= x1 or label_box[0] >= x2 or label_box[3] <= y1 or label_box[1] >= y2


def test_cli_tree_text_prints_leaf_traversal(tmp_path):
    import contextlib
    import io

    from sipl.cli import main
    path = tmp_path / "p.sipl"
    path.write_text(POWER, encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert main(["tree", str(path)]) == 0
    assert out.getvalue().rstrip().endswith("Обхід листків зліва направо: " + TEXTBOOK_LEAVES)
