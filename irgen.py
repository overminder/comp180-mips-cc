#!/usr/bin/env python

"""iter through the code, do type checks, allocate space for global vars, and
generate tacs. Call tac.optim to optimize the tac for several passes"""

import os
import sys
import copy
import datetime
# my libs
import util
import reader
import obtype
from err import CompileTimeError
from tac import tac, separ, tograph, optim, optim_detail

NewVar = util.make_counter('t')
NewLabel = util.make_counter('L')
NewStaticVar = util.make_counter('static')  # Hmmmm....

class Env(object):
    """nested namespace environment, but shares the same keyword set.
    How to adapt this to tac generator?"""
    kw = {}
    libs = {}
    tacs = []
    err_occured = []
    while_stack = []  # contains tuple of (start-label, end-label)
    static_vars = {}  # including strliteral and global vars. tokens
    def __init__(self, parent=None):
        self.parent = parent  # parent env
        if parent:
            self.parent.children.append(self)
        self.children = []
        self.ns = {}  # local namespace

    def iteritems(self):
        for child in self.children:
            for item in child.iteritems():
                yield item
        for item in self.ns.iteritems():
            yield item

    def emit(self, c):
        assert isinstance(c, tac.Tac), 'must only emit tac!'
        self.tacs.append(c)

    def feed_code(self, code):
        self.code = code  # to be used in exec_all

    def exec_block(self, blocks):
        """exec the block and converge the results"""
        last_block = None
        for block in blocks:
            got = self.eval_(block)
            last_block = got

        if not last_block:
            return obtype.Token('void')  # without any return
        else:
            return last_block

    def exec_all(self, fname=None, ext_code=None):
        """to ease debug..."""
        self.curr_fname = fname
        if ext_code is None:
            code_to_run = self.code
        else:
            code_to_run = ext_code

        for block_no, code in enumerate(code_to_run, 1):
            # first pass -- check for global vars and functions
            self.curr_block_no = block_no
            self.curr_code = code
            try:
                self.memorize_globals(code)
            except CompileTimeError, e:
                print e
                self.print_block()
                self.err_occured.append(e)

        for block_no, code in enumerate(code_to_run, 1):
            # second pass -- check for internal structures
            self.curr_block_no = block_no
            self.curr_code = code
            try:
                self.eval_(code)
            except CompileTimeError, e:
                print '  ERROR:', e
                self.print_block()
                self.err_occured.append(e)


    def print_block(self):
        if 'curr_code' not in  self.__dict__:
            self.parent.print_block()
        else:
            print '         File: %r' % self.curr_fname
            print '         Current block: %d --' % self.curr_block_no,
            print self.curr_evaling

    def newitem(self, item):
        if not isinstance(item, obtype.Token):
            raise CompileTimeError, 'not a token: %r' % item
        if not item.symbolp():
            raise CompileTimeError, 'variable decl must have a symbol: %r' % item
        if not item.vt:
            raise CompileTimeError, 'variable decl must have type: %r' % item
        if self.contains(item) and self.lookup(item).v is not None:
            raise CompileTimeError, 'redeclaration of symbol: %r' % item

        if not item.tacn:
            item.tacn = NewVar()  # attach a variable name to it
        self.ns[item.n] = item  # name: (Symbol, VarType)

    def contains(self, item):
        return item.n in self.ns

    def lookup(self, item):
        if not item.symbolp():
            raise CompileTimeError, 'Not a symbol: %r' % item
        if not self.contains(item):
            if self.parent:
                return self.parent.lookup(item)
            else:
                raise CompileTimeError, 'lookup -- unbound symbol: %r' % item
        else:
            return self.ns[item.n]

    def setitem(self, key, value):
        if not key.symbolp():
            raise CompileTimeError, '%r is not a symbol' % key

        var = self.lookup(key)
        if not value.can_cast_to(var):  # type check: this might be good
            print 'WARNING: casting from %r to %r' % (value, var)
            self.print_block()
        var.v = value.v  # asm
        var.p = value.p  # for easy func call check
        self.emit(tac.assign(var.tacn, value.tacn))  # var := value

    def eval_(self, expr):
        self.curr_evaling = expr
        if isinstance(expr, list):
            car = expr[0]
            #self.curr_evaling = expr[:2]  # to show more info
            cdr = expr[1:]
            if not isinstance(car, obtype.Token):  # error handling
                raise CompileTimeError, 'not a callable: %r' % car
            if car.symbolp():  # look parent and find that
                f = self.lookup(car)
                if 'macro' in f.__dict__:
                    return self.eval_macro(f, cdr)
                else:
                    return self.eval_func(f, cdr)

            elif car.keywordp():  # look keyword
                try:  # user-defined symbol can shadow the builtin funcs
                    f = self.lookup(car)
                    return self.eval_func(f, cdr)
                except:
                    f = self.kw[car.n]
                    return f(self, cdr)
            elif car.typep():  # type conv
                if len(cdr) != 1:
                    raise CompileTimeError, \
                        'type conversion -- too many args: %r' % cdr
                # temporary type conv. must not change the original's type
                # XXX: is it correct?
                to_ret = copy.copy(self.eval_(cdr[0]))
                to_ret.vt = car.vt
                return to_ret
            else:
                raise CompileTimeError, 'eval -- Wrong type to apply: %r' % car
        elif expr.symbolp():
            return self.lookup(expr)  # may lookup parent
        elif expr.immp():
            # attach imm to a var name
            if expr.tacn is None:
                expr.tacn = NewVar()
                self.emit(tac.assign(expr.tacn, expr.v))
            return expr
        else:
            raise CompileTimeError, 'eval -- Unknown type: %r' % expr

    def eval_macro(self, f, args):
        if len(f.p) != len(args):  # not an error here.
            print 'Warning: macro %r required %d args, but '\
                    'only %d are given' % (f, len(f.p), len(args))
        to_pushs = []
        for i, arg in enumerate(args):
            arg = self.eval_(arg)
            to_pushs.append(arg.tacn)
        for to_push in reversed(to_pushs):  # reversely push those vars
            self.emit(tac.push_arg(to_push))
        # emit actual call and fetch ret for now
        ret_value = obtype.Token(f.vt)
        ret_value.vt = 'omni'  # can be casted to anything
        ret_value.tacn = NewVar()
        self.emit(tac.call(ret_value.tacn, f.n))  # func call
        return ret_value

    def eval_func(self, f, args):
        if f.p is None:
            raise CompileTimeError, 'Not a callable -- %r' % f
        if len(f.p) != len(args):
            raise CompileTimeError, 'function %r required %d args, but '\
                    'only %d are given' % (f, len(f.p), len(args))

        # func args preparation
        to_pushs = []
        for i, arg in enumerate(args):
            arg = self.eval_(arg)
            if not arg.can_cast_to(f.p[i]):
                print 'WARNING: casting argument '\
                        '%r to %r at func %r' % (arg, f.p[i], f)
                self.print_block()
            to_pushs.append(arg.tacn)

        for to_push in reversed(to_pushs):  # reversely push those vars
            self.emit(tac.push_arg(to_push))

        # emit actual call and fetch ret for now
        ret_value = obtype.Token(f.vt)
        ret_value.tacn = NewVar()
        self.emit(tac.call(ret_value.tacn, f.n))  # func call
        return ret_value

    def memorize_globals(self, code):
        """currently only defvar, defun are supported in global
        scope. require is placed outside..."""
        self.curr_evaling = code
        if isinstance(code, list):
            car = code[0]
            if isinstance(car, list):
                raise CompileTimeError, 'nested parenthesis on static'\
                                        'declaration -- %r' % car

            if car.n == 'defvar':
                cdr = code[1]
                cdr.tacn = NewStaticVar()
                self.static_vars[cdr.tacn] = cdr
                self.newitem(cdr)  # new item with name and type
            elif car.n == 'defun':
                fdecl = code[1][0]
                fparam = code[2]
                func_t = copy.deepcopy(fdecl)
                func_t.p = fparam
                self.newitem(func_t)
            elif car.n == 'defmacro':
                fdecl = code[1][0]
                fparam = code[2]
                func_t = copy.deepcopy(fdecl)
                func_t.p = fparam
                func_t.macro = True
                self.newitem(func_t)

