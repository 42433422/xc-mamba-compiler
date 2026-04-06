/* Minimal RVV smoke: one vsetvli + trivial vector op. Requires -march=...v... */
        .text
        .globl  main
        .type   main, @function
main:
        li      a0, 4
        vsetvli t0, a0, e32, m1, ta, ma
        vmv.v.i v0, 0
        li      a0, 0
        ret
        .size   main, .-main
