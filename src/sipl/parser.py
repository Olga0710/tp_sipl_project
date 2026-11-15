"""Парсер SIPL (метод рекурсивного спуску): текст -> дерево розбору -> AST.

"""
from __future__ import annotations

from . import ast
from .ast_builder import build_ast
from .lexer import Lexer, Token, TokenKind as K
from .parse_tree import ParseNode, leaf, merged_leaf, node
from .source import Diagnostic, SiplSyntaxError

PROGRAM, STMT, EXPR, COND, VAR, NUM = "<програма>", "<оператор>", "<вираз>", "<умова>", "<змінна>", "<число>"

REL_RULES = {K.EQ: "NB1", K.GT: "NB2"}
# Токени, після яких закрита дужка означає, що дужки були у ВИРАЗІ (NA6), а не в умові (NB5)
_EXPR_CONTINUATION = {K.PLUS, K.MINUS, K.STAR, K.EQ, K.GT}


def parse_tree(source: str) -> ParseNode:
    """Дерево синтаксичного виводу. Кидає SiplSyntaxError."""
    return _Parser(Lexer(source).tokenize()).parse_program()


def parse(source: str) -> ast.Program:
    """Абстрактне синтаксичне дерево (AST). Кидає SiplSyntaxError."""
    return build_ast(parse_tree(source))


