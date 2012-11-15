
class CompilerError(Exception):
    pass

class CompileTimeError(CompilerError):
    pass

class InterpTimeError(CompilerError):
    pass

class MipsGenError(CompilerError):
    pass

