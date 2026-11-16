"""Перетворення дерева розбору (конкретний синтаксис) на AST (абстрактний синтаксис)."""
from __future__ import annotations

from . import ast
from .parse_tree import ParseNode


def build_ast(tree: ParseNode) -> ast.Program:
    """<програма> (NP1) -> Program."""
    return ast.Program(body=_stmt(tree.children[1]), span=tree.span)


def _name(var_node: ParseNode) -> str:            # NV
    return var_node.children[0].symbol


def _stmt(n: ParseNode) -> ast.Stmt:
    c, r = n.children, n.rule
    if r == "NS1":
        return ast.Assign(_name(c[0]), _expr(c[2]), n.span)
    if r == "NS2":
        return ast.Seq(_stmt(c[0]), _stmt(c[2]), n.span)
    if r == "NS3":
        return ast.If(_cond(c[1]), _stmt(c[3]), _stmt(c[5]), n.span)
    if r == "NS4":
        return ast.While(_cond(c[1]), _stmt(c[3]), n.span)
    if r == "NS5":
        return ast.Block(_stmt(c[1]), n.span)
    if r == "NS6":
        return ast.Skip(n.span)
    raise ValueError(f"Невідоме правило оператора: {r}")


def _expr(n: ParseNode) -> ast.Expr:
    c, r = n.children, n.rule
    if r == "NA1":
        return ast.Num(int(c[0].children[0].symbol), n.span)
    if r == "NA2":
        return ast.Var(_name(c[0]), n.span)
    if r in ("NA3", "NA4", "NA5"):
        return ast.BinOp(c[1].symbol, _expr(c[0]), _expr(c[2]), n.span)
    if r == "NA6":
        return _expr(c[1])                        # дужки в AST не зберігаються
    raise ValueError(f"Невідоме правило виразу: {r}")


def _cond(n: ParseNode) -> ast.Cond:
    c, r = n.children, n.rule
    if r in ("NB1", "NB2"):
        return ast.Compare(c[1].symbol, _expr(c[0]), _expr(c[2]), n.span)
    if r == "NB3":
        return ast.Or(_cond(c[0]), _cond(c[2]), n.span)
    if r == "NB4":
        return ast.Not(_cond(c[1]), n.span)
    if r == "NB5":
        return _cond(c[1])
    raise ValueError(f"Невідоме правило умови: {r}")
