/**
 * GhostStack Return Trampoline - AArch64 macOS (Darwin)
 */

.section	__TEXT,__text,regular,pure_instructions
.build_version macos, 14, 0	sdk_version 15, 1
.p2align	2

.globl _ghost_ret_trampoline
.private_extern _ghost_ret_trampoline
_ghost_ret_trampoline:
.cfi_startproc
.cfi_personality 0x9b, L_personality_ptr
.cfi_lsda 0x1b, LLSDA0
.cfi_undefined lr

LEHB0:
    sub sp, sp, #64
.cfi_def_cfa_offset 64
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
.cfi_def_cfa_offset 0

    ret

L3:
    bl _ghost_exception_handler
    mov lr, x0
    b ___cxa_rethrow

Ltrampoline_end:
    nop  /* padding to ensure proper size */
.cfi_endproc

.globl _ghost_ret_trampoline_start
.private_extern _ghost_ret_trampoline_start
.set _ghost_ret_trampoline_start, _ghost_ret_trampoline

/* Indirect personality function pointer */
.section __DATA,__data
.p2align 3
L_personality_ptr:
    .quad ___gxx_personality_v0

/* LSDA */
.section __TEXT,__gcc_except_tab
.p2align 2
LLSDA0:
    .byte 0xff
    .byte 0x9b
    .uleb128 LLSDATT0-LLSDATTD0
LLSDATTD0:
    .byte 0x1
    .uleb128 LLSDACSE0-LLSDACSB0
LLSDACSB0:
    .uleb128 LEHB0-_ghost_ret_trampoline
    .uleb128 L3-LEHB0
    .uleb128 L3-_ghost_ret_trampoline
    .uleb128 0x1
LLSDACSE0:
    .byte 0x1
    .byte 0
    .p2align 2
    .long 0
LLSDATT0:

.subsections_via_symbols
