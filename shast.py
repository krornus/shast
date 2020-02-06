import re

class AST:
    def __init__(self, name, input, start, end, children=[]):

        self.name = name
        self.input = input
        self.start = start
        self.end = end
        self.len = self.end - self.start

        if self.len < 0:
            raise ValueError("invalid start/end")
        self.children = children

        for child in children:
            setattr(self, child.name, child)

    def dump_tree(self, indent=0):
        print(" " * indent + self.name)
        if self.children is not None:
            for x in self.children:
                x.dump_tree(indent+1)

    def __str__(self):
        return bytes(self.input[self.start:self.end]).decode()

    def __repr__(self):
        return f"<{self.name} {self.start}:{self.end}>"

    def __len__(self):
        return self.len

class Token:
    def __init__(self, name, x, type=AST):
        x = x.encode("utf8")
        self.name = name
        self.tok = re.compile(x)
        self.ast = type

    def _match(self, input, start):
        m = self.tok.match(bytes(input[start:]))
        if m:
            return self.ast(self.name, input, start + m.start(), start + m.end())

    def __repr__(self):
        return f"{self.name}"

class Production:
    # does not support backtracking so far (no need)
    def __init__(self, name=None, prod=None, type=AST):
        self.name = name
        self.ast = type
        if prod == None:
            self._productions = []
        else:
            if not isinstance(prod, (list, tuple)):
                raise ValueError(f"invalid production value: {prod}: must be iterable")
            self._productions = [prod]

    def __set_name__(self, owner, name):
        self.name = name

    def match(self, input):
        input = memoryview(input)
        return self._match(input, 0)

    def _match(self, input, start):
        for opt in self._productions:
            x = self._single(opt, input, start)
            if x != None:
                return x

    def _single(self, opt, input, start):
        children = []
        end = start
        for pat in opt:
            m = pat._match(input, end)
            if m == None:
                return None
            end += len(m)
            children.append(m)
        return self.ast(self.name, input, start, end, children)

    def __or__(self, other):
        if not isinstance(other, Production):
            raise ValueError(f"invalid production value: {prod}: not a production")
        self._productions.extend(other._productions)
        if self.ast == AST and other.ast != AST:
            self.ast = other.ast

        return self

    def __repr__(self):
        opts = []
        for opt in self._productions:
            pats = []
            for pat in opt:
                pats.append(pat.name)
            opts.append(" ".join(pats))
        return f"{self.name}: " + " | ".join(opts)

class Parser:
    Program: Production

    def __init__(self, input):
        self.ast = self.Program.match(input)
        if not self.ast:
            raise ValueError(f"parsing error: parsing failed")
        if len(input) != len(self.ast):
            i = len(self.ast)
            c = chr(self.ast.input[-1])
            raise ValueError(f"parsing error: unexpected char near {i}: ({c})")

class InvocationNode(AST):
    def __iter__(self):
        yield self.Arg
        try:
            for x in self.Invocation:
                yield x
        except AttributeError:
            pass

    def args(self):
        for x in self:
            try:
                yield x.Text
            except AttributeError:
                pass

    def redirects(self):
        for x in self:
            try:
                yield x.Redirect
            except AttributeError:
                pass

class PipelineNode(AST):
    def __iter__(self):
        yield self.Invocation
        try:
            for x in self.EPipeline.Pipeline:
                yield x
        except AttributeError:
            pass

class GroupNode(AST):
    def __iter__(self):
        try:
            yield self.EmptyCommand.Pipeline
        except AttributeError:
            pass

        try:
            for x in self.EGroup.Group:
                yield x
        except AttributeError:
            pass

class shast(Parser):
    EMPTY = Token("EMPTY", r"")
    Empty = Production("Empty", prod=[EMPTY])

    WS  = Token("WS", r"[ \t]+")
    WSE = Token("WSE", r"[ \t]*")

    DQUOTE = Token("DQUOTE", r'"')
    SQUOTE = Token("SQUOTE", r"'")

    SEMICOLON = Token("SQUOTE", r";")
    PIPE = Token("PIPE", r"\|")
    REDIR = Token("REDIR", r">")

    ESC = Token("ESC", r"\\")
    STRCHAR = Token("STRCHAR", r'[^"\'\\]')
    ARGCHAR = Token("ARGCHAR", r'[^"\'\s\|;\(\)&>]')

    SChar = Production("SChar")
    ESChar = Production("ESChar", prod=[SChar]) | Empty
    SChar |= Production("SChar", prod=[STRCHAR, ESChar])
    SChar |= Production("SChar", prod=[DQUOTE, ESChar])
    SChar |= Production("SChar", prod=[ESC, SQUOTE, ESChar])

    DChar  = Production("DChar")
    EDChar = Production("EDChar", prod=[DChar]) | Empty
    DChar |= Production("DChar", prod=[STRCHAR, EDChar])
    DChar |= Production("DChar", prod=[SQUOTE, EDChar])
    DChar |= Production("DChar", prod=[ESC, DQUOTE, EDChar])

    SStr = Production("SStr", prod=[SQUOTE, SChar, SQUOTE])
    DStr = Production("DStr", prod=[DQUOTE, DChar, DQUOTE])
    Str = Production("Str", prod=[DStr]) | Production(prod=[SStr])

    Quote  = Production("Quote", prod=[DQUOTE])
    Quote |= Production("Quote", prod=[SQUOTE])

    Word  = Production("Word")
    EWord = Production("EWord", prod=[Word]) | Empty
    Word |= Production("Word", prod=[ARGCHAR, EWord])
    Word |= Production("Word", prod=[ESC, WS, EWord])
    Word |= Production("Word", prod=[ESC, Quote, EWord])

    Text  = Production("Text", prod=[Str]) | Production("Text", prod=[Word])

    FWrite  = Production("FWrite", prod=[REDIR, WSE, Text])
    FWriteA = Production("FWriteA", prod=[REDIR, REDIR, WSE, Text])

    Redirect  = Production("Redirect", prod=[FWrite])
    Redirect |= Production("Redirect", prod=[FWriteA])

    Arg  = Production("Arg")
    Arg |= Production("Arg", prod=[Text])
    Arg |= Production("Arg", prod=[Redirect])

    Invocation  = Production("Invocation", type=InvocationNode)
    Invocation |= Production("Invocation", prod=[Arg, WS, Invocation])
    Invocation |= Production("Invocation", prod=[Arg])

    Pipeline  = Production("Pipeline", type=PipelineNode)
    EPipeline = Production("EPipeline", prod=[PIPE, Pipeline]) | Empty
    Pipeline |= Production("Pipeline", prod=[WSE, Invocation, WSE, EPipeline])

    EmptyCommand = Production("EmptyCommand")
    EmptyCommand |= Production("Pipeline", [Pipeline])
    EmptyCommand |= Production("Empty", [Empty])

    Group = Production("Group", type=GroupNode)
    EGroup = Production("EGroup", prod=[SEMICOLON, Group]) | Empty
    Group |= Production("Group", prod=[EmptyCommand, EGroup])

    Program = Production("Program", [Group])

    def __iter__(self):
        for x in self.ast.Group:
            yield x

if __name__ == "__main__":
    ast = shast(b'echo "first line"; echo "second line"; echo "not second line" | grep -v first | sort -u > out.txt')
    for grp in ast:
        print(repr(grp), repr(str(grp)))
        for cmd in grp:
            print(" ", repr(cmd), repr(str(cmd)))

            for arg in cmd.args():
                print("  ", repr(arg), repr(str(arg)))

            for redirect in cmd.redirects():
                print("  ", repr(redirect), repr(str(redirect)))

