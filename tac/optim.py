
all_optims = []
N_PASSES = 5
want_optim = 1

def reg_optim(nth=0, name=None):
    """a decorator, register the given function to the optimization list.
    later functions will be sorted by nth"""
    def call(func):
        _name = name
        if _name is None:
            _name = func.__name__
        all_optims.append((nth, _name, func))
        return func
    return call


def _cleanup_nones(codes):
    """remove None in the codes"""
    codes[:] = [c for c in codes if c is not None]

def auto_cleanup_nones(f):
    def call(*argl, **argd):
        f(*argl, **argd)
        _cleanup_nones(argl[0])
    return call

def _safe_emap(codes, f):
    """safe enumerate map, with list attached also"""
    for i, c in enumerate(codes):
        if c is not None:
            f(i, c, codes)

def auto_foreach(f):
    """decorator for easy for-each"""
    def wrap(codes):
        _safe_emap(codes, f)
    return wrap

def run_all(codes):
    """will mutate the codes"""
    if not want_optim:
        return
    all_optims.sort(key=lambda t: t[0])
    for _ in xrange(N_PASSES):
        for i, (nth, name, func) in enumerate(all_optims):
            try:
                func(codes)
            except:
                print 'Optimization failed at (%d, %d, %s)' % (i, nth, name)
                raise

