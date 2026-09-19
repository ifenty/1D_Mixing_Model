C $Header$
C $Name$

#include "PACKAGES_CONFIG.h"
#include "CPP_OPTIONS.h"

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: INI_WRAPPER_GRID

C !INTERFACE:
      SUBROUTINE INI_WRAPPER_GRID( myThid )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE INI_WRAPPER_GRID                              |
C     | o Initialize grid for KPP standalone wrapper             |
C     *==========================================================*
C     | Sets up vertical grid spacing (drF, rF, rC) either from |
C     | default values or from input arrays passed via arguments|
C     *==========================================================*
C \ev

C !USES:
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "GRID.h"

C !INPUT PARAMETERS:
      INTEGER myThid

C !LOCAL VARIABLES:
      INTEGER k, bi, bj
      _RL zTop, zBot
CEOP

      bi = 1
      bj = 1

C     -------------------------------------------
C     Default uniform vertical grid: 10m spacing
C     -------------------------------------------
      DO k = 1, Nr
       drF(k) = 10.0 _d 0  ! Default 10m cell thickness
      ENDDO

C     Compute interface depths (rF)
C     Convention: rF(1) = 0 at surface, negative downward
      rF(1) = 0.0 _d 0
      DO k = 1, Nr
       rF(k+1) = rF(k) - drF(k)
      ENDDO

C     Compute cell center depths (rC)
      DO k = 1, Nr
       rC(k) = 0.5 _d 0 * (rF(k) + rF(k+1))
      ENDDO

C     Compute vertical spacing between cell centers (drC)
      drC(1) = ABS(rC(1))
      DO k = 2, Nr
       drC(k) = ABS(rC(k) - rC(k-1))
      ENDDO
      drC(Nr+1) = drF(Nr)

C     Reciprocals (for efficiency)
      DO k = 1, Nr
       recip_drF(k) = 1.0 _d 0 / drF(k)
       recip_drC(k) = 1.0 _d 0 / drC(k)
      ENDDO
      recip_drC(Nr+1) = 1.0 _d 0 / drC(Nr+1)

C     -------------------------------------------
C     Horizontal grid (dummy for 1D column)
C     -------------------------------------------
      dxF(1,1,bi,bj) = 1.0 _d 5  ! 100 km
      dyF(1,1,bi,bj) = 1.0 _d 5
      rA(1,1,bi,bj) = dxF(1,1,bi,bj) * dyF(1,1,bi,bj)

C     Reciprocals
      recip_dxF(1,1,bi,bj) = 1.0 _d 0 / dxF(1,1,bi,bj)
      recip_dyF(1,1,bi,bj) = 1.0 _d 0 / dyF(1,1,bi,bj)
      recip_rA(1,1,bi,bj) = 1.0 _d 0 / rA(1,1,bi,bj)

C     -------------------------------------------
C     Ocean mask (all water, no land)
C     -------------------------------------------
      DO k = 1, Nr
       maskC(1,1,k,bi,bj) = 1.0 _d 0
      ENDDO

C     Debug output
      WRITE(6,'(A)') 'INI_WRAPPER_GRID: Grid initialized'
      WRITE(6,'(A,I3)') '  Nr = ', Nr
      WRITE(6,'(A,F10.2,A)') '  drF(1) = ', drF(1), ' m'
      WRITE(6,'(A,F10.2,A)') '  rF(1) = ', rF(1), ' m (surface)'
      WRITE(6,'(A,F10.2,A)') '  rF(Nr+1) = ', rF(Nr+1), ' m (bottom)'
      WRITE(6,'(A,F10.2,A)') '  Total depth = ', ABS(rF(Nr+1)), ' m'

      RETURN
      END