def keyword(name=None):
    """decorator for register at keyword-namespace"""
    def wrap(func):
        if not name:
            fname = func.__name__
        else:
            fname = name
        if isinstance(fname, list):
            for each_fname in fname:
                Env.kw[each_fname] = func
        else:
            Env.kw[fname] = func
        return func
    return wrap

def require_arglen(n):
    """decorator for requiring how many args"""
    def wrap(func):
        name = func.__name__
        def call(env, args):
            if isinstance(n, int):
                if len(args) != n:
                    print 'WARNING: Procedure %s takes exactly %d arguments '\
                          '(%d given)' % (name, n, len(args))
                    env.print_block()
            elif isinstance(n, list):
                if len(args) not in n:
                    print 'WARNING: Procedure %s takes %d to %d arguments '\
                          '(%d given)' % (name, n[0], n[-1], len(args))
                    env.print_block()
            return func(env, args)
        call.__name__ = name
        return call
    return wrap

@keyword('defvar')
@require_arglen([1, 2])
def _defvar(env, args):
    first = args[0]
    env.newitem(first)  # new item with name and type
    if len(args) == 2:
        second = args[1]
        result = env.eval_(second)  # code gen
        env.setitem(first, result)  # set the value
    return obtype.Token('void')

@keyword(['/', '>', '<', '>=' ,'<=', 'eq?', '!=', '<<', '>>', 'and', 'or', '%'])
@require_arglen(2)
def _num_binop(env, args):
    op = env.curr_evaling[0]  # XXX: to know the op

    first, second = args
    first = env.eval_(first)
    second = env.eval_(second)
    if not (first.can_cast_to_type('int') and second.can_cast_to_type('int'))\
        and not (first.vt == second.vt):  # same type is also ok
        print 'WARNING: op %s, argument must be number -- %r %r' % (
                op, first, second)
        env.print_block()

    retval = obtype.Token('int')
    retval.tacn = NewVar()  # give a name and do tac binary op
    env.emit(tac.binary(retval.tacn, first.tacn, op.n, second.tacn))
    return retval

