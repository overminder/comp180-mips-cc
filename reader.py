
def test():
    print loads('''
                   (defun incr:int (+ -1 -2))
                     ''')

def load(fp):
    fp.seek(0)
    return loads(fp.read())

def loads(s):
    s = XStr(s)
    to_ret = []
    s.strip()
    while not s.eof():
        to_ret.append(_loads(s))
        s.strip()
    return to_ret

def _loads(s):
    s.strip()
    c = s.peek(1)
    if c == ';' and not s.eof():
        while c != '\n':
            c = s.read(1)
        return _loads(s)  # no goto...

    s.strip()
    c = s.peek(1)
    if s.eof():
        return None

    if c == '(':
        return load_lparen(s)
    elif c == ')':
        raise SyntaxError, 'Unmatched right-paren at %s' % s.read(20)
    elif c == '"':
        return load_string(s)
    elif c == "'":
        return load_char(s)
    elif c.isdigit():
        return load_number(s)
    elif c == '-' and s.peek(2)[1].isdigit():
        return load_number(s)
    else:
        return load_symbol(s)

def load_lparen(s):
    s.read(1)  # throw (
    s.strip()
    expr = []

    c = s.peek(1)
    while not s.eof() and c != ')':
        expr.append(_loads(s))
        s.strip()
        c = s.peek(1)
    s.read(1)  # throw ')'
    return expr

def load_number(s):
    s.strip()
    num = []
    c = s.read(1)
    if c == '-':
        num.append(c)
        c = s.read(1)
    while c.isdigit():
        num.append(c)
        c = s.read(1)
    s.putback(c)
    return int(''.join(num))

def load_string(s):
    s.read(1)  # throw ""
    strr = []
    strr.append('"')
    c = s.read(1)
    while c != '"' and not s.eof():
        strr.append(c)
        c = s.read(1)
    strr.append('"')
    return ''.join(strr)

def load_char(s):
    s.read(1)  # throw '''
    c = s.read(1)
    if c == '\\':
        c += s.read(1)
        if c == '\\n':
            c = '\n'
        elif c == '\\\'':
            c = '\''
        else:
            c = c[1]
    s.read(1)  # throw '''
    return "'%s'" % c

def load_symbol(s):
    s.strip()
    sym = []
    c = s.read(1)
    while c not in (' ', '\n', ')'):
        sym.append(c)
        c = s.read(1)
        if c == ':' and s.peek(1) == ' ':
            print 'WARNING: trailing space after comma -- is it what you want?'
            print '         @ %s' % s.peek(20)
        elif c == ' ' and s.peek(1) == ':':
            print 'WARNING: trailing comma after space -- is it what you want?'
            print '         @ %s' % s.peek(20)
    s.putback(c)
    return ''.join(sym)

class XStr(object):
    def __init__(self, s):
        self.s = s
        self.begin = 0
        self.end = len(s)

    def strip(self):
        while self.begin < self.end and self.s[self.begin] in (' ', '\n'):
            self.begin += 1
        while self.begin < self.end and self.s[self.end - 1] in (' ', '\n'):
            self.end -= 1

    def read(self, howmany):
        to_ret = self.peek(howmany)
        self.begin += howmany
        return to_ret

    def peek(self, howmany):
        return self.s[self.begin:self.begin + howmany]

    def putback(self, s):
        self.begin -= len(s)

    def eof(self):
        return self.begin >= self.end

if __name__ == '__main__':
    test()

