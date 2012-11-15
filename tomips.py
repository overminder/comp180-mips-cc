#!/usr/bin/env python

import datetime
from cStringIO import StringIO
# my libs
import sys
import util
import irgen
from tac import tac, optim, tograph, old_optim
from err import MipsGenError

class RegPool(object):
    def __init__(self):
        self.free = ['$t%d' % i for i in xrange(10)] + [
                            '$s%d' % i for i in xrange(8)]

    def alloc(self):
        return self.free.pop()

    def dealloc(self, t):
        self.free.append(t)

class Translator(object):
    handlers = {}
    last_call = None
    def __init__(self, codes):
        self.pool = RegPool()
        self.codes = codes
        self.out = []
        self.reg_ns = {}
        self.used_regs = ['$ra']  # to be seen at the end...
        self.has_called_f = False  # then dont save ra
        self.arg_to_push = []
        self.arg_used = []
        self.static_vars = {}

    def __getitem__(self, k):
        if immp(k):
            return k
        if staticp(k):
            if k not in self.static_vars:
                self.static_vars[k] = util.static_counter()
            return self.static_vars[k]
        if k not in self.reg_ns:
            try:
                self.reg_ns[k] = self.pool.alloc()
            except:
                print '#' * 50
                print ' ' * 50
                print 'out of register at %r' % self.funcname
                print ' ' * 50
                print '#' * 50
                self.pool.free.extend(['$X%d' % i for i in xrange(100)])
                self.reg_ns[k] = self.pool.alloc()
            self.used_regs.append(self.reg_ns[k])
        return self.reg_ns[k]

    def emit(self, *argl):
        if not argl:
            self.out.append('')
        elif len(argl) == 1 and argl[0].endswith(':'):
            self.out.append(argl[0])  # label
        else:
            fmt = ' ' * 8 + argl[0].ljust(5) + ', '.join(
                    map(lambda s: str(s).rjust(8), argl[1:]))
            self.out.append(fmt)

    def trans_all(self):
        for c in self.codes:
            self.handlers[c.code_t](self, c)

        if not hasattr(self, 'funcname') or not self.funcname:
            return  # a macro

        # handle the function start
        out = self.out
        self.out = []

        self.emit('# function %s begins' % self.funcname)
        if self.funcname != 'main':
            self.emit('%s:' % util.mangle(self.funcname))
        else:  # is main, dont mangle
            self.emit('main:')
        self.emit('# prologue')

        if self.used_regs:  # only save reg if required
            self.emit('addi', '$sp', '$sp', len(self.used_regs) * -4)
            for i, used_reg in enumerate(self.used_regs):
                self.emit('sw', used_reg, '%d($sp)' % (
                    (i - len(self.used_regs) + 1) * -4))

        # and the pop of the vars
        for i, arg in enumerate(reversed(self.arg_used)):
            self.emit('addi', self[arg.x], '$a%d' % i, 0)
        self.out.extend(out)

def handles(c):
    def wrap(func):
        def call(*argl, **argd):
            vm = argl[0]
            vm.last_call = argl[1]  # last tac
            return func(*argl, **argd)
        Translator.handlers[c] = call
        return call
    return wrap

def immp(s):
    return isinstance(s, int)

def staticp(s):
    return isinstance(s, str) and s.startswith('"')


@handles(tac.ASSIGN)
def _assign(vm, code):
    if immp(code.y):
        if code.y > 2 ** 15:
            vm.emit('lui', vm[code.x], code.y >> 16)
            vm.emit('ori', vm[code.x], code.y & (2 ** 16 - 1))
        else:
            vm.emit('addi', vm[code.x], '$zero', code.y)
    elif staticp(code.y):
        vm.emit('la', vm[code.x], vm[code.y])
    else:
        vm.emit('addi', vm[code.x], vm[code.y], 0)

@handles(tac.UNARY)
def _unary(vm, code):
    if code.op == 'not':
        vm.emit('slti', vm[code.x], vm[code.y], 1)

    raise MipsGenError, 'undefined unary-op: %r' % code

