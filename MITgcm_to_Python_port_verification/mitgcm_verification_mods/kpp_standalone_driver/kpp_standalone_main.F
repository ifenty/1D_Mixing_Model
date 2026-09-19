#include "KPP_OPTIONS.h"

C--   Standalone KPPMIX driver: compiles and calls KPPMIX directly, with
C--   no full MITgcm model, no tiling/exchange machinery, and no MPI.
C--
C--   KPPMIX (kpp_routines.F) takes all physics inputs/outputs as
C--   arguments and only reads scalar/lookup-table parameters via
C--   KPP_PARAMS.h -- it never touches DYNVARS.h/GRID.h/FFIELDS.h. This
C--   driver populates KPP_PARAMS.h's common block by hand from values
C--   captured from a real instrumented full-model run (see
C--   scripts/export_kpp_input_for_fortran.py), then calls KPPMIX once
C--   per captured timestep, replaying the exact same inputs the full
C--   model used. Output is written in the same instrumented text
C--   format kpp_calc.F's KPP_OUTPUT_VALIDATION already produces, so
C--   scripts/parse_mitgcm_split.py consumes it unmodified.
C--
C--   Uses SIZE.h in this directory (imt=1: single column, OLx=OLy=0),
C--   NOT the real experiment's SIZE.h (which has OLx=OLy=3 for
C--   halo/exchange -- irrelevant here).

      PROGRAM KPP_STANDALONE_MAIN

      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "KPP_PARAMS.h"

C     KPPMIX arguments (imt=1: one real column, no halo padding)
      INTEGER kmtj(imt)
      _RL     shsq(imt,Nr)
      _RL     dVsq(imt,Nr)
      _RL     ustarArr(imt)
      _RL     boArr(imt)
      _RL     bosolArr(imt)
      _RL     dbloc(imt,Nr)
      _RL     Ritop(imt,Nr)
      _RS     coriolArr(imt)
      _RS     swattArr(imt,Nr+1)
      _RS     mskArr(imt)
      _RL     diffusKzS(imt,Nr)
      _RL     diffusKzT(imt,Nr)
      INTEGER ikeyArr
      _RL     diffus(imt,0:Nrp1,mdiff)
      _RL     ghat(imt,Nr)
      _RL     hbl(imt)
C     kbl: KPPMIX's signature includes this (#ifdef SHORTWAVE_HEATING)
C     output whenever SHORTWAVE_HEATING is active, as it is here --
C     omitting it is a positional-argument-count mismatch that
C     silently corrupts memory (no interface checking across
C     separately-compiled F77-style units).
      INTEGER kbl(imt)

C     Driver bookkeeping
      INTEGER ntimeIn, nrIn, narg
      INTEGER k, ti, myIter
      _RL     myTime
      INTEGER bi, bj, myThid
      CHARACTER*256 infile, outfile

      _RL     drFVal(Nr), rCVal(Nr)
      _RL     viscAzVal, diffKzSVal, diffKzTVal
      INTEGER kppUseDoubleDiffInt, limitHblStableInt
      INTEGER kppUseSWfrac3DInt
      _RL     p33, zehat, usta, zeta
      INTEGER ii, jj

      narg = IARGC()
      IF (narg .LT. 2) THEN
        WRITE(6,'(A)')
     &    'Usage: kpp_standalone_main <input.txt> <output.txt>'
        STOP 1
      ENDIF
      CALL GETARG(1, infile)
      CALL GETARG(2, outfile)

      bi = 1
      bj = 1
      myThid = 1
      ikeyArr = 0

      OPEN(UNIT=10, FILE=infile, STATUS='OLD')
      OPEN(UNIT=20, FILE=outfile, STATUS='UNKNOWN')

      READ(10,*) ntimeIn, nrIn
      IF (nrIn .NE. Nr) THEN
        WRITE(6,'(A,I5,A,I5)')
     &    'ERROR: input Nr=', nrIn, ' does not match SIZE.h Nr=', Nr
        STOP 1
      ENDIF

      DO k = 1, Nr
        READ(10,*) drFVal(k), rCVal(k)
      ENDDO

