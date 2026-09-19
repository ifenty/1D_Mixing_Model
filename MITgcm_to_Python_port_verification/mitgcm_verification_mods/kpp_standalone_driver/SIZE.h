C     Minimal SIZE.h for the standalone KPPMIX driver.
C     Deliberately NOT the real 1D_ocean_ice_column SIZE.h (which has
C     OLx=OLy=3 for halo/exchange -- irrelevant here, since we call
C     KPPMIX directly with no tiling/exchange machinery). With OLx=OLy=0
C     and sNx=sNy=1, KPP_PARAMS.h's imt=(sNx+2*OLx)*(sNy+2*OLy) = 1: a
C     clean single-column layout, no flat-index arithmetic needed.
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
     &           OLx =   0,
     &           OLy =   0,
     &           nSx =   1,
     &           nSy =   1,
     &           nPx =   1,
     &           nPy =   1,
     &           Nx  = sNx*nSx*nPx,
     &           Ny  = sNy*nSy*nPy,
     &           Nr  =  23)

      INTEGER MAX_OLX
      INTEGER MAX_OLY
      PARAMETER ( MAX_OLX = OLx,
     &            MAX_OLY = OLy )
