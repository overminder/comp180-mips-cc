"""
Howmany types do we have?
fun's return type + param types?
variable type? imm?
"""

import re
from err import CompileTimeError

# why not attach type to the symbol and literals?
obj_names = ['KEYWORD', 'SYMBOL', 'INTLITERAL', 'STRLITERAL', 'CHARLITERAL',
             'TYPENAME', 'PTRNAME']
for i, name in enumerate(obj_names):
    locals()[name] = i

keywords = set(['defun', 'defvar', 'print', 'let', 'set!', 'ref', 'nth',
    'set-nth!', 'cond', 'while', 'asm', 'require', 'and', 'or', 'not',
    'break', 'continue', 'defmacro'])
# macro: no type checking, but still a function (not inlined)
keywords = keywords.union(list('+-*/%'))
keywords = keywords.union(['<', '>', '<<', '>>', '=='])

typenames = set(['int', 'void', 'byte'])
ptrnames = set([t + '*' for t in typenames])
ptrnames = ptrnames.union(t + '*' for t in ptrnames)

def sizeof_byshift(t):
    if typenamep(t):
        if t == 'int':
            return 2
        if t == 'byte':
            return 0
        if t == 'void':
            raise CompileTimeError, 'dereferencing void pointer'
    elif ptrnamep(t):
        return 2  # pointer is a word wide so sll 2
    else:
        raise CompileTimeError, 'cannot do arithmatic on such type %r' % t

def keywordp(s):
    return s in keywords

def typenamep(s):
    return s in typenames

def ptrnamep(s):
    return s in ptrnames

def symbolp(s):
    return not (keywordp(s) or typenamep(s) or
                intliteralp(s) or strliteralp(s) or byteliteralp(s))

def intliteralp(s):
    return isinstance(s, int)

def strliteralp(s):
    return isinstance(s, str) and s.startswith('"') and s.endswith('"')

def byteliteralp(s):
    return isinstance(s, str) and s.startswith('\'') and s.endswith('\'')


# fields: t: token type. vt: variable type. n: name. v: value
class Token(object):
    """seems it contains too many things... refactor?"""
    def __init__(self, s):
        self.t = None  # token-type, a int
        self.vt = None # value-type, a string
        self.n = None  # name, str or int
        self.v = None  # value, used in decl and defi
        self.p = None  # params, used only in func
        self.st = None # on stack length, used in stack-allocated array
        self.tacn = None  # name in tac, a string

        if keywordp(s):
            self.t = KEYWORD
            self.n = s
        elif typenamep(s):
            self.t = TYPENAME
            self.vt = s
        elif ptrnamep(s):
            self.t = PTRNAME
            self.vt = s
        elif strliteralp(s):
            self.t = STRLITERAL
            self.vt = 'byte*'
            self.n = s  # for repr
            self.v = s  # the value
        elif isinstance(s, str) and ':' in s:  # is name:type
            first, second = s.split(':', 1)
            self.t = SYMBOL
            self.n = first
            is_array = re.search(r'(.+?)\[(\d*)\]', second)
            if is_array:
                ary_tp, ary_len = is_array.groups()
                self.vt = ary_tp + '*'
                self.st = ary_len
            else:
                self.vt = second
        elif intliteralp(s):
            self.t = INTLITERAL
            self.vt = 'int'
            self.n = s  # for repr
            self.v = s  # the value
        elif byteliteralp(s):
            self.t = CHARLITERAL
            self.vt = 'byte'
            self.n = ord(s[1:-1])  # for repr
            self.v = ord(s[1:-1])  # the value
        elif symbolp(s):
            self.t = SYMBOL
            self.n = s
        else:
            raise CompileTimeError, 'Unknown type: %s' % s

    def lvalue(self):
        if self.symbolp() and not self.p:
            return self
        else:
            raise CompileTimeError, '%r doesn\'t have a lvalue' % self

    def immp(self):
        return self.t in [INTLITERAL, STRLITERAL, CHARLITERAL]

    def can_cast_to(self, t):
        return self.vt == t.vt or self.vt == 'omni'

    def can_cast_to_type(self, s):
        return self.vt == s or self.vt == 'omni'

    def symbolp(self):
        return self.t == SYMBOL

    def keywordp(self):
        return self.t == KEYWORD

    def vtypep(self):
        return self.vt is not None

    def typep(self):
        """see if this is a type conv token"""
        return self.t in [TYPENAME, PTRNAME]

    def ptrp(self):
        return self.vt.endswith('*')

    def __repr__(self):
        if self.vt is not None:
            return '(%s %s %s)' % (obj_names[self.t], self.vt, self.n)
        else:
            return '(%s %s)' % (obj_names[self.t], self.n)

def tokenize(code):
    for i, item in enumerate(code):
        if isinstance(item, list):
            tokenize(item)
        else:
            code[i] = Token(item)

def test():
    import reader
    s = '''
    (defun (incr:void) (a:int*)
      (set-nth! a 0 (+ 1 (nth a 0))))
    (defun (main:void) ()
      (defvar a:int 5)  ; this is spartaaaa
      (incr (ref a))
      (print a))
    (defun (not-main:void) ()
      (let ((a:int 5)
            (b:byte* 8))
        (print b)
        (print a)))
'''
    c = reader.loads(s)
    print c
    tokenize(c)
    print c

if __name__ == '__main__':
    test()