@keyword(['-', '+'])
def _num_minus(env, args):
    op = env.curr_evaling[0]  # XXX: to know the op
    retval = obtype.Token('int')
    retval.tacn = NewVar()
    env.emit(tac.assign(retval.tacn, 0))

    sll = 0
    if len(args) != 0:
        arg = args[0]
        arg = env.eval_(arg)
        if not arg.can_cast_to_type('int'):
            sll = obtype.sizeof_byshift(arg.vt)
            retval.vt = arg.vt
        env.emit(tac.assign(retval.tacn, arg.tacn))

    for arg in args[1:]:
        arg = env.eval_(arg)
        if not arg.can_cast_to_type('int'):
            print 'WARNING: op %r -- argument must be number -- %r' % (
                    op, arg)
            env.print_block()
        if sll != 0:
            tmp = NewVar()
            env.emit(tac.binary(tmp, arg.tacn, '<<', sll))
        else:
            tmp = arg.tacn
        env.emit(tac.binary(retval.tacn, retval.tacn, op.n, tmp))
    return retval


@keyword('*')
def _num_sumall(env, args):
    retval = obtype.Token('int')
    retval.tacn = NewVar()
    env.emit(tac.assign(retval.tacn, 1))
    for arg in args:
        arg = env.eval_(arg)
        if not arg.can_cast_to_type('int'):
            print 'WARNING: op *, argument must be number at * -- %r' % arg
            env.print_block()
        env.emit(tac.binary(retval.tacn, retval.tacn, '*', arg.tacn))
    return retval


@keyword('let')
def _let(env, args):
    ex_env = Env(env)
    assigns = args[0]
    execs = args[1:]
    for assign in assigns:
        if len(assign) == 2:
            ex_env.eval_([obtype.Token('defvar'), assign[0], assign[1]])
        elif len(assign) == 1:
            ex_env.eval_([obtype.Token('defvar'), assign[0]])
        else:
            raise CompileTimeError, 'let -- Missing blocks %r' % assign

    return ex_env.exec_block(execs)

