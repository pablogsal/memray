/**
 * GhostStack Return Trampoline - AArch64 macOS (Darwin)
 */

.section	__TEXT,__text,regular,pure_instructions
.build_version macos, 14, 0	sdk_version 15, 1
.p2align	2

.globl _ghost_ret_trampoline
.private_extern _ghost_ret_trampoline
_ghost_ret_trampoline:
.cfi_startproc simple
.cfi_signal_frame
.cfi_def_cfa sp, 0
.cfi_undefined lr

LEHB0:
    sub sp, sp, #64
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]

    mov x0, sp
    add x0, x0, #64
    bl _ghost_trampoline_handler

    mov lr, x0

    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    add sp, sp, #64

    ret
LEHE0:

L3:
    bl _ghost_exception_handler
    mov lr, x0
    b ___cxa_rethrow

.cfi_endproc

.globl _ghost_ret_trampoline_start
.private_extern _ghost_ret_trampoline_start
.set _ghost_ret_trampoline_start, _ghost_ret_trampoline

.subsections_via_symbols
