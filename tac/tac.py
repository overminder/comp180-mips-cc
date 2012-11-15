import sys

"""Three Address Code.
Generally speaking, we are going to implement the following operations:
    Assignment x := y  ; la / li / lui + addi
    Unary op   x := op y  ; neg ++ --
    Binary op  x := y op z  ; z can be reg or imm. most of work here...
    Address of x := & y  ; y must be a symbol and in mem
    Load       x := *(p + c)  ; c can be reg or imm, different
    Store      *(p + c) := y  ; c can be reg or imm
    Call       x := f()  ; calling conversion, func name mangling
    Branch     goto L1  ; label naming
    Cbranch    if (y) goto L1  ; beq
    Label      L1
    Ret        y
    Comment    # x
    Push       from y
    Pop        to x
    Syscall    f(y)
    Func_Begin x
    Func_End   x

    Mac_Begin  x
    Mac_End    x

    impl detail:
    we have x, y, z, p, c, f, L
    in the class.

    important concept:
    basic block, where only one variable is returned.
    (just like what i've done in my naive tac-tree impl...)
"""

ASSIGN = 0
UNARY = 1
BINARY = 2
ADDROF = 3
LOAD = 4
STORE = 5
CALL = 6
BRANCH = 7
CBRANCH = 8
LABEL = 9
RET = 10
COMMENT = 11
PUSH_ARG = 12  # for caller to use  z y x
POP_ARG = 13  # for callee to use  x y z
SYSCALL = 14
FUNC_BEGIN = 15
FUNC_END = 16
MAC_BEGIN = 17
MAC_END = 18

code_mapper = [t[1] for t in sorted(((value, key)
               for key, value in locals().iteritems()
               if key.upper() == key and
               not key.startswith('_')), key=lambda t: t[0])]

_MAX = len(code_mapper) + 1
TEMP_VAR_PREFIX = 't'

def assign(x, y):
    t = Tac(ASSIGN)
    t.x = x
    t.y = y
    return t

def unary(x, op, y):
    t = Tac(UNARY)
    t.x = x
    t.y = y
    t.op = op
    return t

def binary(x, y, op, z):
    t = Tac(BINARY)
    t.x = x
    t.y = y
    t.z = z
    t.op = op
    return t

def addrof(x, y):
    t = Tac(ADDROF)
    t.x = x
    t.y = y
    return t

def load(x, p, c):
    t = Tac(LOAD)
    t.x = x
    t.p = p
    t.c = c
    return t

def store(p, c, y):
    t = Tac(STORE)
    t.y = y
    t.p = p
    t.c = c
    return t

def call(x, f):
    t = Tac(CALL)
    t.x = x
    t.f = f
    return t

def branch(L):
    t = Tac(BRANCH)
    t.L = L
    return t

def cbranch(y, L):
    t = Tac(CBRANCH)
    t.y = y
    t.L = L
    return t

def label(L):
    t = Tac(LABEL)
    t.L = L
    return t

def ret(y):
    t = Tac(RET)
    t.y = y
    return t

def comment(x):
    t = Tac(COMMENT)
    t.x = x
    return t

def pop_arg(x):
    t = Tac(POP_ARG)
    t.x = x
    return t

def push_arg(y):
    t = Tac(PUSH_ARG)
    t.y = y
    return t

def syscall(f, y):
    t = Tac(SYSCALL)
    t.f = f
    t.y = y
    return t

def func_begin(x):
    t = Tac(FUNC_BEGIN)
    t.x = x
    return t

def func_end(x):
    t = Tac(FUNC_END)
    t.x = x
    return t

def mac_begin(x):
    t = Tac(MAC_BEGIN)
    t.x = x
    return t

def mac_end(x):
    t = Tac(MAC_END)
    t.x = x
    return t

