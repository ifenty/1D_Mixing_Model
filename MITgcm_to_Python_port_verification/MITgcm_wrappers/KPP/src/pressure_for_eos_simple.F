C Simple wrapper-specific PRESSURE_FOR_EOS
C Uses basic hydrostatic pressure for 1D column

      SUBROUTINE PRESSURE_FOR_EOS(
     I        bi, bj, iMin, iMax, jMin, jMax,  k, dpRef,
     O        locPres,
     I        myThid )

      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "GRID.h"

      INTEGER bi, bj, k
      INTEGER iMin,iMax,jMin,jMax
      _RL dpRef
      _RL locPres(1-OLx:sNx+OLx,1-OLy:sNy+OLy)
      INTEGER myThid

      INTEGER  i,j

C     Simple hydrostatic pressure: P = rho0 * g * |z|
C     rC(k) is depth of cell center (negative downward)
C     dpRef is pressure offset
      DO j=1-OLy,sNy+OLy
       DO i=1-OLx,sNx+OLx
        locPres(i,j) = rhoConst * gravity * ABS(rC(k)) + dpRef
       ENDDO
      ENDDO

      RETURN
      END
