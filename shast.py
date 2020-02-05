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
        return bytes(self.input[self.start:self.end]).decode("utf8")

    def __repr__(self):
        return f"<{self.name} {self.start}:{self.end}>"

    def __len__(self):
        return self.len

class Token:
    def __init__(self, name, x):
        x = x.encode("utf8")
        self.name = name
        self.tok = re.compile(x)

    def _match(self, input, start):
        m = self.tok.match(bytes(input[start:]))
        if m:
            return AST(self.name, input, start + m.start(), start + m.end())

    def __repr__(self):
        return f"{self.name}"

class Production:
    # does not support backtracking so far (no need)
    def __init__(self, name=None, prod=None):
        self.name = name
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
        return AST(self.name, input, start, end, children)

    def __or__(self, other):
        if not isinstance(other, Production):
            raise ValueError(f"invalid production value: {prod}: not a production")
        self._productions.extend(other._productions)
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

# not shlex, shast
class shast(Parser):
    # in a class just so i can use
    # __set_, name__ for debugging/printing the ast
    # sue me

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
    ARGCHAR = Token("ARGCHAR", r'[^"\'\s\|;>]')

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

    Invocation  = Production("Invocation")
    Invocation |= Production("Invocation", prod=[Arg, WS, Invocation])
    Invocation |= Production("Invocation", prod=[Arg])

    Pipeline  = Production("Pipeline")
    EPipeline = Production("EPipeline", prod=[PIPE, Pipeline]) | Empty
    Pipeline |= Production("Pipeline", prod=[WSE, Invocation, WSE, EPipeline])

    EmptyCommand = Production("EmptyCommand")
    EmptyCommand |= Production("Pipeline", [Pipeline])
    EmptyCommand |= Production("Empty", [Empty])

    Group = Production("Group")
    EGroup = Production("EGroup", prod=[SEMICOLON, Group]) | Empty
    Group |= Production("Group", prod=[EmptyCommand, EGroup])

    Program = Production("Program", [Group])

    def args(self, invocation):
        yield invocation.Arg
        try:
            for x in self.args(invocation.Invocation):
                yield x
        except AttributeError:
            pass

    def invocations(self, pipeline):
        yield pipeline.Invocation
        try:
            for x in self.invocations(pipeline.EPipeline.Pipeline):
                yield x
        except AttributeError:
            pass

    def commands(self, group=None):
        for x in self._commands(self.ast.Group):
            yield x

    def _commands(self, group):
        try:
            yield group.EmptyCommand.Pipeline
        except AttributeError:
            pass

        try:
            for x in self._commands(group.EGroup.Group):
                yield x
        except AttributeError:
            pass