class Tac(object):
    def __init__(self, code_t):
        if code_t > _MAX:
            raise 'unknown code type: %d' % code_t
        self.code_t = code_t
        self.is_leader = False

    def typep(self, name):
        if isinstance(name, str):
            return code_mapper[self.code_t].startswith(name.upper())
        else:
            return any(map(self.typep, name))

    def immp(self, varname=None):
        if varname is None:
            if self.code_t == UNARY:
                return isinstance(self.y, int)
            if self.code_t == BINARY:
                return isinstance(self.y, int) and isinstance(self.z, int)
            return False
        else:
            return isinstance(self[varname], int)

    def fold(self):
        if self.code_t == UNARY:
            return int(eval('%s %s' % (self.op, self.y)))
        if self.code_t == BINARY:
            return int(eval('%s %s %s' % (self.y, self.op, self.z)))

    def xvals(self):  # that is modified
        if self.code_t in (ASSIGN, UNARY, BINARY, LOAD, CALL, POP_ARG):
            return (self.x, )
        else:
            return ()

    def yvals(self):  # that is used
        to_ret = ()
        if self.code_t in (ASSIGN, UNARY, CBRANCH, RET, PUSH_ARG, SYSCALL):
            to_ret = (self.y,)
        elif self.code_t == BINARY:
            to_ret = (self.y, self.z)
        elif self.code_t == LOAD:
            to_ret = (self.p,)
        elif self.code_t == STORE:
            to_ret = (self.p, self.y)
        return filter(lambda v: isinstance(v, str) and
                      v.startswith(TEMP_VAR_PREFIX),
                      to_ret)

    def varnames(self):
        if self.code_t in (ASSIGN, UNARY, ADDROF):
            to_ret = (self.x, self.y)
        elif self.code_t == BINARY:
            to_ret = (self.x, self.y, self.z)
        elif self.code_t == LOAD:
            to_ret = (self.x, self.p)
        elif self.code_t == STORE:
            to_ret = (self.y, self.p)
        elif self.code_t in (CALL, POP_ARG, SYSCALL):
            to_ret = (self.x,)
        elif self.code_t in (CBRANCH, RET, PUSH_ARG):
            to_ret = (self.y,)
        else:
            to_ret = ()
        return filter(lambda t: isinstance(t, str) and \
                t.startswith('t'), to_ret)

    def replace_var(self, v_from, v_to):
        for ch in 'xyzpcfL':
            if self[ch] == v_from:
                self[ch] = v_to

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, val):
        return setattr(self, key, val)

    def __repr__(self):
        repr_mapper = [
            '%(x)s := %(y)s',  # assign
            '%(x)s := %(op)s %(y)s',
            '%(x)s := %(y)s %(op)s %(z)s',
            '%(x)s := & %(y)s',
            '%(x)s := *(%(p)s + %(c)s)',
            '*(%(p)s + %(c)s) := %(y)s',
            '%(x)s := %(f)s()',
            'goto %(L)s',
            'if (%(y)s) goto %(L)s',
            '%(L)s:',  # label
            'ret %(y)s',  # return var
            '# %(x)s',  # comment
            'push %(y)s',  # for func call
            'pop arg as %(x)s',  # for func call
            'syscall %(f)s(%(y)s)',  # syscall, to be specified
            'Function %(x)s',  # for func block start
            'End %(x)s',  # func end
            'MACRO %(x)s',  # for macro block start
            'END MACRO %(x)s',  # macro end
        ]
        line = code_mapper[self.code_t].rjust(12) + \
               '    ' + (repr_mapper[self.code_t] % self).ljust(40)
        if self.is_leader:
            line += 'Leader'
        if self.code_t in (FUNC_END, MAC_END):
            line += '\n'
        return line

for c in 'xyzpcfL':
    def wrap():
        setattr(Tac, c, c)
    wrap()
Tac.op = 'op'

for i, t in enumerate(code_mapper):
    def wrap():
        def test(s):
            return code_mapper[s.code_t] == test._t
        setattr(Tac, 'is_%s' % t.lower(), test)
        test._t = t
    wrap()

# end of kls decl

def showall():
    for i in xrange(_MAX + 1):
        t1 = Tac(i)
        print t1

def test():
    to_show = [
        assign('t1', 0),
        label('loop_start'),
        binary('t2', 't1', '>', 10),
        cbranch('t2', 'loop_end'),
        binary('t1', 't1', '+', 1),
        branch('loop_start'),
        label('loop_end'),
    ]
    #map(lambda x: sys.stdout.write('%s\n' % x), to_show)

def pprint(tacs):
    for i, tac in enumerate(tacs):
        sys.stdout.write('%3d%s\n' % (i, tac))


if __name__ == '__main__':
    test()

