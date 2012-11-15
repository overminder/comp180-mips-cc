;; omlisp lib
;; note that function args are pushed reversily.

(defun (newline:void) ()
  (print '\n'))

;; but the user must also press the enter...
(defmacro (getc:byte) ()
  (asm "li $v0, 12"
       "syscall"
       "addi $a3, $v0, 0"
       "li $v0, 12"
       "syscall"
       "addi $v0, $a3, 0"
       "jr $ra"))

(defmacro (input:int) ()
  (asm "li $v0, 5"
       "syscall"
       "jr $ra"))

(defmacro (x86-getc:byte) ()
  (asm "lui $a0, 0xffff"
       "_getc_1:"
       "lw $a1, 0($a0)"
       "andi $a1, $a1, 1"
       "beq $a1, $zero, _getc_1"
       "lw $v0, 4($a0)"
       "jr $ra"))

