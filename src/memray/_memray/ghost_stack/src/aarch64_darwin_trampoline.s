/**
 * GhostStack Return Trampoline - AArch64 macOS (Darwin)
 * ======================================================
 *
 * This assembly implements the return address trampoline for shadow stack unwinding
 * on Apple Silicon (AArch64) macOS systems.
 *
 * When GhostStack patches a return address to point here, this trampoline:
 *   1. Saves the function's return value registers (x0-x7)
 *   2. Calls _ghost_trampoline_handler() to get the real return address
 *   3. Restores the return value registers and returns to the real address
 *
 * macOS/Darwin Exception Handling Strategy:
 *   Darwin's assembler doesn't allow non-private labels (symbols not starting with L)
 *   inside CFI regions (.cfi_startproc/.cfi_endproc pairs). To work around this:
 *   1. Use private labels (Lxxx) for internal code structure
 *   2. Place ALL code inside a single CFI region for proper exception handling
 *   3. Use .set directives to create public symbol aliases pointing to private labels
 *
 * Apple ARM64 ABI Notes:
 *   - Return values: x0-x7 (same as AAPCS64)
 *   - Link register: x30 (LR) or 'lr' alias
 *   - Frame pointer: x29 (FP) or 'fp' alias
 *   - Stack: 16-byte aligned
 *
 * Pointer Authentication (PAC):
 *   On Apple Silicon with PAC enabled, return addresses are cryptographically
 *   signed. The C++ code uses xpaclri to strip the PAC before use.
 */

.section	__TEXT,__text,regular,pure_instructions
.build_version macos, 14, 0	sdk_version 15, 1
.p2align	2

/* ==========================================================================
 * Public symbol declarations (before CFI region)
 * ==========================================================================
 * Declare public symbols BEFORE the CFI region starts. We'll use .set
 * at the end to point these to the private labels inside the CFI region.
 */
.globl _ghost_ret_trampoline_start
.globl _ghost_ret_trampoline
.private_extern _ghost_ret_trampoline_start
.private_extern _ghost_ret_trampoline

/* ==========================================================================
 * CFI Region - Contains ALL exception-handling-relevant code
 * ==========================================================================
 * Everything from Ltrampoline_start through the landing pad is inside
 * this single CFI region, ensuring proper DWARF unwind info coverage.
 */
Ltrampoline_start:
.cfi_startproc
.cfi_personality 155, ___gxx_personality_v0
.cfi_lsda 16,LLSDA0
.cfi_undefined lr

/* Exception try region - any exception here redirects to L3 */
LEHB0:
    nop                         /* Placeholder marking exception region start */

/* ==========================================================================
 * Ltrampoline - The actual trampoline entry point (private label)
 * ==========================================================================
 * When a function returns through a patched return address, execution
 * lands here. We retrieve the real return address from GhostStack's
 * shadow stack and continue execution transparently.
 *
 * This label is INSIDE the CFI region so exceptions can unwind through it.
 */
Ltrampoline:

    /* -------------------------------------------------------------------------
     * Step 1: Save return value registers
     * -------------------------------------------------------------------------
     * The Apple ARM64 ABI uses x0-x7 for return values (same as AAPCS64).
     * We save all 8 to handle any return type (scalars, structs, HFA/HVA).
     *
     * Stack layout after save (64 bytes total):
     *   sp+48: x6, x7
     *   sp+32: x4, x5
     *   sp+16: x2, x3
     *   sp+0:  x0, x1 (most common return value location)
     */
    sub sp, sp, #64             /* Allocate 64 bytes (8 * 8 = 64) */
