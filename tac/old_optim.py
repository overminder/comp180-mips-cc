"""algorithm for tac optimization!!!
This is spartaaaaaa!

intended output: faster asm gen
                 easiler asm gen
                 fewer operators
                 fewer regs

05/05/11:
    Refactor all functions after reading sufficient paper.
    MUST!

"""

import util
import tac
from err import CompileTimeError
N_PASSES = 10

# helper utilities
def make_optim(can, f=None, *argl, **argd):
    return (can, f, argl, argd)

optim_d = []
def reg_optim(func):
    """maybe sorted?"""
    optim_d.append((func.__name__, func))
    return func

# main entrance
def run_all(codes):
# firstly cut the codes into different functions
    funcs = split_to_func(codes)
    to_ret = []
    eliminate_unused_func(funcs)
    for name, func in funcs.iteritems():
        if name == '__others':
            to_ret.extend(func)
            continue
        optim_func_code(func)
        to_ret.extend(func)
    codes[:] = to_ret
    return funcs

def split_to_func(codes):
    splits = {}
    others = []
    i = 0
    while i < len(codes):
        c = codes[i]
        if c.code_t == tac.FUNC_BEGIN:
            fun_name = c.x
            curr = []
            while c.code_t != tac.FUNC_END:
                curr.append(c)
                i += 1
                c = codes[i]
            curr.append(c)
            splits[fun_name] = curr
        else:
            others.append(c)
        i += 1
    splits['__others'] = others
    return splits

def optim_func_code(func_code):
    for i in xrange(N_PASSES):
        for i, (n, f) in enumerate(optim_d):
            #if i in (2,):  # propagand_ops and reduce_name_trivial
            #    continue

            # 7: reduce name trivial is also unsafe wtf..
            # edit: disabled 7 when there is control flow.
            # heuristic_dec2 and useless_assign are unsafe, disabled
            result = f(func_code)
            if result and result[0]:
                result[1](func_code, result[2], result[3])

# ez...
def eliminate_unused_func(funcs):
    if 'main' not in funcs:
        return  # main undefined, dont eliminate

    usage = {}
    for fname, body in funcs.iteritems():
        usage[fname] = set()
        for c in body:
            if c.code_t == tac.CALL:
                usage[fname].add(c.f)

    # dfs
    def dfs(graph, fname, done):
        done.add(fname)
        if fname not in graph:  # is a macro
            return
        for name in graph[fname]:
            if name in done:
                pass
            else:
                dfs(graph, name, done)

    _done = set()
    dfs(usage, 'main', _done)
    _funcs = dict((fname, funcs[fname]) for fname in _done if fname in funcs)
    _funcs['__others'] = funcs['__others']
    funcs.clear()
    funcs.update(_funcs)

# case 0:  const folding...
@reg_optim
def case0_can(codes):
    opt_idx = []
    for i, c in enumerate(codes):
        if c.immp():  # which can be change to simple assign
            opt_idx.append(i)
    if opt_idx:
        return make_optim(True, case0_run, opt_idx=opt_idx)
    else:
        return make_optim(False)

def case0_run(codes, argl, argd):
    for i in argd['opt_idx']:
        codes[i] = tac.assign(codes[i].x, codes[i].fold())

# case 0.1: move imm to the right
@reg_optim
def move_imm_to_right(codes):
    for i, c in enumerate(codes):
        if c.code_t == tac.BINARY:
            if isinstance(c.y, int) and c.op in ['*', '+']:
                c.y, c.z = c.z, c.y
            elif isinstance(c.z, int) and c.op == '-':
                c.z = -c.z
                c.op = '+'
    return make_optim(False)

# case 0.2: remove meaningless binop and unary op
@reg_optim
def propagand_ops(codes):
    for i, c in enumerate(codes):
        if c.code_t == tac.BINARY and not c.immp('y') and c.immp('z'):
            if c.z == 0 and c.op in ['+', '-']:  # + 0 / - 0: throw
                codes[i] = tac.assign(c.x, c.y)
            elif c.z == 1 and c.op in ['*', '/']:
                codes[i] = tac.assign(c.x, c.y)
            elif c.z == 0 and c.op == '*':
                codes[i] = tac.assign(c.x, 0)
            elif c.z == 0 and c.op == '/':
                raise CompileTimeError, 'divide by zero'
    return make_optim(False)