@keyword('break')
@require_arglen(0)
def _break(env, args):
    if not env.while_stack:
        raise CompileTimeError, 'break -- not in a block'
    env.emit(tac.branch(env.while_stack[-1][1]))
    return obtype.Token('void')

@keyword('continue')
@require_arglen(0)
def _break(env, args):
    if not env.while_stack:
        raise CompileTimeError, 'continue -- not in a block'
    env.emit(tac.branch(env.while_stack[-1][0]))
    return obtype.Token('void')

@keyword('while')
def _while(env, args):
    if len(args) < 2:
        raise CompileTimeError, 'while -- Missing blocks %r' % args
    pred = args[0]
    codes = args[1:]

    # create some labels
    loop_start_label = NewLabel('loop_start')
    loop_next_label = NewLabel('loop_next')
    loop_end_label = NewLabel('loop_end')
    env.while_stack.append((loop_start_label, loop_end_label))

    env.emit(tac.label(loop_start_label))
    # emit code for looping
    tmp_pred = env.eval_(pred)
    if not tmp_pred.can_cast_to_type('int'):
        print 'WARNING: while -- casting %r to boolean type' % tmp_pred
        env.print_block()

    # loop labels
    env.emit(tac.cbranch(tmp_pred.tacn, loop_next_label))
    env.emit(tac.branch(loop_end_label))
    env.emit(tac.label(loop_next_label))

    ret_val = env.exec_block(codes)  # XXX: the block need to know how to jump
                                     # out of this loop! hmm... a stack?
    env.emit(tac.branch(loop_start_label))
    env.emit(tac.label(loop_end_label))
    env.while_stack.pop()  # remove while stack
    # while should not have a return value... things should be changed
    # by side effects. this is what loops are intended to do
    return obtype.Token('void')

@keyword('cond')
def _cond(env, args):
    to_ret = []

    # tac preparations
    pred_labels = [NewLabel('case') for i in xrange(len(args))]
    block_labels = [NewLabel('iftrue') for i in xrange(len(args))]
    else_label = NewLabel('else')
    final_label = NewLabel('final')
    final_result = NewVar()

    # for each predicate and code block:
    for i, pred_todo in enumerate(args):
        if len(pred_todo) == 1:  # no todo?
            raise CompileTimeError, 'cond -- Missing code block '\
                    'after predicate %r' % (pred_todo)
        pred = pred_todo[0]
        codes = pred_todo[1:]

        # XXX: here i dont check whether the else is placed at the last
        if isinstance(pred, obtype.Token) and pred.symbolp() \
                and pred.n == 'else':  # is else
            env.emit(tac.label(else_label))
            ret_val = env.exec_block(codes)
            env.emit(tac.assign(final_result, ret_val.tacn))

        else:  # is predcate
            if i != 0:
                env.emit(tac.label(pred_labels[i]))  # at case i

            pred = env.eval_(pred)  # eval and emit code block
            if not pred.can_cast_to_type('int'):
                print 'WARNING: cond -- casting %r to boolean type' % pred
                env.print_block()

            env.emit(tac.cbranch(pred.tacn, block_labels[i]))  # if true
            if i == len(args) - 1:
                # is the last case. XXX: somehow dirty..
                env.emit(tac.branch(final_label))
            elif isinstance(args[i + 1][0], obtype.Token) and \
                    args[i + 1][0].n == 'else':
                env.emit(tac.branch(else_label))
            else:  # still have more cases to check
                env.emit(tac.branch(pred_labels[i + 1]))

            env.emit(tac.label(block_labels[i]))  # exec block
            ret_val = env.exec_block(codes)
            env.emit(tac.assign(final_result, ret_val.tacn))
            env.emit(tac.branch(final_label))

        to_ret.append(ret_val)

    # cond over, the final label
    env.emit(tac.label(final_label))

    if not to_ret:
        return obtype.Token('void')
    else:
        first = to_ret[0]
        first.tacn = final_result  # it's created on the fly so dont worry 
                                   # about the side effect ^ ^
        for item in to_ret:
            if not first.can_cast_to(item):
                print 'WARNING: cond -- returning different types: %r %r' % (
                        first, item)
                env.print_block()
        return first

