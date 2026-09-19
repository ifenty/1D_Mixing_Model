# Fortran Coding Rules for MITgcm Modifications

## Critical Rules

### 1. Line Length Limit: 72 Characters
**NEVER exceed 72 characters in fixed-form Fortran (.F files)**

- Fortran fixed-form has strict line length limits
- Lines longer than 72 characters will cause compilation errors
- Use continuation lines with `&` in column 6 for long statements

**Example - WRONG:**
```fortran
      IF (myIter .GE. 2310 .AND. myIter .LE. 2315 .AND. i .EQ. 1 .AND. bi .EQ. 1 .AND. bj .EQ. 1) THEN
```

**Example - CORRECT:**
```fortran
      IF (myIter .GE. 2310 .AND. myIter .LE. 2315 .AND.
     &    i .EQ. 1 .AND. bi .EQ. 1 .AND. bj .EQ. 1) THEN
```

### 2. Continuation Character
- Column 6 must contain `&` or any non-space/non-zero character for continuation
- Continuation lines should be indented consistently
- Maximum of 19 continuation lines per statement

### 3. Column Layout
```
Columns 1-5:   Statement labels (optional)
Column 6:      Continuation character (& or any char)
Columns 7-72:  Fortran statements
Columns 73-80: Ignored (historically used for sequence numbers)
```

### 4. Comments
```fortran
C     This is a comment (C in column 1)
c     Lowercase c also works
!     Exclamation mark also works (more modern)
```

## Common Compilation Errors

### "Missing ')' in statement at or before (1)"
**Cause**: Line exceeds 72 characters
**Fix**: Break into multiple lines with continuation character

### "Non-numeric character in statement label"
**Cause**: Often a misplaced character in columns 1-5
**Fix**: Check that labels are numeric only, or leave columns 1-5 blank

## Tools

### Check Line Length
```bash
# Find lines longer than 72 characters
awk 'length > 72 {print NR": "length" chars: "$0}' your_file.F
```

### Auto-format (use with caution)
```bash
# Use fprettify or similar tools, but verify output!
fprettify --line-length 72 your_file.F
```

## References
- [Fortran Standards](https://fortran-lang.org/)
- [MITgcm Documentation](https://mitgcm.readthedocs.io/)
