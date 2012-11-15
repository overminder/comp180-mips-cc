import re
import os

def make_counter(prefix='t', start=0):
    start = [start]  # to be mutable
    def call(more_info=''):
        to_ret = '%s%d%s' % (prefix, start[0], more_info)
        start[0] += 1
        return to_ret
    return call

static_counter = make_counter('str_')

mangle_dict = {
    '+': '__plus',
    '-': '__dash',
    '*': '__star',
    '/': '__slsh',
    '!': '__bang',
    '?': '__qmrk',
    '=': '__equl',
    '<': '__less',
    '>': '__grat',
}

demangle_dict = dict((v, k) for (k, v) in mangle_dict.iteritems())

def translate(s, d):
    for k, v in d.iteritems():
        s = s.replace(k, v)
    return s

def mangle(name):
    return '_' + translate(name, mangle_dict)

def demangle(name):
    return translate(name[1:], demangle_dict)

def shut_output():
    sys.stderr = sys.stdout = open('/dev/null', 'w')

def print_env(e):
    to_print = []
    for name, item in e.iteritems():
        if item.p:  # is func
            mitem = mangle(item.n)
            assert demangle(mitem) == item.n and \
                    re.match(r'([a-zA-Z0-9_]+)', mitem).group(1) == mitem, \
                    'corrupted mangle table -- %r => %r' % (item.n, mitem)
        else:
            mitem = item.n
        to_print.append((name, mitem))
    maxlen = len(max(to_print, key=lambda t: len(t[0]))[0])
    for k, v in to_print:
        print '%s %s' % (k.ljust(maxlen), v)

LIB_DIR = '/home/overmind/src/py/mips_compiler/interp/lib'
PWD_DIR = os.getcwd()

