CBOP
C    !ROUTINE: SIZE.h
C    !INTERFACE:
C    include SIZE.h
C    !DESCRIPTION: \bv
C     Standalone GGL90_CALC driver's SIZE.h. sNx=sNy=1, OLx=OLy=2
C     preserved from vermix's real code_validation/SIZE.h (real halo
C     width, needed by GGL90_CALC's own loop bounds/array declarations).
C     Nr is auto-regenerated on every run from the input file's own
C     ntimeIn/nrIn header -- do not hand-edit.
      INTEGER sNx
      INTEGER sNy
      INTEGER OLx
      INTEGER OLy
      INTEGER nSx
      INTEGER nSy
      INTEGER nPx
      INTEGER nPy
      INTEGER Nx
      INTEGER Ny
      INTEGER Nr
      PARAMETER (
     &           sNx =   1,
     &           sNy =   1,
     &           OLx =   2,
     &           OLy =   2,
     &           nSx =   1,
     &           nSy =   1,
     &           nPx =   1,
     &           nPy =   1,
     &           Nx  = sNx*nSx*nPx,
     &           Ny  = sNy*nSy*nPy,
     &           Nr  =  50)

      INTEGER MAX_OLX
      INTEGER MAX_OLY
      PARAMETER ( MAX_OLX = OLx,
     &            MAX_OLY = OLy )
