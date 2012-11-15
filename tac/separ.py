
import tac

def to_func(codes):
    """separate codes to functions
    @param codes: a list of raw tacs
    @return: a dict of (func-name, codes)
    """
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

