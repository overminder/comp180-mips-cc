
import tac

@tac.unary('deref')
def dereference(var):
    return 'lw %(var)s, 0($%(var)s)' % locals()

@tac.unary('neg')
def negative(var):
    return 'sub %(var)s, $zero, %(var)s' % locals()

@tac.binary('+')
def adder(l, r):
    return 'add %(l)s, %(l), %(r)s' % locals()

@tac.binary('-')
def adder(l, r):
    return 'sub %(l)s, %(l), %(r)s' % locals()

@tac.binary('*')
def adder(l, r):
    return 'mul %(l)s, %(l), %(r)s' % locals()

@tac.binary('/')
def adder(l, r):
    return 'div %(l)s, %(l), %(r)s' % locals()