# when two assigns are away but... Notice that this is not safe because
# of the jumping... or is it safe?
@reg_optim
def useless_assign(codes):
    ret = []
    for i, c in enumerate(codes):
        if c.code_t == tac.ASSIGN:
            if c.x == c.y:  # assign to self, which is safe to eliminate
                ret.append((i, i))
                continue

            # part 2: dup assign
            '''
            old_i = i
            lhs = c.x
            i += 1
            while i < len(codes):
                cc = codes[i]
                if cc.code_t == tac.ASSIGN and cc.x == lhs:  # dup
                    ret.append((old_i, i))
                    break
                elif lhs in cc.varnames():  # modified?
                    break
                i += 1
            '''

    if ret:
        return make_optim(True, run_useless_assign, ret)
    else:
        return make_optim(False)

def run_useless_assign(codes, argl, argd):
    for d, t in argl[0]:
        codes[d] = None
    codes[:] = [c for c in codes if c]

# case 1.5: <Double assign>
# example: ASSIGN t0 := 0
#          ASSIGN t0 := t1
# seems it can be generalized to assign-rewrite
@reg_optim
def double_assign(codes):
    opt_idx = []
    for i, c in enumerate(codes):
        if i == len(codes) - 1:  # last code: abandon
            continue
        next_c = codes[i + 1]
        if c.code_t == tac.ASSIGN and next_c.code_t == tac.ASSIGN:
            if c.x == next_c.x:
                opt_idx.append(i)
    if opt_idx:
        return make_optim(True, double_assign_run, opt_idx=opt_idx)
    else:
        return make_optim(False)

def double_assign_run(codes, argl, argd):
    for i in argd['opt_idx']:
        codes[i] = None
    codes[:] = [c for c in codes if c]

# case 2:  <Dangling pre-assign>
# example: ASSIGN t0 := imm
#          BINARY t2 := t3 + t0
# Which can be changed into:
#          BINARY t2 := t3 + imm
# Note that the binary can also be PUSH, UNARY, RET, SYSCALL or other mutators
# bug: must also consider if others will also use the t0
@reg_optim
def case2_can(codes):
    opt_idx = []
    for i, c in enumerate(codes):
        if i == len(codes) - 1:  # last code: abandon
            continue
        next_c = codes[i + 1]
        if c.code_t == tac.ASSIGN:
            #if next_c.code_t in (tac.PUSH_ARG, tac.UNARY, tac.RET, tac.SYSCALL):
            #    if c.x == next_c.y:  # can optimiz
            #        opt_idx.append(i)
            #if next_c.code_t == tac.BINARY:
            #    if c.x in (next_c.y, next_c.z):  # can optimiz
            #        opt_idx.append(i)
            if next_c.code_t in (tac.LOAD, tac.STORE):
                if c.x == next_c.p:
                    opt_idx.append(i)  # optimiz load
    if opt_idx:
        return make_optim(True, case2_run, opt_idx=opt_idx)
    else:
        return make_optim(False)

def case2_run(codes, argl, argd):
    for i in argd['opt_idx']:
        this_c = codes[i]
        next_c = codes[i + 1]
        if next_c.code_t in (tac.PUSH_ARG, tac.UNARY, tac.RET, tac.SYSCALL):
            next_c.y = this_c.y
        elif next_c.code_t == tac.BINARY:
            if this_c.x == next_c.y:
                next_c.y = this_c.y
            elif this_c.x == next_c.z:
                next_c.z = this_c.y
            else:
                raise CompileTimeError, 'Invalid optimization at optcase 2'
        elif next_c.code_t in (tac.LOAD, tac.STORE):
            next_c.p = this_c.y

        codes[i] = None
    codes[:] = [c for c in codes if c]

