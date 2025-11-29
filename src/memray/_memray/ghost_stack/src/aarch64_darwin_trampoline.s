/**
 * GhostStack Return Trampoline - AArch64 macOS (Darwin)
 * ======================================================
 *
 * This assembly implements the return address trampoline for shadow stack unwinding
 * on Apple Silicon (AArch64) macOS systems.
 *
 * Exception Handling Strategy:
 *   On Darwin, the CFI region must cover all code that may be active during
 *   exception unwinding. We place the public symbol BEFORE .cfi_startproc
 *   (which is allowed) and extend CFI to cover all code including the landing pad.
 */

.section	__TEXT,__text,regular,pure_instructions
.build_version macos, 14, 0	sdk_version 15, 1
.p2align	2

/* ==========================================================================
 * _ghost_ret_trampoline - The trampoline entry point
 * ==========================================================================
 * Public symbol declared BEFORE .cfi_startproc (this is allowed on Darwin).
 * The CFI region covers from here through the landing pad.
 */
.globl _ghost_ret_trampoline
.private_extern _ghost_ret_trampoline
_ghost_ret_trampoline:
.cfi_startproc
.cfi_personality 155, ___gxx_personality_v0
.cfi_lsda 16, LLSDA0
.cfi_undefined lr

/* Exception try region starts here */
LEHB0:
    /* Step 1: Save return value registers */
    sub sp, sp, #64
.cfi_def_cfa_offset 64
    stp x0, x1, [sp, #0]
    stp x2, x3, [sp, #16]
    stp x4, x5, [sp, #32]
    stp x6, x7, [sp, #48]

    /* Step 2: Call into C++ to get the real return address */
    mov x0, sp
    add x0, x0, #64
    bl _ghost_trampoline_handler

    /* Step 3: Prepare return address and restore registers */
    mov lr, x0

    ldp x0, x1, [sp, #0]
    ldp x2, x3, [sp, #16]
    ldp x4, x5, [sp, #32]
    ldp x6, x7, [sp, #48]
    add sp, sp, #64
.cfi_def_cfa_offset 0

    /* Step 4: Return to real caller */
    ret
LEHE0:

/* ==========================================================================
 * Exception landing pad
 * ==========================================================================
 */
L3:
    bl _ghost_exception_handler
    mov lr, x0
    b ___cxa_rethrow

.cfi_endproc

/* For backwards compatibility, alias _ghost_ret_trampoline_start */
.globl _ghost_ret_trampoline_start
.private_extern _ghost_ret_trampoline_start
.set _ghost_ret_trampoline_start, _ghost_ret_trampoline


/* ==========================================================================
 * LSDA (Language Specific Data Area)
 * ==========================================================================
 */
.section __TEXT,__gcc_except_tab
.align 2
LLSDA0:
    .byte 0xff                  /* @LPStart encoding: omit */
    .byte 0x9b                  /* @TType encoding: indirect pcrel sdata4 */
    .uleb128 LLSDATT0-LLSDATTD0 /* @TType base offset */
LLSDATTD0:
    .byte 0x1                   /* Call site encoding: uleb128 */
    .uleb128 LLSDACSE0-LLSDACSB0    /* Call site table length */
LLSDACSB0:
    /* Call site entry: covers the entire trampoline */
    .uleb128 LEHB0-_ghost_ret_trampoline  /* Region start */
    .uleb128 LEHE0-LEHB0                  /* Region length */
    .uleb128 L3-_ghost_ret_trampoline     /* Landing pad */
    .uleb128 0x1                          /* Action: index 1 */
LLSDACSE0:
    .byte 0x1                   /* Action table entry */
    .byte 0                     /* No next action */
    .align 2
    .long 0                     /* Type table: 0 = catch(...) */
LLSDATT0:

.section __DATA,__data
.align 3
.private_extern ___gxx_personality_v0

.subsections_via_symbols
