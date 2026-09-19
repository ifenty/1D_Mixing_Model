C $Header$
C $Name$

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: KPP_WRAPPER
C
C !INTERFACE:
      PROGRAM KPP_WRAPPER

C !DESCRIPTION: \bv
C     *==========================================================*
C     | PROGRAM KPP_WRAPPER                                      |
C     | o Standalone wrapper for MITgcm KPP package             |
C     *==========================================================*
C     | Reads binary input file prepared by prep_inputs.py,      |
C     | populates MITgcm common blocks, calls KPP routines,     |
C     | and outputs validation data via kpp_output_validation.F |
C     |                                                          |
C     | Usage: ./kpp_wrapper < input.bin                        |
C     |                                                          |
C     | Binary input format (big-endian):                        |
C     |   Nr (int32)                                            |
C     |   coriol (float64)                                      |
C     |   drF(Nr), rF(Nr+1), rC(Nr)                            |
C     |   theta(Nr), salt(Nr), uVel(Nr), vVel(Nr)              |
C     |   surfaceForcingU/V/T, Qsw, EmPmR (float64 scalars)    |
C     *==========================================================*
C \ev
CEOP

C !USES:
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PACKAGES_CONFIG.h"
#include "PARAMS.h"
#include "EOS.h"
#include "GRID.h"
#include "DYNVARS.h"
#include "FFIELDS.h"
#include "KPP.h"
#include "KPP_PARAMS.h"

C !LOCAL VARIABLES:
      INTEGER myThid, bi, bj, myIter
      INTEGER Nr_input
      INTEGER k
      REAL*8 coriol_input
      REAL*8 drF_input(Nr)
      REAL*8 rF_input(Nr+1)
      REAL*8 rC_input(Nr)
      REAL*8 theta_input(Nr)
      REAL*8 salt_input(Nr)
      REAL*8 uVel_input(Nr)
      REAL*8 vVel_input(Nr)
      REAL*8 surfForcU_input
      REAL*8 surfForcV_input
      REAL*8 surfForcT_input
      REAL*8 Qsw_input
      REAL*8 EmPmR_input

C     ================================================================
C     BEGIN EXECUTABLE CODE
C     ================================================================

      WRITE(6,*) 'KPP_WRAPPER: Starting standalone KPP wrapper'

C     -------------------------------------------
C     1. Initialize thread/tile parameters
C     -------------------------------------------
      myThid = 1
      bi = 1
      bj = 1
      myIter = 1

C     -------------------------------------------
C     2. Read binary input file
C     -------------------------------------------
      WRITE(6,*) 'KPP_WRAPPER: Reading binary input'

C     Open input file for stream (unformatted) access
C     File name passed as command line argument, or use 'input.bin' default
      OPEN(UNIT=5, FILE='input.bin', ACCESS='STREAM',
     &     FORM='UNFORMATTED', STATUS='OLD')

C     Read Nr (int32)
      READ(5) Nr_input
      WRITE(6,*) 'KPP_WRAPPER: Nr_input =', Nr_input

C     Validate Nr against SIZE.h
      IF (Nr_input .NE. Nr) THEN
       WRITE(6,*) 'ERROR: Input Nr=',Nr_input,' != SIZE.h Nr=',Nr
       STOP 'SIZE MISMATCH'
      ENDIF

C     Read scalar parameters
      READ(5) coriol_input

C     Read grid arrays
      READ(5) (drF_input(k), k=1,Nr)
      READ(5) (rF_input(k), k=1,Nr+1)
      READ(5) (rC_input(k), k=1,Nr)

C     Read state arrays
      READ(5) (theta_input(k), k=1,Nr)
      READ(5) (salt_input(k), k=1,Nr)
      READ(5) (uVel_input(k), k=1,Nr)
      READ(5) (vVel_input(k), k=1,Nr)

C     Read surface forcing scalars
      READ(5) surfForcU_input
      READ(5) surfForcV_input
      READ(5) surfForcT_input
      READ(5) Qsw_input
      READ(5) EmPmR_input

      WRITE(6,*) 'KPP_WRAPPER: Successfully read binary input'
      WRITE(6,*) '  coriol =', coriol_input
      WRITE(6,*) '  drF(1) =', drF_input(1), ' drF(Nr) =', drF_input(Nr)
      WRITE(6,*) '  rF(1) =', rF_input(1), ' rF(Nr+1) =', rF_input(Nr+1)
      WRITE(6,*) '  theta(1) =', theta_input(1)
      WRITE(6,*) '  surfForcT =', surfForcT_input
      WRITE(6,*) '  Qsw =', Qsw_input
      WRITE(6,*) '  EmPmR =', EmPmR_input

C     -------------------------------------------
C     3. Initialize grid (with defaults first)
C     -------------------------------------------
      CALL INI_WRAPPER_GRID( myThid )

C     Override with input values if provided
      CALL SET_WRAPPER_GRID( drF_input, rF_input, rC_input, myThid )