.cfi_def_cfa_offset 64
    stp x0, x1, [sp, #0]        /* Save x0, x1 (primary return values) */
    stp x2, x3, [sp, #16]       /* Save x2, x3 */
    stp x4, x5, [sp, #32]       /* Save x4, x5 */
    stp x6, x7, [sp, #48]       /* Save x6, x7 */

    /* -------------------------------------------------------------------------
     * Step 2: Call into C++ to get the real return address
     * -------------------------------------------------------------------------
     * First argument (x0): Original stack pointer location
     *   = current sp + 64 (our saved registers)
     *
     * This allows the C++ code to verify stack consistency if needed.
     * Returns the real return address in x0.
     */
    mov x0, sp
    add x0, x0, #64             /* x0 = original stack pointer */
    bl _ghost_trampoline_handler /* Call C++ handler */

    /* -------------------------------------------------------------------------
     * Step 3: Prepare return address and restore registers
     * -------------------------------------------------------------------------
     * Move real return address to lr (x30) BEFORE restoring x0,
     * since x0 will be overwritten by ldp.
     */
    mov lr, x0                  /* lr = real return address */

    /* Restore all return value registers */
    ldp x0, x1, [sp, #0]        /* Restore x0, x1 */
    ldp x2, x3, [sp, #16]       /* Restore x2, x3 */
    ldp x4, x5, [sp, #32]       /* Restore x4, x5 */
    ldp x6, x7, [sp, #48]       /* Restore x6, x7 */
    add sp, sp, #64             /* Deallocate stack frame */
.cfi_def_cfa_offset 0

    /* -------------------------------------------------------------------------
     * Step 4: Return to real caller
     * -------------------------------------------------------------------------
     * 'ret' uses lr (x30) as the return address by default.
     * The branch predictor will see this as a normal return.
     */
    ret

LEHE0:                          /* End of exception region */

/* ==========================================================================
 * Exception landing pad (inside CFI region)
 * ==========================================================================
 * When a C++ exception propagates through our patched frame, the unwinder
 * uses our LSDA to find this landing pad. We:
 *   1. Call _ghost_exception_handler to get real return addr
 *   2. Restore lr with the real address
 *   3. Tail-call ___cxa_rethrow to continue exception propagation
 *
 * The exception object pointer is passed in x0 by the runtime.
 */
L3:
    bl _ghost_exception_handler /* Get real return addr in x0 */
    mov lr, x0                  /* Restore lr with real return address */
    b ___cxa_rethrow            /* Tail-call rethrow (never returns) */

Ltrampoline_end:
.cfi_endproc

/* ==========================================================================
 * Public symbol aliases
 * ==========================================================================
 * Create public symbols pointing to the private labels inside the CFI region.
 * This allows C++ code to reference these symbols while keeping the actual
 * labels inside the CFI region for proper exception handling.
 */
.set _ghost_ret_trampoline_start, Ltrampoline_start
.set _ghost_ret_trampoline, Ltrampoline


/* ==========================================================================
 * LSDA (Language Specific Data Area)
 * ==========================================================================
 * Exception handling metadata for ___gxx_personality_v0.
 * This tells the C++ runtime:
 *   - Where our "try" region is (LEHB0 to LEHE0)
 *   - Where to jump on exception (L3)
 *   - What types to catch (0 = catch all, i.e., catch(...))
 *
 * Format follows DWARF exception handling specification.
 * Note: Offsets are relative to Ltrampoline_start (the CFI function start).
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
    /* Call site entry: our try region covers the entire trampoline */
    .uleb128 LEHB0-Ltrampoline_start  /* Region start (relative to function) */
    .uleb128 LEHE0-LEHB0              /* Region length */
    .uleb128 L3-Ltrampoline_start     /* Landing pad (relative to function) */
    .uleb128 0x1                      /* Action: index 1 in action table */
LLSDACSE0:
    .byte 0x1                   /* Action table entry */
    .byte 0                     /* No next action */
    .align 2
    .long 0                     /* Type table: 0 = catch(...) */
LLSDATT0:

/* ==========================================================================
 * Symbol declarations
 * ==========================================================================
 * Declare reference to the C++ personality function.
 * On macOS, this is ___gxx_personality_v0 (three underscores total).
 */
.section __DATA,__data
.align 3
.private_extern ___gxx_personality_v0

/* Enable dead code stripping optimization */
.subsections_via_symbols
