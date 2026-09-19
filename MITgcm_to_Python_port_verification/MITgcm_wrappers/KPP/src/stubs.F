C $Header$
C $Name$

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: STUBS
C
C !DESCRIPTION: \bv
C     *==========================================================*
C     | STUBS.F                                                  |
C     | o Stub implementations of MITgcm routines not needed    |
C     |   for standalone KPP wrapper                            |
C     *==========================================================*
C     | These are minimal no-op implementations to satisfy      |
C     | linker requirements. They should never be called.       |
C     *==========================================================*
C \ev
CEOP

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|

      SUBROUTINE EXCH_XY_RL( array, myThid )
C     Stub for horizontal exchange (not needed in 1D)
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
      _RL array(1-OLx:sNx+OLx,1-OLy:sNy+OLy,nSx,nSy)
      INTEGER myThid
      RETURN
      END

      SUBROUTINE EXCH_XY_RS( array, myThid )
C     Stub for horizontal exchange (not needed in 1D)
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
      _RS array(1-OLx:sNx+OLx,1-OLy:sNy+OLy,nSx,nSy)
      INTEGER myThid
      RETURN
      END

      SUBROUTINE EXCH_XYZ_RL( array, myThid )
C     Stub for 3D horizontal exchange (not needed in 1D)
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
      _RL array(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr,nSx,nSy)
      INTEGER myThid
      RETURN
      END

      SUBROUTINE EXCH_XYZ_RS( array, myThid )
C     Stub for 3D horizontal exchange (not needed in 1D)
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
      _RS array(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr,nSx,nSy)
      INTEGER myThid
      RETURN
      END

      SUBROUTINE STOP_IF_ERROR( myThid )
C     Stub for error checking
      IMPLICIT NONE
      INTEGER myThid
      RETURN
      END

      SUBROUTINE WRITE_FLD_XYZ_RL( fn, var, irec, it, mt )
C     Stub for NetCDF output (not used)
      IMPLICIT NONE
      CHARACTER*(*) fn
#include "SIZE.h"
#include "EEPARAMS.h"
      _RL var(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr,nSx,nSy)
      INTEGER irec, it, mt
      RETURN
      END

      SUBROUTINE MDS_WRITE_FIELD( fn, prec, lg, ar, kt, it, mt )
C     Stub for MDS output (not used)
      IMPLICIT NONE
      CHARACTER*(*) fn
      INTEGER prec
      LOGICAL lg
#include "SIZE.h"
#include "EEPARAMS.h"
      _RL ar(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr,nSx,nSy)
      INTEGER kt, it, mt
      RETURN
      END

      SUBROUTINE GLOBAL_MAX_R8( val, mt )
C     Stub for global reduction (single process, no-op)
      IMPLICIT NONE
      REAL*8 val
      INTEGER mt
      RETURN
      END

      SUBROUTINE GLOBAL_MIN_R8( val, mt )
C     Stub for global reduction (single process, no-op)
      IMPLICIT NONE
      REAL*8 val
      INTEGER mt
      RETURN
      END

      SUBROUTINE GLOBAL_SUM_R8( val, mt )
C     Stub for global reduction (single process, no-op)
      IMPLICIT NONE
      REAL*8 val
      INTEGER mt
      RETURN
      END

      SUBROUTINE BARRIER( myThid )
C     Stub for thread barrier (single thread, no-op)
      IMPLICIT NONE
      INTEGER myThid
      RETURN
      END

      SUBROUTINE CALC_3D_DIFFUSIVITY(
     I     bi, bj, iMin, iMax, jMin, jMax,
     I     K, kappaRk,
     U     KappaRTk, KappaRSk,
     I     myThid )
C     Stub for generic diffusivity calculation (not needed for KPP)
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
      INTEGER bi, bj, iMin, iMax, jMin, jMax, K, myThid
      _RL kappaRk(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      _RL KappaRTk(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      _RL KappaRSk(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      RETURN
      END

      LOGICAL FUNCTION DIFFERENT_MULTIPLE( val1, val2, myTime )
C     Stub for time interval check (always false for single timestep)
      IMPLICIT NONE
      REAL*8 val1, val2, myTime
      DIFFERENT_MULTIPLE = .FALSE.
      RETURN
      END

C     PRESSURE_FOR_EOS removed - using real version from MITgcm

      SUBROUTINE PRINT_ERROR( msgBuf, myThid )
C     Stub for error printing
      IMPLICIT NONE
#include "EEPARAMS.h"
      CHARACTER*(*) msgBuf
      INTEGER myThid
      WRITE(6,'(A)') 'ERROR: ' // msgBuf
      RETURN
      END

      SUBROUTINE PRINT_MESSAGE( msgBuf, ioUnit, sq, myThid )
C     Stub for message printing
      IMPLICIT NONE
      CHARACTER*(*) msgBuf
      CHARACTER*(*) sq
      INTEGER ioUnit, myThid
C     Simple print to stdout, ignore squeezing
      WRITE(6,'(A)') msgBuf
      RETURN
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|

      SUBROUTINE OPEN_COPY_DATA_FILE(fname, routine, iounit, mythid)
C     Stub for opening data files
      IMPLICIT NONE
#include "EEPARAMS.h"
      CHARACTER*(*) fname, routine
      INTEGER iounit, mythid
C     For wrapper: just use default parameters, don't require file
C     Set iounit to invalid value to signal file not found (triggers defaults)
      iounit = -1
      RETURN
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|

      SUBROUTINE ALL_PROC_DIE(myThid)
C     Stub for fatal error handling
      IMPLICIT NONE
      INTEGER myThid
C     In 1D wrapper, just stop
      STOP 'FATAL ERROR in KPP'
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|

      INTEGER FUNCTION ILNBLNK(string)
C     Returns index of last non-blank character in string
      IMPLICIT NONE
      CHARACTER*(*) string
      INTEGER i
      DO i = LEN(string), 1, -1
       IF (string(i:i) .NE. ' ') THEN
        ILNBLNK = i
        RETURN
       ENDIF
      ENDDO
      ILNBLNK = 0
      RETURN
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|

      SUBROUTINE PACKAGES_UNUSED_MSG(pkgname, msg1, msg2)
C     Stub for package warning messages
      IMPLICIT NONE
      CHARACTER*(*) pkgname, msg1, msg2
C     No-op in wrapper
      RETURN
      END