@keyword('defmacro')
def _defmacro(env, args):
    """no type checking"""
    mac_name = env.curr_evaling[1][0].n  # get the macro name
    env = Env(env)
    env.emit(tac.mac_begin('%s' % mac_name))
    env.emit(tac.label(util.mangle(mac_name)))  # entrance
    fbody = args[2:]
    for mac in fbody:
        if mac[0].n != 'asm':
            raise CompileTimeError, 'defmacro -- body must be all asm'
    ret_val = env.exec_block(fbody)  # must return one val
    ret_val.vt = 'omni'  # can be cast to any type
    env.emit(tac.mac_end('%s' % mac_name))
    return ret_val


@keyword('defun')
def _defun(env, args):
    """assume that global functions are already globally visiable"""
    fun_name = env.curr_evaling[1][0].n  # get the function name
    ex_env = Env(env)  # extend the env using a new block

    env.emit(tac.func_begin('%s' % fun_name))
    #env.emit(tac.label(util.mangle(fun_name)))

    fdecl = args[0][0]
    argdecls = args[1]
    fbody = args[2:]

    for argdecl in argdecls:
        argdecl.tacn = NewVar()
        ex_env.emit(tac.pop_arg(argdecl.tacn))

    if not fdecl.symbolp() or not fdecl.vtypep():
        raise CompileTimeError('function decl must contain a return type: %r'\
                % fdecl)

    for argdecl in argdecls:
        ex_env.eval_([obtype.Token('defvar'), argdecl])

    ret_val = ex_env.exec_block(fbody)  # must return one val
    if not ret_val.can_cast_to(fdecl):
        print 'WARNING: defun -- casting %r to %r' % (ret_val, fdecl)
        env.print_block()

    env.emit(tac.ret(ret_val.tacn))  # return from function
    env.emit(tac.func_end('%s' % fun_name))
    return obtype.Token('void')

@keyword('print')
def _print(env, args):
    for arg in args:
        arg = env.eval_(arg)
        if arg.vt == 'byte*':
            env.emit(tac.syscall('print_str', arg.tacn))
        elif arg.vt == 'int':
            env.emit(tac.syscall('print_int', arg.tacn))
        elif arg.vt == 'byte':
            env.emit(tac.syscall('print_byte', arg.tacn))
        else:
            raise CompileTimeError, 'print -- dont know how to print '\
                    'type %r' % arg

    return obtype.Token('void')

@keyword('set!')
@require_arglen(2)
def _setbang(env, args):
    first, second = args
    first = env.lookup(first)
    second = env.eval_(second)
    env.setitem(first, second)
    return obtype.Token('void')

@keyword('not')
@require_arglen(1)
def _not(env, args):
    arg = args[0]
    arg = env.eval_(arg)
    if not arg.can_cast_to_type('int'):
        print 'WARNING: not -- casting %r to int' % arg
        env.print_block()
    retval = obtype.Token('int')
    retval.tacn = NewVar()
    env.emit(tac.unary(retval.tacn, 'not', arg.tacn))
    return retval

@keyword('ref')
@require_arglen(1)
def _ref(env, args):
    arg = args[0]
    if not isinstance(arg, obtype.Token) or not arg.symbolp():
        raise CompileTimeError, 'cannot dereference %r' % arg
    arg = env.lookup(arg).lvalue()
    return obtype.Token(arg.vt + '*')

@keyword('nth')
@require_arglen(2)
def _nth(env, args):
    sym, idx = args
    sym = env.eval_(sym)
    idx = env.eval_(idx)
    if not sym.ptrp():
        print 'WARNING: dereferencing a non-pointer %r' % sym
        env.print_block()
    # bound checking?
    if not idx.can_cast_to_type('int'):
        print 'WARNING: array index is not an integer %r' % idx
        env.print_block()
    retval = obtype.Token(sym.vt[:-1])  # dereferencing
    retval.tacn = NewVar()

    # sizeof retval, to facilitate idx
    memsize = obtype.sizeof_byshift(retval.vt)
    tmpoffset = NewVar()
    env.emit(tac.binary(tmpoffset, idx.tacn, '<<', memsize))
    env.emit(tac.binary(tmpoffset, tmpoffset, '+', sym.tacn))
    env.emit(tac.load(retval.tacn, tmpoffset, 0))
    return retval

