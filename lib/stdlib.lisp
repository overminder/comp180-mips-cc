
(require stdio)

(defun (exit:void) ()
  (asm "li $v0, 10"
       "syscall"))

;; yeah we have macros...
;; although here we alloc by byte, len must be a multiplier of 4
(defmacro (malloc:void*) (len:int)
  (asm "li $v0, 9"
       "syscall"
       "jr $ra"))

(defun (eq?:int) (a:int b:int)
  (cond
    ((< a b)
      0)
    ((< b a)
      0)
    (else
      1)))

(defmacro (rand:int) (range:int)
  (asm "ori $a1, $0, 32749"

       "la $a3, randseed" ; which is added in the lib
       "lw $a3, 0($a3)"

       "multu $a3, $a1"
       "mflo $a3"
       "addiu $a3, $a3, 32649"

       "ori $a1, $0, 32497"
       "divu $a3, $a1"
       "mfhi $a3"

       "la $a1, randseed"
       "sw $a3, 0($a1)" ; save new seed

       "divu $a3, $a0"
       "mfhi $v0"

       "jr $ra"))

(defmacro (srand:void) (i:int)
  (asm "la $a3, randseed"
       "sw $a0, 0($a3)"
       "jr $ra"))

(defun (busy-wait:void) (k:int)
  (let ((x:int 0))
    (while (< x k) (set! x (+ x 1)))))