# case 3:  <Dangling post-assign>
# example: BINARY t0 := t1 + t2  # this_c
#          ASSIGN t3 := t2       # next_c
# Which can be changed into:
#          BINARY t3 := t1 + t2
# Note here the binary op may also be an unary op or a function, or anything
# that may have a return value.
@reg_optim
def case3_can(codes):
    opt_idx = []
    for i, c in enumerate(codes):
        if i == len(codes) - 1:  # last code: abandon
            continue
        next_c = codes[i + 1]
        if c.code_t in (tac.ASSIGN, tac.BINARY, tac.UNARY, tac.CALL):
            if next_c.code_t in (tac.ASSIGN, tac):
                if c.x == next_c.y:  # can optimiz
                    opt_idx.append(i)
    if opt_idx:
        return make_optim(True, case3_run, opt_idx=opt_idx)
    else:
        return make_optim(False)

def case3_run(codes, argl, argd):
    for i in argd['opt_idx']:
        this_c = codes[i]
        next_c = codes[i + 1]
        if not this_c or not next_c:
            continue  # a hole
        this_c.x = next_c.x
        codes[i + 1] = None
    # some clean up
    codes[:] = [c for c in codes if c]


# reduce the usage of the var names
# to reduce the burden of the registers
# but how to?
# phase one: fetch one var -- t1
# phase two: scan the existence of this var
# phase three: fetch another var -- t2
# phase four: replace all et2
#
# be ware of control flows!
# but a flow graph is absolutely needed...
@reg_optim
def reduce_name_trivial1(codes):
    ncf = no_control_flows(codes)
    code_ranges = calculate_ranges(codes, ncf)
    code_ranges.sort(key=lambda t: t[0])  # sort by from. is it worth?
    while code_ranges:
        this_c = code_ranges.pop()
        for c in code_ranges:
            if c[1] < this_c[0]:  # no overlap: can replace
                name_replace(codes, this_c, c)
                return make_optim(False)
    return make_optim(False)

def no_control_flows(codes):
    for c in codes:
        if c.code_t in (tac.BRANCH, tac.CBRANCH):
            return False
    return True

def calculate_ranges(codes, ncf):
    # will consider any jump as the ...
    # (from, to, vname)
    d = {}
    for i, c in enumerate(codes):
        vns = c.varnames()
        for vn in vns:
            if vn not in d:
                d[vn] = [i, i]
            else:
                d[vn][1] = i
    to_ret = [item + [key] for (key, item) in d.iteritems()]

    if not ncf:
        # has control flow: extend ranges using heuristic
        adjust_range_withcf(codes, to_ret)
        #to_ret = calculate_range_withcf(codes)
    return to_ret

def adjust_range_withcf(codes, rgs):
    """current ctrl needed is 2"""
    for nth, (begin, end, vn) in enumerate(rgs):
        ctrl_need = 4
        left_got = 0  # left has got n ctrl flows
        rite_got = 0  # rite has got n

        left_reached = begin
        i = begin - 1
        while i >= 0:
            c = codes[i]
            if c.code_t in (tac.BRANCH, tac.LABEL, tac.CBRANCH):
                left_reached = i
                left_got += 1
            if left_got >= ctrl_need:
                break
            i -= 1

        rite_reached = end
        i = end + 1
        while i < len(codes):
            c = codes[i]
            if c.code_t in (tac.BRANCH, tac.LABEL, tac.CBRANCH):
                rite_reached = i
                rite_got += 1
            if rite_got >= ctrl_need:
                break
            i += 1

        if left_reached == begin or rite_reached == end:  # out of flow
            continue

        rgs[nth][0] = left_reached
        rgs[nth][1] = rite_reached


def calculate_range_withcf(codes):

    control_begin = None
    control_end = None

    for i, c in enumerate(codes):
        if c.code_t in (tac.BRANCH, tac.CBRANCH, tac.LABEL):
            if not control_begin:
                control_begin = i
            else:
                control_end = i

    # to find the longest control, which is not good..
    # here i try to find the control with padding (1 - 2)

    d = {}
    for i, c in enumerate(codes):
        vns = c.varnames()
        for vn in vns:
            if vn not in d:
                if control_begin <= i <= control_end:
                    d[vn] = [control_begin, control_end]
                else:
                    d[vn] = [i, i]
            else:
                if d[vn][1] < i:
                    d[vn][1] = i
    return [item + [key] for (key, item) in d.iteritems()]