C     --- KPP_PARAMS.h scalar/common parameters, in the exact order
C         scripts/export_kpp_input_for_fortran.py writes them ---
      READ(10,*) Ricr
      READ(10,*) cekman
      READ(10,*) cmonob
      READ(10,*) concv
      READ(10,*) hbf
      READ(10,*) epsilon
      READ(10,*) vonk
      READ(10,*) dB_dz
      READ(10,*) Riinfty
      READ(10,*) BVSQcon
      READ(10,*) difm0
      READ(10,*) difs0
      READ(10,*) dift0
      READ(10,*) difmcon
      READ(10,*) difscon
      READ(10,*) diftcon
      READ(10,*) conc1
      READ(10,*) conam
      READ(10,*) concm
      READ(10,*) conc2
      READ(10,*) zetam
      READ(10,*) conas
      READ(10,*) concs
      READ(10,*) conc3
      READ(10,*) zetas
      READ(10,*) Rrho0
      READ(10,*) dsfmax
      READ(10,*) epsln
      READ(10,*) phepsi
      READ(10,*) cstar
      READ(10,*) minKPPhbl
      READ(10,*) zmin
      READ(10,*) zmax
      READ(10,*) umin
      READ(10,*) umax
      READ(10,*) viscAzVal
      READ(10,*) diffKzSVal
      READ(10,*) diffKzTVal
      READ(10,*) num_v_smooth_Ri
      READ(10,*) selectPenetratingSW
      READ(10,*) kppUseDoubleDiffInt
      READ(10,*) limitHblStableInt
      READ(10,*) kppUseSWfrac3DInt
      LimitHblStable = (limitHblStableInt .NE. 0)
      KPPuseSWfrac3D = (kppUseSWfrac3DInt .NE. 0)

C     --- derived KPP_PARAMS.h quantities, exact formulas from
C         kpp_init_fixed.F (Vtc, cg, wm/ws table, zgrid/hwide) ---
      p33 = 1. _d 0 / 3. _d 0
      Vtc = concv * SQRT(0.2 _d 0/concs/epsilon) / vonk**2 / Ricr
      cg  = cstar * vonk * (concs*vonk*epsilon)**p33

      deltaz = (zmax - zmin) / DBLE(nni+1)
      deltau = (umax - umin) / DBLE(nnj+1)
      DO ii = 0, nni+1
        zehat = deltaz*ii + zmin
        DO jj = 0, nnj+1
          usta = deltau*jj + umin
          zeta = zehat / MAX(phepsi, usta**3)
          IF (zehat .GE. 0. _d 0) THEN
            wmt(ii,jj) = vonk*usta/(1. _d 0 + conc1*zeta)
            wst(ii,jj) = wmt(ii,jj)
          ELSE
            IF (zeta .GT. zetam) THEN
              wmt(ii,jj) = vonk*usta*(1. _d 0-conc2*zeta)**0.25 _d 0
            ELSE
              wmt(ii,jj) = vonk*(conam*usta**3-concm*zehat)**p33
            ENDIF
            IF (zeta .GT. zetas) THEN
              wst(ii,jj) = vonk*usta*SQRT(1. _d 0 - conc3*zeta)
            ELSE
              wst(ii,jj) = vonk*(conas*usta**3-concs*zehat)**p33
            ENDIF
          ENDIF
        ENDDO
      ENDDO

      zgrid(0) = phepsi
      hwide(0) = phepsi
      DO k = 1, Nr
        zgrid(k) = rCVal(k)
        hwide(k) = drFVal(k)
      ENDDO
      zgrid(Nrp1) = zgrid(Nr) * 100. _d 0
      hwide(Nrp1) = phepsi

C     --- PARAMS.h common: Ri_iwmix reads viscArNr(1) directly (not an
C         explicit KPPMIX argument) ---
      DO k = 1, Nr
        viscArNr(k) = viscAzVal
      ENDDO

