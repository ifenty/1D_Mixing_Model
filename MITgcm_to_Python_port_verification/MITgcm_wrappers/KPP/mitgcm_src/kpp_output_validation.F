C $Header$
C $Name$

#include "KPP_OPTIONS.h"

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: KPP_OUTPUT_VALIDATION

C !INTERFACE:
      SUBROUTINE KPP_OUTPUT_VALIDATION(
     I     myIter, bi, bj, myThid )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE KPP_OUTPUT_VALIDATION                         |
C     | o Output KPP inputs and outputs for Python validation    |
C     *==========================================================*
C     | Outputs CSV-formatted data to STDOUT with E25.16         |
C     | precision to enable rtol=1e-12 validation testing        |
C     *==========================================================*
C \ev

C !USES:
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "DYNVARS.h"
#include "KPP.h"
#include "GRID.h"
#include "FFIELDS.h"

C !INPUT PARAMETERS:
      INTEGER myIter
      INTEGER bi, bj
      INTEGER myThid

C !LOCAL VARIABLES:
      INTEGER i, j, k
      INTEGER iMin, iMax, jMin, jMax
      PARAMETER(iMin=1, iMax=sNx, jMin=1, jMax=sNy)
CEOP

C     Only thread 1 writes (avoid duplicate output)
      IF ( myThid .NE. 1 ) RETURN

C     Debug: Test if output is working at all
      WRITE(6,'(A,I10,A,I3)')
     & 'DEBUG: KPP_OUTPUT_VALIDATION, myIter=',myIter,' myThid=',myThid

C     Output grid geometry once (first timestep only)
      IF ( myIter .EQ. 1 ) THEN
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_GRID_GEOMETRY ====='
       DO k = 1, Nr
        WRITE(standardMessageUnit,101) 'GRID_GEOM',k,
     &    drF(k), rF(k), rC(k)
       ENDDO
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_GRID_GEOMETRY_END ====='
      ENDIF

C     Output header for this timestep
      WRITE(standardMessageUnit,'(A)')
     &  '===== KPP_VALIDATION_START ====='
      WRITE(standardMessageUnit,'(A,I10,A,I3,A,I3)')
     &  'TIMESTEP=',myIter,',BI=',bi,',BJ=',bj

C     Loop over all grid points and output data
      DO j = jMin, jMax
       DO i = iMin, iMax

C       --- OUTPUT INPUTS ---
C       Grid and state variables (cell centers)
        DO k = 1, Nr
C        Format: INPUT_STATE,i,j,k,theta,salt,uvel,vvel
         WRITE(standardMessageUnit,100) 'INPUT_STATE',i,j,k,
     &     theta(i,j,k,bi,bj),
     &     salt(i,j,k,bi,bj),
     &     uVel(i,j,k,bi,bj),
     &     vVel(i,j,k,bi,bj)
        ENDDO

C       Surface forcing (scalar per column)
C       Format: INPUT_FORCING,i,j,tau_x,tau_y,q_net,q_sw,fw_flux
        WRITE(standardMessageUnit,102) 'INPUT_FORCING',i,j,
     &    surfaceForcingU(i,j,bi,bj),
     &    surfaceForcingV(i,j,bi,bj),
     &    surfaceForcingT(i,j,bi,bj),
     &    Qsw(i,j,bi,bj),
     &    EmPmR(i,j,bi,bj)

C       Coriolis parameter
        WRITE(standardMessageUnit,103) 'INPUT_CORIOLIS',i,j,
     &    fCori(i,j,bi,bj)

C       --- OUTPUT OUTPUTS ---
C       KPP mixing coefficients (at interfaces, k=1..Nr)
        DO k = 1, Nr
C        Format: OUTPUT_MIXING,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat
         WRITE(standardMessageUnit,104) 'OUTPUT_MIXING',i,j,k,
     &     KPPviscAz(i,j,k,bi,bj),
     &     KPPdiffKzS(i,j,k,bi,bj),
     &     KPPdiffKzT(i,j,k,bi,bj),
     &     KPPghat(i,j,k,bi,bj)
        ENDDO

C       Boundary layer depth (scalar per column)
        WRITE(standardMessageUnit,105) 'OUTPUT_HBL',i,j,
     &    KPPhbl(i,j,bi,bj)

       ENDDO
      ENDDO

C     Output footer for this timestep
      WRITE(standardMessageUnit,'(A)')
     &  '===== KPP_VALIDATION_END ====='

C     Format specifications (E25.16 for high precision)
 100  FORMAT(A,3(',',I3),4(',',E25.16))
 101  FORMAT(A,',',I3,3(',',E25.16))
 102  FORMAT(A,2(',',I3),5(',',E25.16))
 103  FORMAT(A,2(',',I3),',',E25.16)
 104  FORMAT(A,3(',',I3),4(',',E25.16))
 105  FORMAT(A,2(',',I3),',',E25.16)

      RETURN
      END
