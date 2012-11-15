from collections import defaultdict
import optim
import tac

"""
optimizations.
I suddenly feel that pointer alias analysis is extremely hard...
"""

@optim.reg_optim(0, 'constant-folding-for-binary-op')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes):
        if c.typep('BINARY') and c.immp():
            c.y = c.fold()
            c.code_t = tac.ASSIGN
            del c.z

@optim.reg_optim(10, 'move-immediate-to-z-for-binary-op')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes):
        if all((c.typep('BINARY'), c.immp('y'),
                    not c.immp('z'), c.op in ['+', '*'])):
            c.y, c.z = c.z, c.y

@optim.reg_optim(10, 'algebraic-simplificaton-for-binary-op')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes):
        if c.typep('BINARY') and c.op in ['+', '-'] and c.z == 0:
            c.code_t = tac.ASSIGN
            del c.z
        elif c.typep('BINARY') and c.op in ['*', '/'] and c.z == 1:
            c.code_t = tac.ASSIGN
            del c.z

# applied when t1 := t2, t3 := (op) t1. will not delete the first one though.
@optim.reg_optim(50, 'peephole-eliminate-assign-before-assign')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes[:-1]):
        cn = codes[i + 1]
        if c.typep('ASSIGN') and cn.typep(['ASSIGN', 'BINARY', 'UNARY']):
            if cn.y == c.x:
                cn.y = c.y
            if cn.z == c.x:
                cn.z = c.y

# Be aware of self-changing. Make sure the expr will not change xval.
# applied when the second change will shadow the first change.
@optim.reg_optim(50, 'peephole-eliminate-shadowed-changes')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes[:-1]):
        cn = codes[i + 1]
        if cn.x == c.x:  # the former may be useless
            if c.typep('ASSIGN'):  # assign, (...)
                if cn.typep(['ASSIGN', 'UNARY', 'BINARY']):
                    # first assign is useless
                    codes[i] = None
            elif c.typep('UNARY') and c.x != c.y \
                    and cn.x != cn.y:  # unary, (...)
                # make sure xval is not changed
                if cn.typep(['ASSIGN', 'UNARY', 'BINARY']):
                    codes[i] = None
            elif c.typep('BINARY') and c.x not in (c.y, c.z) \
                    and cn.x not in (cn.x, cn.y):  # binary, (...)
                # again make sure xval is not changed
                if cn.typep(['ASSIGN', 'UNARY', 'BINARY']):
                    codes[i] = None

def get_occurence(codes):
    """get the occurence of all values in the codes, and return
    a two tuple of (x-occ, y-occ)
    x means the val is changed, y means the val is used"""
    x_appear = defaultdict(lambda: [])  # changed
    y_appear = defaultdict(lambda: [])  # used
    for i, c in enumerate(codes):
        if not c:
            continue
        for xval in c.xvals():
            x_appear[xval].append(i)
        for yval in c.yvals():
            y_appear[yval].append(i)
    return (x_appear, y_appear)

# applied when the xval is never used.
@optim.reg_optim(0, 'peephole-eliminate-unused-xval')
@optim.auto_cleanup_nones
def _run(codes):
    x_appear, y_appear = get_occurence(codes)
    for i, c in enumerate(codes):
        for xval in c.xvals():
            if not y_appear[xval]:  # this var is used zero times
                if codes[i].typep('CALL'):
                    codes[i].x = None  # but not entirely delete.
                else:
                    codes[i] = None  # if no side effect then del it
                continue

# applied with FIRST = (x := unary/binary), SECOND = (x := assign).
# will not remove FIRST
# Again be aware of the mutating FIRST, eg. CALL
#@optim.reg_optim(0, 'peephole-do-op-rather-than-assign')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes[:-1]):
        cn = codes[i + 1]
        if cn.typep('ASSIGN') and cn.y == c.x and \
                c.typep(['UNARY', 'BINARY']) and c.x not in c.yvals():
            # copy FIRST's type, y, op and z to SECOND
            cn.code_t, cn.y, cn.op, cn.z = c.code_t, c.y, c.op, c.z

# applied when:
#
# ASSIGN t00 := t01
# ... (no leader,
#      t00 is not used as a yval,
#      t01 is not used as a xval)
# ASSIGN/UNARY/BINARY t00
#
# and the optimized result is:
# ASSIGN/UNARY/BINARY t00 using t01
#
@optim.reg_optim(50, 'peephole-eliminate-long-range-shadowed-variable')
@optim.auto_cleanup_nones
def _run(codes):
    for i, c in enumerate(codes):
        if c.typep('ASSIGN'):
            for ni, nc in enumerate(codes[i + 1:]):
                if nc.is_leader:  # dangerous.
                    break
                if c.y in nc.xvals():  # t01 is changed
                    break
                if nc.typep(['ASSIGN', 'UNARY', 'BINARY']) and nc.x == c.x:
                    if nc.y == c.x:  # forward self-mutating
                        nc.y = c.y
                    if nc.z == c.x:
                        nc.z = c.y
                    codes[i] = None  # safe to eliminate
                    break
                if c.x in nc.yvals():  # t00 is used. place here because forward
                                       # self-mutating make this safe.
                    break


# we call variables temporary when they are thrown away after use.
# Therefore, it's critical to identify them in order to maximize register usage 
def get_absolute_temporary_vars(codes):
    xoc_d, yoc_d = get_occurence(codes)
    to_ret = {}
    for vn, xoc in xoc_d.iteritems():
        if is_var_temporary(vn, xoc, yoc_d, codes):
            to_ret[vn] = (xoc, yoc_d[vn])
    return to_ret

# when a change is at the first,
# then any consequent use will be safe to change.. yes.
def is_var_temporary(vn, xoc, yoc_d, codes):
    if vn in yoc_d:  # is used in the right
        yoc = yoc_d[vn]
        #if xoc[-1] <= yoc[0]:  # possibly a temporary var
        if xoc[0] <= yoc[0] and xoc[-1] <= yoc[-1]:  # possibly a temporary var
            for i in xrange(xoc[0], yoc[-1] + 1):
                if not codes[i] or codes[i].is_leader:  # dangerous!
                    return False
            return True
    return False


# @see get_absolute_temporary_vars
# applied when several temporary variables are not found overlapping.
@optim.reg_optim(60, 'peephole-homogenize-temporary-variables')
@optim.auto_cleanup_nones
def _run(codes):
    tvars = get_absolute_temporary_vars(codes).items()
    tvars.sort(key=lambda t: t[1])
    # merge them, using 
    tmpval = None
    curr_start = None
    curr_end = None
    while tvars:
        vn, (xoc, yoc) = tvars.pop()
        if not tmpval:
            tmpval = vn
            curr_start = xoc[0]
            curr_end = yoc[-1]

        if xoc[0] >= curr_end:
            for i in xrange(xoc[0], yoc[-1] + 1):
                codes[i].replace_var(vn, tmpval)
            curr_end = yoc[-1]
        elif yoc[-1] <= curr_start:  # can merge
            for i in xrange(xoc[0], yoc[-1] + 1):
                codes[i].replace_var(vn, tmpval)
            curr_start = xoc[0]
        else:  # cannot merge.
            tmpval = vn
            curr_start = xoc[0]
            curr_end = yoc[-1]

# Additional optimization(though it will actually not affect the reg alloc)
# run dead code elimination.

#
# todo: optimize the push_arg. maybe this could be done in the mips?
#

