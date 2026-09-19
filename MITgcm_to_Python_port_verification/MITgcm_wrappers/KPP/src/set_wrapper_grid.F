C $Header$
C $Name$

#include "PACKAGES_CONFIG.h"
#include "CPP_OPTIONS.h"

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: SET_WRAPPER_GRID

C !INTERFACE:
      SUBROUTINE SET_WRAPPER_GRID(
     I     drF_in, rF_in, rC_in,
     I     myThid )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE SET_WRAPPER_GRID                              |
C     | o Override default grid with user-provided values        |
C     *==========================================================*
C     | Call this AFTER INI_WRAPPER_GRID to override defaults  |
C     *==========================================================*
C \ev

C !USES:
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "GRID.h"

C !INPUT PARAMETERS:
      INTEGER myThid
      _RL drF_in(Nr)
      _RL rF_in(Nr+1)
      _RL rC_in(Nr)

C !LOCAL VARIABLES:
      INTEGER k
CEOP

C     Copy input arrays to COMMON block
      DO k = 1, Nr
       drF(k) = drF_in(k)
       rF(k) = rF_in(k)
       rC(k) = rC_in(k)
      ENDDO
      rF(Nr+1) = rF_in(Nr+1)

C     Recompute drC (spacing between cell centers)
      drC(1) = ABS(rC(1))
      DO k = 2, Nr
       drC(k) = ABS(rC(k) - rC(k-1))
      ENDDO
      drC(Nr+1) = drF(Nr)

C     Recompute reciprocals
      DO k = 1, Nr
       recip_drF(k) = 1.0 _d 0 / drF(k)
       recip_drC(k) = 1.0 _d 0 / drC(k)
      ENDDO
      recip_drC(Nr+1) = 1.0 _d 0 / drC(Nr+1)

      WRITE(6,'(A)') 'SET_WRAPPER_GRID: Grid overridden from input'
      WRITE(6,'(A,F10.2,A)') '  drF(1) = ', drF(1), ' m'
      WRITE(6,'(A,F10.2,A)') '  rF(Nr+1) = ', rF(Nr+1), ' m'

      RETURN
      END
