In memory of passed days working on the COMP180 project!
----------------------------------------------------

Just found this dust-covered project at somewhere. Welp, this compiler
was really a huge hack (and it even worked in some ways!).

There were several "innovations":

- No register allocation. Each function can only use a limited number
  of **virtual** register as virtual registers were almost directly
  mapped to machine registers. Although Mips has about 32 machine registers,
  obviously it's still not enough.

- Just plain wrong optimizations. I tried to optimize away some instructions
  so that the pressure on register allocation could be less but at first
  I didn't even know what a basic block is... Then I read from some articles
  and found that I need to build some sort of "graph". Then I started writing
  several "optimizations" that might or might not work in different cases.
  As as result, I learned to carefully avoid those bugs in my compiler by 
  rewriting the source code that is going to be compiled.

- Type systems! I decided and managed to build a cee-language-like type system
  where there are ints, bytes, voids and pointers. They were doing more bads
  than goods at the beginning but soon I got used to them. From a
  retrospective point of view, I think actually this decision is essential as
  it helped me to solved several bugs in the source language.

