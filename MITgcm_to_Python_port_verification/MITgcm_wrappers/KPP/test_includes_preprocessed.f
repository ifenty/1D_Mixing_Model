# 1 "test_includes.F"
# 1 "<built-in>"
# 1 "<command-line>"
# 1 "test_includes.F"

# 1 "./include/SIZE.h" 1
CBOP
C    !ROUTINE: SIZE.h
C    !INTERFACE:
C    include SIZE.h
C    !DESCRIPTION: \bv
C     *==========================================================*
C     | SIZE.h Declare size of underlying computational grid.
C     *==========================================================*
C     | Simplified for 1D column KPP wrapper:
C     |   - Single horizontal point (sNx=1, sNy=1)
C     |   - 50 vertical levels (Nr=50)
C     |   - No MPI (nPx=1, nPy=1)
C     |   - Minimal overlap (OLx=1, OLy=1)
C     *==========================================================*
C     \ev
CEOP

C     Grid dimensions
      INTEGER sNx, sNy, OLx, OLy, nSx, nSy, nPx, nPy, Nx, Ny, Nr
      PARAMETER (
     &           sNx =   1,
     &           sNy =   1,
     &           OLx =   1,
     &           OLy =   1,
     &           nSx =   1,
     &           nSy =   1,
     &           nPx =   1,
     &           nPy =   1,
     &           Nx  = sNx*nSx*nPx,
     &           Ny  = sNy*nSy*nPy,
     &           Nr  =  50)

C     MAX_OLX :: Set to the maximum overlap region size of any array
C     MAX_OLY    that will be exchanged. Controls the sizing of exch
C                routine buffers.
      INTEGER MAX_OLX
      INTEGER MAX_OLY
      PARAMETER ( MAX_OLX = OLx,
     &            MAX_OLY = OLy )
# 2 "test_includes.F" 2
      PROGRAM TEST
      END