def name_replace(codes, c_from, c_to):
    for i, c in enumerate(codes):
        c.replace_var(c_from[2], c_to[2])



################## try to reduce name usage by elimiating temporary var
# case:
#        t1 := t2
#        ... (t2 is not modified and no ctrl flow occured)
#        t3 := t1 op xxx
#
#        and t1 can be eliminated
@reg_optim
def reduce_name_2(codes):
    occurence = {}  # name: ([idx at left], [idx at right])
    for i, c in enumerate(codes):
        xvals = c.xvals()
        if xvals:
            x = xvals[0]
            if x not in occurence:
                occurence[x] = ([], [])
            occurence[x][0].append(i)
        yvals = c.yvals()
        for y in yvals:
            if y not in occurence:
                occurence[y] = ([], [])
            occurence[y][1].append(i)

    for name, (at_left, at_rite) in occurence.iteritems():
        if len(at_left) == 1 and len(at_rite) == 1:
            a = at_left[0]
            b = at_rite[0]
            if codes[a].code_t == tac.ASSIGN and codes[b].code_t == tac.BINARY:
                codes[b].replace_var(name, codes[a].y)  # do replace
                codes[a].x = codes[a].y  # del it
            #print name, codes[at_left[0]], codes[at_rite[0]]

@reg_optim
def elimin_void_return(codes):
    # if the call result is not used, turn it to None
    # if the assign result is not used, also
    to_ret = []
    for c in codes:
        found = False
        if c.code_t in (tac.ASSIGN, tac.CALL):
            pivot = c.x
            for i, cc in enumerate(codes):
                if cc is not c and pivot in cc.yvals():
                    found = True
                    break
            if found:
                continue
            else:
                if c.code_t == tac.ASSIGN:
                    c.x = c.y
                elif c.code_t == tac.CALL:
                    c.x = None


# XXX: not safe
# heuristic dead code elimination
# Assign, ?, Binary
#@reg_optim
def heuristic_dce1(codes):
    for i, c in enumerate(codes[:-2]):
        nc = codes[i + 2]
        if c.code_t == tac.ASSIGN and nc.code_t == tac.BINARY:
            if c.x == nc.y:
                nc.y = c.y
                break
            elif c.x == nc.z:
                nc.z = c.y
                break

# find those vars that are assigned but soon rewritten
#@reg_optim
def heuristic_dce2(codes):
    for i, c in enumerate(codes):
        if c.code_t == tac.ASSIGN:
            i += 1
            while i < len(codes):
                cc = codes[i]
                if c.x in (cc.y, cc.z):
                    break
                elif cc.x == c.x:  # rewritten
                    c.x = c.y
                    break
                i += 1
                

# find those vars that only appears in the left

# simple const propagand, to further eliminate simple assigns
# buggy. need control flow
#@reg_optim
def const_propagand1(codes):
    for i, c in enumerate(codes):
        if c.code_t == tac.ASSIGN:
            modified_till_use(codes, c, i)
    return make_optim(False)

def modified_till_use(codes, orig_c, i):
    saved_i = i
    i += 1
    while i < len(codes):  # orig_c: upper assign. c: curr c
        c = codes[i]
        if c.code_t in (tac.ASSIGN, tac.UNARY) and c.y == orig_c.x:
            c.y = orig_c.y
        elif c.code_t in (tac.LOAD, tac.STORE) and c.p == orig_c.x:
            c.p = orig_c.y
        elif c.code_t == tac.BINARY:
            if c.y == orig_c.x:
                c.y = orig_c.y
            elif c.z == orig_c.x:
                c.z = orig_c.y
        elif c.code_t in (tac.BRANCH, tac.CBRANCH):
            return
        elif orig_c.x == c.x:  # no we need flow graph
            break
        elif orig_c.x in c.varnames():  # modified
            return
        i += 1
    orig_c.x = orig_c.y  # optimize out