C     Set maskC and fCori here in wrapper (COMMON block visibility issue
C     prevents SET_WRAPPER_GRID from setting them correctly)
      DO k = 1, Nr
       maskC(1,1,k,bi,bj) = 1.0D0
      ENDDO
      fCori(1,1,bi,bj) = coriol_input

C     -------------------------------------------
C     4. Populate other MITgcm common blocks
C     -------------------------------------------
      WRITE(6,*) 'KPP_WRAPPER: Populating state and forcing'

C     Number of wet levels (KPP_PARAMS.h)
C     Set to Nr for full water column (1D case)
      nzmax(1,1,bi,bj) = Nr

C     State variables (DYNVARS.h)
      DO k = 1, Nr
       theta(1,1,k,bi,bj) = theta_input(k)
       salt(1,1,k,bi,bj) = salt_input(k)
       uVel(1,1,k,bi,bj) = uVel_input(k)
       vVel(1,1,k,bi,bj) = vVel_input(k)
      ENDDO

C     Surface forcing (FFIELDS.h)
      surfaceForcingU(1,1,bi,bj) = surfForcU_input
      surfaceForcingV(1,1,bi,bj) = surfForcV_input
      surfaceForcingT(1,1,bi,bj) = surfForcT_input
      Qsw(1,1,bi,bj) = Qsw_input
      EmPmR(1,1,bi,bj) = EmPmR_input

C     Physical parameters (PARAMS.h)
C     These should match physical_parameters.yaml defaults
      gravity = 9.81D0
      rhoConst = 1029.0D0
      HeatCapacity_Cp = 3994.0D0
      f0 = coriol_input

C     Background vertical viscosity/diffusivity (from physical_parameters.yaml)
      DO k = 1, Nr
       viscArNr(k) = 5.0D-5  ! 0.5e-4 m^2/s
       diffKrNrS(k) = 1.0D-5  ! 1.0e-5 m^2/s
       diffKrNrT(k) = 1.0D-5  ! 1.0e-5 m^2/s
      ENDDO

C     Equation of state (EOS.h) - CRITICAL for density calculations!
C     JMD95Z is the full nonlinear EOS used by Python port
      equationOfState = 'JMD95Z'
      eosType = 'JMD95Z'
      fluidIsWater = .TRUE.

C     Timestep parameters (dummy for single-step run)
      deltaT = 3600.0D0  ! 1 hour
      deltaTMom = 3600.0D0
      deltaTClock = 3600.0D0

C     Enable KPP package
      useKPP = .TRUE.

C     -------------------------------------------
C     5. Initialize EOS and KPP
C     -------------------------------------------
C     Initialize equation of state (sets JMD95 coefficients)
      WRITE(6,*) 'KPP_WRAPPER: Calling INI_EOS'
      CALL INI_EOS(myThid)

C     First read KPP parameters (sets defaults)
      WRITE(6,*) 'KPP_WRAPPER: Calling KPP_READPARMS'
      CALL KPP_READPARMS(myThid)

C     Then initialize fixed KPP arrays (lookup tables, etc.)
      WRITE(6,*) 'KPP_WRAPPER: Calling KPP_INIT_FIXED'
      CALL KPP_INIT_FIXED(myThid)

C     Check maskC after KPP_INIT_FIXED
      WRITE(6,*) 'DEBUG after KPP_INIT_FIXED: maskC(1,1,1,bi,bj)=',
     &  maskC(1,1,1,bi,bj)

C     -------------------------------------------
C     6. Run KPP physics
C     -------------------------------------------
      WRITE(6,*) 'KPP_WRAPPER: Calling KPP_CALC'
      WRITE(6,*) 'DEBUG wrapper: fCori(1,1,bi,bj)=', fCori(1,1,bi,bj)
      WRITE(6,*) 'DEBUG wrapper: maskC(1,1,1,bi,bj)=',
     &  maskC(1,1,1,bi,bj)
      WRITE(6,*) 'DEBUG wrapper: nzmax(1,1,bi,bj)=', nzmax(1,1,bi,bj)
      WRITE(6,*) 'DEBUG wrapper: theta(1,1,1,bi,bj)=',
     &  theta(1,1,1,bi,bj)

C     KPP_CALC signature: (bi, bj, myTime, myIter, myThid)
      CALL KPP_CALC(
     I     bi, bj, 0.0D0, myIter, myThid )

C     -------------------------------------------
C     7. Output validation data
C     -------------------------------------------
      WRITE(6,*) 'KPP_WRAPPER: Calling KPP_OUTPUT_VALIDATION'
      CALL KPP_OUTPUT_VALIDATION(
     I     myIter, bi, bj, myThid )

C     -------------------------------------------
C     8. Done
C     -------------------------------------------
      WRITE(6,*) 'KPP_WRAPPER: Completed successfully'

      STOP
      END