C     --- fixed per-column setup: imt=1, one real (non-halo) column ---
      kmtj(1) = Nr
      mskArr(1) = 1.0
      DO k = 1, Nr
        diffusKzS(1,k) = diffKzSVal
        diffusKzT(1,k) = diffKzTVal
      ENDDO

C     --- output header, matching kpp_calc.F's instrumented format so
C         parse_mitgcm_split.py consumes it unmodified ---
      WRITE(20,'(A)') '===== KPP_DATA_HEADERS ====='
      WRITE(20,'(A)')
     &  'OUTPUT_MIXING_HEADER,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat'
      WRITE(20,'(A)') 'OUTPUT_HBL_HEADER,i,j,hbl'
      WRITE(20,'(A)') '===== KPP_DATA_HEADERS_END ====='

      DO ti = 1, ntimeIn
        READ(10,*) myIter
        READ(10,*) ustarArr(1), boArr(1), bosolArr(1), coriolArr(1)
        DO k = 1, Nr
          READ(10,*) shsq(1,k), dVsq(1,k), dbloc(1,k), Ritop(1,k)
        ENDDO
        DO k = 1, Nr+1
          READ(10,*) swattArr(1,k)
        ENDDO

C       ghat is a "U" (update) KPPMIX argument: internally it is the
C       (horizontally-smoothed) dbloc used by Ri_iwmix, and the real
C       caller (kpp_calc.F) initializes it to dbloc before the call
C       (then applies KPP_SMOOTH_DBLOC, a horizontal smooth across
C       neighboring tile columns -- a no-op here, since this is a
C       genuinely isolated single column with no lateral neighbors).
C       Leaving it uninitialized silently zeros the Richardson-number
C       shear term and forces maximal shear-mixing at every level.
        DO k = 1, Nr
          ghat(1,k) = dbloc(1,k)
        ENDDO

C       myTime is only used by KPPMIX's SWFRAC fallback, which is
C       bypassed whenever KPPuseSWfrac3D is true (as it is here) --
C       any finite value is safe.
        myTime = DBLE(myIter)

        CALL KPPMIX (
     I       kmtj, shsq, dVsq, ustarArr, mskArr,
     I       boArr, bosolArr,
     I       dbloc, Ritop, coriolArr,
     I       swattArr,
     I       diffusKzS, diffusKzT,
     I       ikeyArr,
     O       diffus,
     U       ghat,
     O       hbl,
     O       kbl,
     I       bi, bj, myTime, myIter, myThid )

        WRITE(20,'(A)') '===== KPP_VALIDATION_START ====='
        WRITE(20,'(A,I10,A,I3,A,I3)') 'TIMESTEP=',myIter,',BI=',bi,
     &    ',BJ=',bj
        DO k = 1, Nr
          WRITE(20,204) 'OUTPUT_MIXING',1,1,k,
     &      diffus(1,k-1,1), diffus(1,k-1,2), diffus(1,k-1,3),
     &      ghat(1,k)
        ENDDO
        WRITE(20,205) 'OUTPUT_HBL',1,1,hbl(1)
        WRITE(20,'(A)') '===== KPP_VALIDATION_END ====='
      ENDDO

      CLOSE(10)
      CLOSE(20)

 204  FORMAT(A,3(',',I3),4(',',E25.16))
 205  FORMAT(A,2(',',I3),',',E25.16)

      STOP
      END

C--   Link-only stubs: kpp_routines.F contains other subroutines in
C--   the same file (STATEKPP, bldepth's SWFRAC fallback) that this
C--   driver never calls -- KPPuseSWfrac3D=.TRUE. bypasses SWFRAC, and
C--   STATEKPP/KPP_DOUBLEDIFF are not invoked at all, since their
C--   outputs are already in the captured input. But the linker still
C--   needs every external symbol *referenced* anywhere in the object
C--   file to resolve, even in dead code. These bodies never execute.
      SUBROUTINE SWFRAC
      RETURN
      END

      SUBROUTINE FIND_RHO_2D
      RETURN
      END

      SUBROUTINE FIND_ALPHA
      RETURN
      END

      SUBROUTINE FIND_BETA
      RETURN
      END
