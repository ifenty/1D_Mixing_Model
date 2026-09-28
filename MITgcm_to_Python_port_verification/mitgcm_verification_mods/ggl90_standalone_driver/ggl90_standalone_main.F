#include "GGL90_OPTIONS.h"

C--   Standalone GGL90_CALC driver: compiles and calls the real, unmodified
C--   GGL90_CALC directly, with no full MITgcm model, no tiling/exchange
C--   machinery, and no MPI. Mirrors kpp_standalone_driver/kpp_standalone_main.F's
C--   build/output-format/comparison pattern (1DMIX-024); see that file's own
C--   header comment for the precedent this driver follows as closely as the
C--   two schemes' structural differences allow.
C--
C--   Structural difference from KPPMIX (read before editing): KPPMIX takes
C--   every physics input as an explicit argument. GGL90_CALC(bi, bj, sigmaR,
C--   myTime, myIter, myThid) has almost no explicit arguments -- it reads/
C--   writes DYNVARS.h (uVel,vVel), FFIELDS.h (surfaceForcingU/V), GRID.h
C--   (maskC,hFacC,drC,drF,rF,rC,recip_*), GGL90.h (GGL90TKE -- prognostic,
C--   both input AND output), and PARAMS.h scalars, all via COMMON blocks
C--   populated by hand below from a real captured vermix full-model
C--   trajectory (scripts/export_vermix_capture_to_ggl90_driver.py).
C--
C--   GGL90mixingLength and the correct floored viscosity (GGL90viscOutput,
C--   the 1DMIX-016 ground-truth column) are call-local scratch variables
C--   inside GGL90_CALC with no COMMON-block export path -- unlike KPP's
C--   driver, which writes its own output blocks directly after the call,
C--   this driver instead compiles the SAME already-instrumented
C--   ggl90_calc.F used by the real vermix full-model build (identical
C--   physics; the instrumentation only adds captures, confirmed bit-
C--   identical against the pre-sigmaR full-model capture, see 1DMIX-024's
C--   open_issues.md entry) and simply redirects its embedded
C--   GGL90_OUTPUT_VALIDATION call's WRITE target (standardMessageUnit,
C--   an ordinary EEPARAMS.h COMMON INTEGER, uninitialized without a real
C--   eeboot) to this driver's own opened output unit. GGL90_CALC then
C--   writes its own MODEL_PARAMETERS/GRID_GEOMETRY/DATA_HEADERS/
C--   VALIDATION blocks in exactly the format scripts/parse_mitgcm_ggl90_split.py
C--   already parses -- no separate output-writing code needed here.
C--
C--   Uses SIZE.h with sNx=sNy=1, OLx=OLy=2 (originally copied once from
C--   vermix's real code_validation/SIZE.h, Nr=26) -- NOT a minimal
C--   OLx=OLy=0 SIZE.h like KPP's driver, because GGL90_CALC's loop bounds
C--   (iMin=2-OLx, iMax=sNx+OLx-1) and every array's declared halo are
C--   parameterized directly from SIZE.h; reusing the real OLx=OLy=2
C--   removes a whole class of bugs. UPDATE (1DMIX-024 scenario-extension
C--   follow-up): build_and_run.sh now auto-regenerates SIZE.h's Nr (like
C--   KPP's driver already did) from each input file's own header, since
C--   the 6 idealized Python-port scenarios use varying grid sizes
C--   (Nr=23..50) unlike vermix's fixed Nr=26 -- OLx=OLy=2/sNx=sNy=1 are
C--   preserved unchanged in the regenerated file, only Nr varies.

      PROGRAM GGL90_STANDALONE_MAIN

      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "DYNVARS.h"
#include "FFIELDS.h"
#include "GRID.h"
#include "GGL90.h"

C     Driver bookkeeping
      INTEGER ntimeIn, nrIn, narg
      INTEGER k, ti, myIter, i, j
      _RL     myTime
      INTEGER bi, bj, myThid
      CHARACTER*256 infile, outfile

      _RL     drFVal(Nr), rFVal(Nr), rCVal(Nr)
      _RL     paramDeltaT, paramViscAz, paramDiffKzS
      INTEGER dirichletInt, meanShearInt

      _RL     thetaCol(Nr), saltCol(Nr), uCol(Nr), vCol(Nr)
      _RL     tkeCol(Nr), sigmaRCol(Nr)
      _RL     tauX, tauY, uStarSqCapture

C     GGL90_CALC's one explicit array argument (vertical gradient of
C     iso-neutral density); captured directly from the real Fortran
C     (1DMIX-024's INPUT_SIGMAR addition), not derived in Python, since
C     this run uses eosType='MDJWF' and the Python port only implements
C     JMD95 (see open_issues.md 1DMIX-024).
      _RL     sigmaR(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)

      narg = IARGC()
      IF (narg .LT. 2) THEN
        WRITE(6,'(A)')
     &    'Usage: ggl90_standalone_main <input.txt> <output.txt>'
        STOP 1
      ENDIF
      CALL GETARG(1, infile)
      CALL GETARG(2, outfile)

      bi = 1
      bj = 1
      myThid = 1

      OPEN(UNIT=10, FILE=infile, STATUS='OLD')
      OPEN(UNIT=20, FILE=outfile, STATUS='UNKNOWN')

C     Redirect GGL90_CALC's own embedded GGL90_OUTPUT_VALIDATION dump to
C     this driver's own opened unit (see header comment above).
      standardMessageUnit = 20

      READ(10,*) ntimeIn, nrIn
      IF (nrIn .NE. Nr) THEN
        WRITE(6,'(A,I5,A,I5)')
     &    'ERROR: input Nr=', nrIn, ' does not match SIZE.h Nr=', Nr
        STOP 1
      ENDIF

      DO k = 1, Nr
        READ(10,*) drFVal(k), rFVal(k), rCVal(k)
      ENDDO

C     --- GGL90.h/PARAMS.h scalar parameters, in the exact order
C         scripts/export_vermix_capture_to_ggl90_driver.py writes them ---
      READ(10,*) GGL90ck
      READ(10,*) GGL90ceps
      READ(10,*) GGL90alpha
      READ(10,*) GGL90m2
      READ(10,*) GGL90TKEmin
      READ(10,*) GGL90TKEsurfMin
      READ(10,*) GGL90TKEbottom
      READ(10,*) GGL90mixingLengthMin
      READ(10,*) GGL90viscMax
      READ(10,*) GGL90diffMax
      READ(10,*) gravity
      READ(10,*) rhoConst
      READ(10,*) paramViscAz
      READ(10,*) paramDiffKzS
      READ(10,*) paramDeltaT
      READ(10,*) mxlMaxFlag
      READ(10,*) dirichletInt
      READ(10,*) meanShearInt
      GGL90_dirichlet = (dirichletInt .NE. 0)
      calcMeanVertShear = (meanShearInt .NE. 0)

      recip_rhoConst = 1. _d 0 / rhoConst

      DO k = 1, Nr
        viscArNr(k) = paramViscAz
        diffKrNrS(k) = paramDiffKzS
        dTtracerLev(k) = paramDeltaT
        drF(k) = drFVal(k)
        rF(k) = rFVal(k)
        rC(k) = rCVal(k)
        recip_drF(k) = 1. _d 0 / drF(k)
      ENDDO
C     rF(Nr+1) is never read by GGL90_CALC/GGL90_MIXINGLENGTH for this
C     configuration (mxlMaxFlag=3, usingPCoords=.FALSE., useLANGMUIR=
C     .FALSE. -- confirmed by reading every rF(k) reference in both
C     files), but is filled in for hygiene via the same rF(k+1)=
C     rF(k)+rkSign*drF(k) relation ini_vertical_grid.F uses (rkSign=-1
C     for z-coordinates).
      rF(Nr+1) = rF(Nr) - drF(Nr)

C     drC(k) for k=2..Nr, derived from the captured rC per
C     model/src/ini_vertical_grid.F's z-coordinate relation
C     rC(k) = rC(k-1) + rkSign*drC(k) with rkSign=-1, i.e.
C     drC(k) = rC(k-1) - rC(k). drC(1) and drC(Nr+1) are never read by
C     GGL90_CALC for this iMin..iMax=2..Nr loop range (confirmed by
C     grep) and are deliberately left unset rather than guessed.
      DO k = 2, Nr
        drC(k) = rCVal(k-1) - rCVal(k)
        recip_drC(k) = 1. _d 0 / drC(k)
      ENDDO

C     --- fixed per-column setup: replicate the single real column into
C     every halo position over the FULL declared array extent
C     (1-OLx..sNx+OLx, 1-OLy..sNy+OLy), not just the iMin..iMax
C     computational ring -- some GGL90_CALC init loops (e.g.
C     recip_hFacI) touch the full declared range. A physically-correct
C     zero-lateral-gradient idealization for a genuinely isolated
C     column, matching kpp_standalone_main.F's own established
C     technique for ghat/dbloc. hFacC=1, maskC=1 everywhere: vermix is
C     a synthetic single-column setup with no bathyFile (default flat
C     bottom at the full grid depth) -- confirmed by reading
C     input_ggl90_merged/data (no bathyFile entry). ---
C     Ro_surf/R_low (GRID.h 2-D fields): the surface reference position and
C     bottom-of-fluid position used by GGL90_MIXINGLENGTH's mxlMaxFlag=0
C     ("simple depth limit", MaxLength=Ro_surf-R_low) and mxlMaxFlag=1
C     limiters (ggl90_mixinglength.F:163-193) -- UNUSED by vermix (which
C     runs mxlMaxFlag=3, the two-way-sweep branch that never reads either
C     field) but REQUIRED for the idealized-scenario extension (1DMIX-024
C     follow-up), whose Python port uses GGL90Parameters' own default
C     mxl_max_flag=0. Left uninitialized, these COMMON fields are whatever
C     the linker's zero-filled .bss gives (0.0 for both), which would make
C     MaxLength=0-0=0 and clamp GGL90mixingLength to exactly zero at every
C     level -- a real, silent, near-certain bug for this configuration if
C     omitted (not merely a latent one), caught by reading
C     ggl90_mixinglength.F's flag=0 branch line-by-line before running.
C     Values match MITgcm's own default (no bathyFile/topoFile) case,
C     model/src/ini_depths.F:91-102 (R_low=rF(Nr+1)) and :155-166
C     (Ro_surf=rF(1)) -- confirmed by reading ini_depths.F directly, not
C     assumed. rF(1) and rF(Nr+1) are already set above (rF(1) read from
C     input; rF(Nr+1)=rF(Nr)-drF(Nr) a few lines up).
      DO j = 1-OLy, sNy+OLy
       DO i = 1-OLx, sNx+OLx
        kLowC(i,j,bi,bj) = Nr
        Ro_surf(i,j,bi,bj) = rF(1)
        R_low(i,j,bi,bj) = rF(Nr+1)
        DO k = 1, Nr
         maskC(i,j,k,bi,bj) = 1. _d 0
         hFacC(i,j,k,bi,bj) = 1. _d 0
         recip_hFacC(i,j,k,bi,bj) = 1. _d 0
        ENDDO
       ENDDO
      ENDDO

      usingPCoords = .FALSE.
      usingZCoords = .TRUE.
C     gravitySign = -1 for z-coordinates (model/src/ini_parms.F:53-57;
C     usingPCoords=.FALSE. here, so it never gets the p-coords override
C     to +1). Not vermix-specific; a universal MITgcm z-coordinate
C     constant, safe to hardcode with this citation.
      gravitySign = -1. _d 0
C     useDiagnostics=.FALSE.: verified by reading every ALLOW_DIAGNOSTICS-
C     guarded block in ggl90_calc.F -- each either archives an already-
C     finalized physics array for later output, or (the one exception,
C     'GGL90KN2') overwrites a call-local scratch variable never read
C     again within the call. Zero effect on GGL90TKE/GGL90diffKr/the
C     validation dump either way; avoids needing the diagnostics
C     package's own runtime initialization here.
      useDiagnostics = .FALSE.
C     useLANGMUIR default is .FALSE. (pkg/ggl90/ggl90_readparms.F:128)
C     and not set in vermix's data.ggl90 -- confirmed, not assumed.
      useLANGMUIR = .FALSE.
C     mxlSurfFlag default is .FALSE. (GGL90.h's own doc comment,
C     confirmed against pkg/ggl90/ggl90_readparms.F:123) and not set in
C     vermix's data.ggl90.
      mxlSurfFlag = .FALSE.

      DO ti = 1, ntimeIn
        READ(10,*) myIter
        READ(10,*) tauX, tauY, uStarSqCapture
        DO k = 1, Nr
          READ(10,*) thetaCol(k), saltCol(k), uCol(k), vCol(k)
        ENDDO
        DO k = 1, Nr
          READ(10,*) tkeCol(k)
        ENDDO
        DO k = 1, Nr
          READ(10,*) sigmaRCol(k)
        ENDDO

C       Replicate this timestep's single real column into every halo
C       position (see the fixed per-column setup comment above).
C       GGL90TKE is prognostic (both input AND output): this OVERWRITES
C       it at the *start* of every timestep's call with the full
C       model's own captured tke_before, since this is an exact
C       per-timestep replay against the full model's own trajectory,
C       not letting TKE evolve independently under the driver's own
C       (potentially drifting) state.
        DO j = 1-OLy, sNy+OLy
         DO i = 1-OLx, sNx+OLx
          surfaceForcingU(i,j,bi,bj) = tauX
          surfaceForcingV(i,j,bi,bj) = tauY
          DO k = 1, Nr
           theta(i,j,k,bi,bj) = thetaCol(k)
           salt(i,j,k,bi,bj)  = saltCol(k)
           uVel(i,j,k,bi,bj)  = uCol(k)
           vVel(i,j,k,bi,bj)  = vCol(k)
           GGL90TKE(i,j,k,bi,bj) = tkeCol(k)
           sigmaR(i,j,k) = sigmaRCol(k)
          ENDDO
         ENDDO
        ENDDO

C       myTime is never actually read inside GGL90_CALC or
C       GGL90_MIXINGLENGTH (confirmed by grep -- passed through only,
C       exactly like KPPMIX's own myTime argument in the KPP driver);
C       any finite value is safe.
        myTime = DBLE(myIter) * paramDeltaT

        CALL GGL90_CALC( bi, bj, sigmaR, myTime, myIter, myThid )

      ENDDO

      CLOSE(10)
      CLOSE(20)

      STOP
      END

C--   Link-only stubs: dead-code paths never executed for this
C--   configuration but still referenced by the compiled object code --
C--   Fortran requires every external symbol referenced anywhere in a
C--   compiled unit to resolve at link time, even inside an unreachable
C--   branch (no interface checking across separately-compiled F77-style
C--   units) -- exactly mirroring kpp_standalone_main.F's own stub
C--   section (SWFRAC, FIND_RHO_2D, FIND_ALPHA, FIND_BETA there).
C--     DIAGNOSTICS_IS_ON/_COUNT/_FILL: referenced inside
C--       `IF (useDiagnostics)` blocks in ggl90_calc.F; useDiagnostics is
C--       set .FALSE. above, so these are never actually called here.
C--     PRINT_ERROR: referenced in ggl90_mixinglength.F's
C--       mxlMaxFlag-not-implemented / Langmuir-not-implemented error
C--       branches, both unreachable for mxlMaxFlag=3, useLANGMUIR=.FALSE.
      LOGICAL FUNCTION DIAGNOSTICS_IS_ON( name, myThid )
      IMPLICIT NONE
      CHARACTER*(*) name
      INTEGER myThid
      DIAGNOSTICS_IS_ON = .FALSE.
      RETURN
      END

      SUBROUTINE DIAGNOSTICS_COUNT( name, bi, bj, myThid )
      IMPLICIT NONE
      CHARACTER*(*) name
      INTEGER bi, bj, myThid
      RETURN
      END

      SUBROUTINE DIAGNOSTICS_FILL( fld, name, kLo, kHi, iSlot,
     &                              bi, bj, myThid )
      IMPLICIT NONE
      CHARACTER*(*) name
      INTEGER kLo, kHi, iSlot, bi, bj, myThid
      Real*8 fld(*)
      RETURN
      END

      SUBROUTINE PRINT_ERROR( msg, myThid )
      IMPLICIT NONE
      CHARACTER*(*) msg
      INTEGER myThid
      RETURN
      END