@keyword('set-nth!')
@require_arglen(3)
def _set_nthbang(env, args):
    sym, idx, val = map(env.eval_, args)
    if not sym.ptrp():
        print 'WARNING: dereferencing a non-pointer %r' % sym
        env.print_block()
    if not idx.can_cast_to_type('int'):
        print 'WARNING: array index is not an integer %r' % idx
        env.print_block()
    if not sym.vt[:-1] == val.vt:
        print 'WARNING: casting %r to %r at set-nth!' % (val.vt, sym.vt[:-1])
        env.print_block()

    memsize = obtype.sizeof_byshift(sym.vt[:-1])
    if memsize != 0:  # not zero: need to change
        tmpoffset = NewVar()
        env.emit(tac.binary(tmpoffset, idx.tacn, '<<', memsize))
        env.emit(tac.binary(tmpoffset, tmpoffset, '+', sym.tacn))
        env.emit(tac.store(tmpoffset, 0, val.tacn))  # *(p+c) = val
    else:  # zero: just do it
        env.emit(tac.store(sym.tacn, 0, val.tacn))

    return obtype.Token('void')

@keyword('asm')
def _asm(env, args):
    for arg in args:
        if not isinstance(arg, obtype.Token) or not arg.immp() or \
                not arg.vt == "byte*":
            raise CompileTimeError, 'asm -- argument must be string: %r' % arg
        env.emit(tac.comment('__ASM__ %s' % arg.n))
    return obtype.Token('void')

@keyword('require')
def _require(env, args):
    """(require stdio
                stdlib)"""
    for arg in args:
        if not isinstance(arg, obtype.Token) or not arg.symbolp():
            raise CompileTimeError, \
                    'require -- argument must be symbol: %r' % arg
        # exec the file in the environment
        symb = arg.n
        fname = symb + '.lisp'
        fpath_b = os.path.join(util.LIB_DIR, fname)
        if os.path.isfile(fpath_b):
            # the file is a builtin lib file: run in the env
            fpath = fpath_b
        else:
            fpath_l = os.path.join(util.PWD_DIR, fname)
            if not os.path.isfile(fpath_l):
                raise CompileTimeError, \
                        'require -- cannot find file %r\nsearch path are: %r' \
                        % (fname, [fpath_b, fpath_l])
            else:
                # the file is a local lib file: run in the env
                fpath = fpath_l

        if fpath in env.libs:
            continue  # already included
        else:
            env.libs[fpath] = 1
            with open(fpath) as fp:
                lib_code = reader.load(fp)
            obtype.tokenize(lib_code)
            old_fname = env.curr_fname
            env.exec_all(fname, lib_code)
            env.curr_fname = old_fname

    return obtype.Token('void')

# generate functionized tacs from file
def from_file(fname):
    with open(fname) as f:
        code_data = reader.load(f)
    obtype.tokenize(code_data)

    tac_env = Env()
    tac_env.feed_code(code_data)
    tac_env.exec_all(fname)

    if tac_env.err_occured:
        print tac_env.err_occured
        return None
    else:
        return separ.to_func(tac_env.tacs)

def main():
    if len(sys.argv) == 1:
        print 'Usage: %s [file name]' % sys.argv[0]
        return

    fname = sys.argv[1]
    funcs = from_file(fname)
    if not funcs:
        print
        print '** IRgen failed to give TAC, abort **'
        return

    want_to_see = []
    if not want_to_see:  # see all
        for fname, fcode in funcs.iteritems():
            tograph.find_leaders(fcode)  # important
            optim.run_all(fcode)
            tac.pprint(fcode)
    else:
        for fname in want_to_see:
            fcode = funcs[fname]
            tograph.find_leaders(fcode)
            optim.run_all(fcode)
            tac.pprint(fcode)


if __name__ == '__main__':
    main()

