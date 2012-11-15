
;; fixed-size array

(require stdlib
         stdio)

;; hide the length and return the array with could be accessed using nth
(defun (array-init:int*) (size:int)
  (defvar ret:int* (int* (malloc (+ 4 (<< size 2)))))
  (set-nth! ret 0 size)  ; store the length
  (+ ret 1))  ; return the actual array

;; get the length of the array
(defun (array-len:int) (array-obj:int*)
  (nth array-obj (- 0 1)))

(defun (array-sum:int) (array-obj:int*)
  (let ((size:int (array-len array-obj))
        (ret:int 0)
        (i:int 0))
    (while (< i size)
           (set! ret (+ ret (nth array-obj i)))
           (set! i (+ i 1)))
    ret))