@handles(tac.BINARY)
def _binary(vm, code):
    if code.op == '+':
        if immp(code.z):
            vm.emit('addi', vm[code.x], vm[code.y], code.z)
        else:
            vm.emit('add', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '-':
        if code.y == 0:
            vm.emit('sub', vm[code.x], '$zero', vm[code.z])
        elif immp(code.y):
            vm.emit('sub', vm[code.x], '$zero', vm[code.z])
            vm.emit('addi', vm[code.x], vm[code.x], code.y)
        else:  # all are reg
            vm.emit('sub', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '*':
        if immp(code.z):
            vm.emit('addi', vm[code.x], '$zero', code.z)
            vm.emit('mul', vm[code.x], vm[code.x], vm[code.y])
        else:
            vm.emit('mul', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '/':
        vm.emit('div', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '%':
        vm.emit('rem', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '<':
        if immp(code.z):
            vm.emit('slti', vm[code.x], vm[code.y], code.z)
        elif immp(code.y):  # imm < reg
            vm.emit('addi', '$a0', '$zero', code.y)
            vm.emit('slt', vm[code.x], '$a0', vm[code.z])
        else:
            vm.emit('slt', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == '<<':
        if immp(code.z):
            vm.emit('sll', vm[code.x], vm[code.y], code.z)
        else:
            vm.emit('sllv', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == 'or':
        vm.emit('or', vm[code.x], vm[code.y], vm[code.z])
        return

    if code.op == 'and':
        vm.emit('and', vm[code.x], vm[code.y], vm[code.z])
        return

    raise MipsGenError, 'undefined binary-op: %r' % code.op

@handles(tac.ADDROF)
def _addrof(vm, code):
    vm.emit('# addrof code? %r' % code)

@handles(tac.LOAD)
def _load(vm, code):
    vm.emit('lw', vm[code.x], '%d(%s)' % (code.c, vm[code.p]))

@handles(tac.STORE)
def _store(vm, code):
    vm.emit('sw', vm[code.y], '%d(%s)' % (code.c, vm[code.p]))

@handles(tac.CALL)
def _call(vm, code):
    vm.has_called_f = True
    for i, arg in enumerate(vm.arg_to_push):
        if immp(arg.y):
            vm.emit('addi', '$a%d' % i, '$zero', vm[arg.y])
        else:
            vm.emit('addi', '$a%d' % i, vm[arg.y], 0)
    vm.arg_to_push[:] = []
    vm.emit('jal', util.mangle(code.f))
    if code.x is not None:  # else: dont return
        vm.emit('addi', vm[code.x], '$v0', 0)

@handles(tac.BRANCH)
def _branch(vm, code):
    vm.emit('j', code.L)

@handles(tac.CBRANCH)
def _cbranch(vm, code):
    vm.emit('bne', vm[code.y], '$zero', code.L)

@handles(tac.LABEL)
def _lbl(vm, code):
    vm.emit('%s:' % code.L)

@handles(tac.RET)
def _return(vm, code):
    if not vm.has_called_f:
        vm.used_regs.remove('$ra')
    vm.emit('# epilogue')
    if code.y is not None:  # dont return if ret is none
        if immp(code.y):
            vm.emit('addi', '$v0', '$zero', vm[code.y])
        else:
            vm.emit('addi', '$v0', vm[code.y], 0)
    if vm.used_regs:
        for i, used_reg in enumerate(vm.used_regs):
            vm.emit('lw', used_reg, '%d($sp)' % (
                (len(vm.used_regs) - i - 1) * 4))
        vm.emit('addi', '$sp', '$sp', len(vm.used_regs) * 4)
    vm.emit('jr', '$ra')

@handles(tac.COMMENT)
def _comment(vm, code):
    if code.x.startswith('__ASM__'):  # is asm
        vm.emit(code.x[8:][1:-1])
    else:
        vm.emit('# %s' % code.x)

@handles(tac.PUSH_ARG)
def _push_arg(vm, code):
    vm.arg_to_push.append(code)

@handles(tac.POP_ARG)
def _pop_arg(vm, code):
    vm.arg_used.append(code)

@handles(tac.SYSCALL)
def _syscall(vm, code):
    if code.f == 'print_int':
        vm.emit('li', '$v0', 1)
        if immp(code.y):
            vm.emit('addi', '$a0', '$zero', vm[code.y])
        else:
            vm.emit('addi', '$a0', vm[code.y], 0)
    elif code.f == 'print_byte':
        vm.emit('li', '$v0', 11)
        if immp(code.y):
            vm.emit('addi', '$a0', '$zero', vm[code.y])
        else:
            vm.emit('addi', '$a0', vm[code.y], 0)
    elif code.f == 'print_str':
        vm.emit('li', '$v0', 4)
        if staticp(code.y):
            vm.emit('la', '$a0', vm[code.y])
        else:
            vm.emit('addi', '$a0', vm[code.y], 0)
    vm.emit('syscall')

@handles(tac.FUNC_BEGIN)
def _func_begin(vm, code):
    vm.funcname = code.x

@handles(tac.FUNC_END)
def _func_end(vm, code):
    vm.emit('# function %s ends' % code.x)

@handles(tac.MAC_BEGIN)
def _mac_begin(vm, code):
    vm.used_regs = []
    vm.funcname = None

@handles(tac.MAC_END)
def _mac_end(vm, code):
    pass

# main routine
def main():
    if len(sys.argv) == 1:
        print 'Usage: %s [file name]' % sys.argv[0]
        return

    fname = sys.argv[1]
    if fname.split('.')[0] + '.s' == fname:
        print 'cannot output to the same file'
        return

    with open(fname.split('.')[0] + '.s', 'w') as f:
        f.write('# %s\n' % datetime.datetime.now())

    fhead = StringIO()
    fbody = StringIO()

    funcs = irgen.from_file(fname)
    if not funcs:
        print
        print '** compilation failed due to irgen not generating any TAC **'
        return
    old_optim.eliminate_unused_func(funcs)

    for func in funcs.values():
        tograph.find_leaders(func)
        optim.run_all(func)
        #tac.pprint(func)
        mipstrans = Translator(func)
        mipstrans.trans_all()
        for var_name, var in mipstrans.static_vars.iteritems():
            fhead.write('%s: .asciiz %s\n' % (var, var_name))
        map(lambda s: fbody.write('%s\n' % s), mipstrans.out)

    with open(fname.split('.')[0] + '.s', 'a') as f:
        f.write('.data\n')
        f.write('randseed: .word 12345\n')
        f.write(fhead.getvalue())
        f.write('.text\n')
        f.write(fbody.getvalue())