class _Parser:
    def __init__(self, tokens: list[Token]):
        self._toks = tokens
        self._i = 0

    # ---------- допоміжні ----------
    @property
    def _cur(self) -> Token:
        return self._toks[self._i]

    def _peek(self, k: int = 1) -> Token:
        return self._toks[min(self._i + k, len(self._toks) - 1)]

    def _next(self) -> Token:
        tok = self._cur
        if tok.kind is not K.EOF:
            self._i += 1
        return tok

    def _at(self, *kinds: K) -> bool:
        return self._cur.kind in kinds

    @staticmethod
    def _describe(tok: Token) -> str:
        return "кінець програми" if tok.kind is K.EOF else f"'{tok.text}'"

    def _error(self, message: str) -> SiplSyntaxError:
        return SiplSyntaxError(Diagnostic(message, self._cur.span))

    def _expect(self, kind: K, what: str, hint: str = "") -> ParseNode:
        if self._cur.kind is kind:
            return leaf(self._next())
        msg = f"Очікувалося {what}, а знайдено {self._describe(self._cur)}"
        if hint:
            msg += f". {hint}"
        raise self._error(msg)

    # ---------- <програма> ::= begin <оператор> end   (NP1) ----------
    def parse_program(self) -> ParseNode:
        begin = self._expect(K.BEGIN, "'begin' (програма SIPL має вигляд begin ... end)")
        body = self._parse_statement()
        end = self._expect(K.END, "'end'", "Можливо, пропущено ';' між операторами")
        if not self._at(K.EOF):
            raise self._error("Після завершального 'end' програми знайдено зайвий текст")
        return node(PROGRAM, "NP1", [begin, body, end])

    # ---------- <оператор> ; <оператор>   (NS2) ----------
    def _parse_statement(self) -> ParseNode:
        parts = [self._parse_simple()]
        semis: list[ParseNode] = []
        while self._at(K.SEMI):
            semis.append(leaf(self._next()))
            parts.append(self._parse_simple())
        acc = parts[-1]
        for i in range(len(parts) - 2, -1, -1):      # ';' асоціативна праворуч
            acc = node(STMT, "NS2", [parts[i], semis[i], acc])
        return acc

    def _parse_simple(self) -> ParseNode:
        kind = self._cur.kind
        if kind is K.IDENT:
            return self._parse_assign()
        if kind is K.IF:
            return self._parse_if()
        if kind is K.WHILE:
            return self._parse_while()
        if kind is K.BEGIN:
            return self._parse_block()
        if kind is K.SKIP:
            return node(STMT, "NS6", [leaf(self._next())])
        raise self._error(
            "Очікувався оператор (присвоювання, if, while, begin або skip), "
            f"а знайдено {self._describe(self._cur)}"
        )

    def _variable(self) -> ParseNode:                              # NV
        return node(VAR, "NV", [leaf(self._next())])

    def _parse_assign(self) -> ParseNode:                          # NS1
        var = self._variable()
        assign = self._expect(K.ASSIGN, "':='")
        return node(STMT, "NS1", [var, assign, self._parse_expr()])

    def _parse_if(self) -> ParseNode:                              # NS3
        kw = leaf(self._next())
        cond = self._parse_cond()
        then_kw = self._expect(K.THEN, "'then'")
        then = self._parse_simple()
        else_kw = self._expect(K.ELSE, "'else'",
                               "У SIPL розгалуження завжди має гілку else (використайте skip)")
        orelse = self._parse_simple()
        return node(STMT, "NS3", [kw, cond, then_kw, then, else_kw, orelse])

    def _parse_while(self) -> ParseNode:                           # NS4
        kw = leaf(self._next())
        cond = self._parse_cond()
        do_kw = self._expect(K.DO, "'do'")
        return node(STMT, "NS4", [kw, cond, do_kw, self._parse_simple()])

    def _parse_block(self) -> ParseNode:                           # NS5
        begin = leaf(self._next())
        inner = self._parse_statement()
        end = self._expect(K.END, "'end'", "Можливо, пропущено ';' між операторами")
        return node(STMT, "NS5", [begin, inner, end])

    # ---------- <умова> ----------
    def _parse_cond(self) -> ParseNode:
        left = self._parse_not()
        while self._at(K.OR):                                       # NB3
            op = leaf(self._next())
            left = node(COND, "NB3", [left, op, self._parse_not()])
        return left

    def _parse_not(self) -> ParseNode:
        if self._at(K.NOT):                                         # NB4
            op = leaf(self._next())
            return node(COND, "NB4", [op, self._parse_not()])
        return self._parse_cond_atom()

    def _paren_is_condition(self) -> bool:
        """Поточний токен '('. Чи це дужки навколо УМОВИ (NB5), а не виразу (NA6)?

        Знаходимо парну ')' і дивимось, що йде після неї: арифметична операція чи
        порівняння означають, що дужки були частиною виразу.
        """
        depth = 0
        j = self._i
        while self._toks[j].kind is not K.EOF:
            if self._toks[j].kind is K.LPAREN:
                depth += 1
            elif self._toks[j].kind is K.RPAREN:
                depth -= 1
                if depth == 0:
                    return self._toks[j + 1].kind not in _EXPR_CONTINUATION
            j += 1
        return False        # дужка не закрита: розбиратимемо як вираз і повідомимо про помилку

    def _parse_cond_atom(self) -> ParseNode:
        if self._at(K.LPAREN) and self._paren_is_condition():       # NB5
            lp = leaf(self._next())
            inner = self._parse_cond()
            rp = self._expect(K.RPAREN, "')'")
            return node(COND, "NB5", [lp, inner, rp])
        left = self._parse_expr()                                   # NB1, NB2
        if not self._at(*REL_RULES):
            raise self._error(
                f"Очікувався оператор порівняння '=' або '>', а знайдено {self._describe(self._cur)}"
            )
        rule = REL_RULES[self._cur.kind]
        op = leaf(self._next())
        return node(COND, rule, [left, op, self._parse_expr()])

    # ---------- <вираз>: '*' сильніше за '+' і '-' ----------
    def _parse_expr(self) -> ParseNode:
        left = self._parse_term()
        while self._at(K.PLUS, K.MINUS):                            # NA3, NA4
            rule = "NA3" if self._cur.kind is K.PLUS else "NA4"
            op = leaf(self._next())
            left = node(EXPR, rule, [left, op, self._parse_term()])
        return left

    def _parse_term(self) -> ParseNode:
        left = self._parse_factor()
        while self._at(K.STAR):                                     # NA5
            op = leaf(self._next())
            left = node(EXPR, "NA5", [left, op, self._parse_factor()])
        return left

    def _parse_factor(self) -> ParseNode:
        tok = self._cur
        if tok.kind is K.NUMBER:                                    # NA1 -> NN
            self._next()
            return node(EXPR, "NA1", [node(NUM, "NN", [leaf(tok)])])
        if tok.kind is K.MINUS and self._peek().kind is K.NUMBER:   # від'ємна константа -> NN
            self._next()
            num = self._next()
            lit = merged_leaf("-" + num.text, tok, num)
            return node(EXPR, "NA1", [node(NUM, "NN", [lit])])
        if tok.kind is K.IDENT:                                     # NA2 -> NV
            return node(EXPR, "NA2", [self._variable()])
        if tok.kind is K.LPAREN:                                    # NA6
            lp = leaf(self._next())
            inner = self._parse_expr()
            rp = self._expect(K.RPAREN, "')'")
            return node(EXPR, "NA6", [lp, inner, rp])
        raise self._error(
            f"Очікувався вираз (число, змінна або дужки), а знайдено {self._describe(tok)}"
        )
