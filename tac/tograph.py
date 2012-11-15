
import tac

# here the tac will be changed into a internal repr of...
def analyze_labels(fcode):
    """
    @returns: labels, a dict of (label-name, line-number)
    """
    labels = {}

    for i, c in enumerate(fcode):
        if c.code_t == tac.LABEL:
            lbl = c.L
            if lbl in labels:
                raise InterpTimeError, 'redefination of label %r' % c
            labels[lbl] = i
    return labels

def find_leaders(fcode):
    labels = analyze_labels(fcode)
    for i, c in enumerate(fcode):
        if i == 0:
            c.is_leader = True
        elif c.code_t in (tac.BRANCH, tac.CBRANCH):
            # is branch, the target of the jump is a leader
            j_target = labels[c.L]
            fcode[j_target].is_leader = True
            if i + 1 < len(fcode):
                fcode[i + 1].is_leader = True


