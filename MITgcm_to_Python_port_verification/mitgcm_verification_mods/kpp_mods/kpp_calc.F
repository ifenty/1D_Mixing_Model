#include "KPP_OPTIONS.h"
#ifdef ALLOW_AUTODIFF
# include "AUTODIFF_OPTIONS.h"
#endif
#ifdef ALLOW_SALT_PLUME
# include "SALT_PLUME_OPTIONS.h"
#endif

C-- File kpp_calc.F:
C--  Contents
C--  o KPP_CALC         - Main KPP interface routine.
C--  o KPP_CALC_DUMMY   - Dummy routine for TAF

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: KPP_CALC

C !INTERFACE: ==========================================================
      SUBROUTINE KPP_CALC(
     I     bi, bj, myTime, myIter, myThid )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE KPP_CALC                                      |
C     | o Compute all KPP fields defined in KPP.h                |
C     *==========================================================*
C     | This subroutine serves as an interface between MITGCMUV  |
C     | code and NCOM 1-D routines in kpp_routines.F             |
C     *==========================================================*

c=======================================================================
c
c     written  by  : jan morzel, august  11, 1994
c     modified by  : jan morzel, january 25, 1995 : "dVsq" and 1d code
c                    detlef stammer, august, 1997 : for MIT GCM Classic
c                    d. menemenlis,    july, 1998 : for MIT GCM UV
c
c     compute vertical mixing coefficients based on the k-profile
c     and oceanic planetary boundary layer scheme by large & mcwilliams.
c
c     summary:
c     - compute interior mixing everywhere:
c       interior mixing gets computed at all interfaces due to constant
c       internal wave background activity ("fkpm" and "fkph"), which
c       is enhanced in places of static instability (local richardson
c       number < 0).
c       Additionally, mixing can be enhanced by adding contribution due
c       to shear instability which is a function of the local richardson
c       number
c     - double diffusivity:
c       interior mixing can be enhanced by double diffusion due to salt
c       fingering and diffusive convection (ifdef "kmixdd").
c     - kpp scheme in the boundary layer:
c
c       a.boundary layer depth:
c         at every gridpoint the depth of the oceanic boundary layer
c         ("hbl") gets computed by evaluating bulk richardson numbers.
c       b.boundary layer mixing:
c         within the boundary layer, above hbl, vertical mixing is
c         determined by turbulent surface fluxes, and interior mixing at
c         the lower boundary, i.e. at hbl.
c
c     this subroutine provides the interface between the MITGCM and
c     the routine "kppmix", where boundary layer depth, vertical
c     viscosity, vertical diffusivity, and counter gradient term (ghat)
c     are computed slabwise.
c     note: subroutine "kppmix" uses m-k-s units.
c
c     time level:
c     input tracer and velocity profiles are evaluated at time level
c     tau, surface fluxes come from tau or tau-1.
c
c     grid option:
c     in this "1-grid" implementation, diffusivity and viscosity
c     profiles are computed on the "t-grid" (by using velocity shear
c     profiles averaged from the "u,v-grid" onto the "t-grid"; note, that
c     the averaging includes zero values on coastal and seafloor grid
c     points).  viscosity on the "u,v-grid" is computed by averaging the
c     "t-grid" viscosity values onto the "u,v-grid".
c
c     vertical grid:
c     mixing coefficients get evaluated at the bottom of the lowest
c     layer, i.e., at depth zw(Nr).  these values are only useful when
c     the model ocean domain does not include the entire ocean down to
c     the seafloor ("upperocean" setup) and allows flux through the
c     bottom of the domain.  for full-depth runs, these mixing
c     coefficients are being zeroed out before leaving this subroutine.
c
c-------------------------------------------------------------------------

c global parameters updated by kpp_calc
c     KPPviscAz   - KPP eddy viscosity coefficient                 (m^2/s)
c     KPPdiffKzT  - KPP diffusion coefficient for temperature      (m^2/s)
c     KPPdiffKzS  - KPP diffusion coefficient for salt and tracers (m^2/s)
c     KPPghat     - Nonlocal transport coefficient                 (s/m^2)
c     KPPhbl      - Boundary layer depth on "t-grid"                   (m)
c     KPPfrac     - Fraction of short-wave flux heating the mixing layer
c     KPPplumefrac- Fraction of saltplume (flux) penetrating mixing layer

c--   KPP_CALC computes vertical viscosity and diffusivity for region
c     (-2:sNx+3,-2:sNy+3) as required by CALC_DIFFUSIVITY and requires
c     values of uVel, vVel, surfaceForcingU, surfaceForcingV in the
c     region (-2:sNx+4,-2:sNy+4).
c     Hence overlap region needs to be set OLx=4, OLy=4.
c \ev

C !USES: ===============================================================
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "DYNVARS.h"
#include "KPP.h"
#include "KPP_PARAMS.h"
#include "FFIELDS.h"
#include "GRID.h"
#include "GAD.h"
#ifdef ALLOW_SALT_PLUME
# include "SALT_PLUME.h"
#endif /* ALLOW_SALT_PLUME */
#ifdef ALLOW_SHELFICE
# include "SHELFICE.h"
#endif /* ALLOW_SHELFICE */
#ifdef ALLOW_AUTODIFF_TAMC
# include "tamc.h"
#endif /* ALLOW_AUTODIFF_TAMC */

C !INPUT PARAMETERS: ===================================================
c Routine arguments
c     bi, bj :: Current tile indices
c     myTime :: Current time in simulation
c     myIter :: Current iteration number in simulation
c     myThid :: My Thread Id. number
      INTEGER bi, bj
      _RL     myTime
      INTEGER myIter
      INTEGER myThid

#ifdef ALLOW_KPP
C !FUNCTIONS:
      LOGICAL  DIFFERENT_MULTIPLE
      EXTERNAL DIFFERENT_MULTIPLE

C !LOCAL VARIABLES: ====================================================
c Local constants
c     minusone, p0, p5, p25, p125, p0625
c     iMin, iMax, jMin, jMax  - array computation indices
      _RL        minusone
      PARAMETER( minusone=-1.0)
      _RL        p0    , p5    , p25     , p125      , p0625
      PARAMETER( p0=0.0, p5=0.5, p25=0.25, p125=0.125, p0625=0.0625 )
      INTEGER   iMin      ,iMax          ,jMin      ,jMax
      PARAMETER(iMin=2-OLx,iMax=sNx+OLx-1,jMin=2-OLy,jMax=sNy+OLy-1)

c Local arrays and variables
c     sdens  (nx,ny        - density of surface layer                (kg/m^3)
c     ustar  (nx,ny)       - surface friction velocity                  (m/s)
c     bo     (nx,ny)       - surface turbulent buoyancy forcing     (m^2/s^3)
c     bosol  (nx,ny)       - surface radiative buoyancy forcing     (m^2/s^3)
c     shsq   (nx,ny,Nr)    - local velocity shear squared
c                            at interfaces for ri_iwmix             (m^2/s^2)
c     dVsq   (nx,ny,Nr)    - velocity shear re surface squared
c                            at grid levels for bldepth             (m^2/s^2)
c     dbloc  (nx,ny,Nr)    - local delta buoyancy at interfaces
c                            for ri_iwmix and bldepth                 (m/s^2)
c     Ritop  (nx,ny,Nr)    - numerator of bulk richardson number
c                            at grid levels for bldepth
c     vddiff (nx,ny,Nrp2,1)- vertical viscosity on "t-grid"           (m^2/s)
c     vddiff (nx,ny,Nrp2,2)- vert. diff. on next row for salt&tracers (m^2/s)
c     vddiff (nx,ny,Nrp2,3)- vert. diff. on next row for temperature  (m^2/s)
c     ghat   (nx,ny,Nr)    - nonlocal transport coefficient           (s/m^2)
c     hbl    (nx,ny)       - mixing layer depth                           (m)
c     kbl    (nx,ny)       - k-cell index of mixing layer depth
c     kmtj   (nx,ny)       - maximum number of wet levels in each column
c     work?  (nx,ny)       - horizontal working arrays
c     temp?  (nx,ny,Nr)    - 3d working arrays
c     boplume(nx,ny,Nrp1)  - surface haline buoyancy forcing        (m^2/s^3)
      _RL sdens ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
      _RL ustar ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
      _RL bo    ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
      _RL bosol ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
      _RL shsq  ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr            )
      _RL dVsq  ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr            )
      _RL dbloc ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr            )
      _RL Ritop ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr            )
      _RL vddiff( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, 0:Nrp1, mdiff )
      _RL ghat  ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr            )
      _RL hbl   ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
C     1DMIX-025: KPPMIX's real bulk Richardson number profile and final
C     surface buoyancy forcing, now exposed as new output arguments
C     (kpp_routines.F) purely for this project's OUTPUT_DIAGNOSTICS dump
C     below -- not otherwise used, no existing behavior changed.
      _RL kppRib   ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr )
      _RL kppBfsfc ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy               )
cph(
      _RL TTALPHA( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nrp1 )
      _RL SSBETA ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nrp1 )
cph)
#if ( defined ALLOW_SALT_PLUME || defined SHORTWAVE_HEATING )
      _RL worka ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
#endif
#ifdef ALLOW_SALT_PLUME
      _RL temp1   ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr          )
      _RL temp2   ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nr          )
      _RL boplume ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy, Nrp1        )
#ifdef SALT_PLUME_SPLIT_BASIN
      _RL lon ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                  )
      _RL lat ( 1-OLx:sNx+OLx, 1-OLy:sNy+OLy                  )
#endif /* SALT_PLUME_SPLIT_BASIN */
#endif /* ALLOW_SALT_PLUME */
#ifdef SHORTWAVE_HEATING
      INTEGER kbl(1-OLx:sNx+OLx, 1-OLy:sNy+OLy                )
C     interpolation factor 1 >= (KPPhbl+rF(kbl))/drF(kbl) >= 0
      _RL rFac
#endif
      INTEGER i, j, kSurf, k, kp1, km1, im1, ip1, jm1, jp1
C     ikey :: tape key (depends on tiles)
      INTEGER ikey
CEOP

#ifdef ALLOW_AUTODIFF_TAMC
      ikey = bi + (bj-1)*nSx + (ikey_dynamics-1)*nSx*nSy
#else /* ALLOW_AUTODIFF_TAMC */
      ikey = 0
#endif /* ALLOW_AUTODIFF_TAMC */

c     Check to see if new vertical mixing coefficient should be computed now?
      IF ( DIFFERENT_MULTIPLE(kpp_freq,myTime,deltaTClock)
     1     .OR. myTime .EQ. startTime ) THEN

c-----------------------------------------------------------------------
c     prepare input arrays for subroutine "kppmix" to compute
c     viscosity and diffusivity and ghat.
c     All input arrays need to be in m-k-s units.
c
c     note: for the computation of the bulk richardson number in the
c     "bldepth" subroutine, gradients of velocity and buoyancy are
c     required at every depth. in the case of very fine vertical grids
c     (thickness of top layer < 2m), the surface reference depth must
c     be set to zref=epsilon/2*zgrid(k), and the reference value
c     of velocity and buoyancy must be computed as vertical average
c     between the surface and 2*zref.  in the case of coarse vertical
c     grids zref is zgrid(1)/2., and the surface reference value is
c     simply the surface value at zgrid(1).
c-----------------------------------------------------------------------

c------------------------------------------------------------------------
c     density related quantities
c     --------------------------
c
c      sdens   - density of surface layer                        (kg/m^3)
c      dbloc   - local buoyancy gradient at Nr interfaces
c                g/rho{k+1,k+1} * [ drho{k,k+1}-drho{k+1,k+1} ]   (m/s^2)
c      dbsfc (stored in Ritop to conserve stack memory)
c              - buoyancy difference with respect to the surface
c                g * [ drho{1,k}/rho{1,k} - drho{k,k}/rho{k,k} ]  (m/s^2)
c      ttalpha - thermal expansion coefficient without 1/rho factor
c                d(rho{k,k})/d(T(k))                           (kg/m^3/C)
c      ssbeta  - salt expansion coefficient without 1/rho factor
c                d(rho{k,k})/d(S(k))                    ((kg/m^3)/(g/kg))
c------------------------------------------------------------------------

      CALL STATEKPP(
     O     sdens, dbloc, Ritop,
     O     TTALPHA, SSBETA,
     I     ikey, bi, bj, myThid )

      DO k = 1, Nr
       DO j = 1-OLy, sNy+OLy
        DO i = 1-OLx, sNx+OLx
         ghat(i,j,k) = dbloc(i,j,k)
        ENDDO
       ENDDO
      ENDDO

#ifdef KPP_SMOOTH_DBLOC
c     horizontally smooth dbloc with a 121 filter
c     smooth dbloc stored in ghat to save space
c     dbloc(k) is buoyancy gradientnote between k and k+1
c     levels therefore k+1 mask must be used

      DO k = 1, Nr-1
       CALL SMOOTH_HORIZ (
     I      k+1, bi, bj,
     U      ghat (1-OLx,1-OLy,k),
     I      myThid )
      ENDDO

#endif /* KPP_SMOOTH_DBLOC */

#ifdef KPP_SMOOTH_DENS
c     horizontally smooth density related quantities with 121 filters
      CALL SMOOTH_HORIZ (
     I     1, bi, bj,
     U     sdens,
     I     myThid )
      DO k = 1, Nr
         CALL SMOOTH_HORIZ (
     I        k+1, bi, bj,
     U        dbloc (1-OLx,1-OLy,k),
     I        myThid )
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        Ritop (1-OLx,1-OLy,k),
     I        myThid )
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        TTALPHA(1-OLx,1-OLy,k),
     I        myThid )
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        SSBETA(1-OLx,1-OLy,k),
     I        myThid )
      ENDDO
#endif /* KPP_SMOOTH_DENS */

c     surface index
      kSurf = 1
      DO k = 1, Nr
       km1 = max(1,k-1)
       kp1 = min(Nr,k+1)
       DO j = 1-OLy, sNy+OLy
        DO i = 1-OLx, sNx+OLx

c     zero out dbloc over land points (so that the convective
c     part of the interior mixing can be diagnosed).
c     ML: Note that dbloc and ghat (=smoothed dbloc) are defined at
c     the bottom of the cell rather than the (MITgcm-standard) top
c     of the cell; therefore the proper masking is maskC(k)*maskC(k+1)
         dbloc(i,j,k) = dbloc(i,j,k) * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,kp1,bi,bj)
         ghat(i,j,k)  = ghat(i,j,k)  * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,kp1,bi,bj)
#ifdef ALLOW_SHELFICE
         IF ( useShelfIce ) kSurf = MAX(1,kTopC(i,j,bi,bj))
#endif /* ALLOW_SHELFICE */
         Ritop(i,j,k) = Ritop(i,j,k) * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,kSurf,bi,bj)
         IF(k.EQ.nzmax(i,j,bi,bj)) THEN
          dbloc(i,j,k) = p0
          ghat(i,j,k)  = p0
          Ritop(i,j,k) = p0
         ENDIF

c     numerator of bulk richardson number on grid levels
c     note: land and ocean bottom values need to be set to zero
c     so that the subroutine "bldepth" works correctly
         Ritop(i,j,k) = (zgrid(1)-zgrid(k)) * Ritop(i,j,k)

        ENDDO
       ENDDO
      ENDDO

cph(
cph  this avoids a single or double recomp./call of statekpp
#ifdef ALLOW_AUTODIFF_TAMC
CADJ STORE sdens, Ritop       = comlev1_kpp, key = ikey
CADJ STORE TTALPHA, SSBETA    = comlev1_kpp, key = ikey
#endif /* ALLOW_AUTODIFF_TAMC */
cph)

CML#ifdef ALLOW_SHELFICE
CMLC     For the pbl parameterisation to work underneath the ice shelves
CMLC     it needs to know the surface (ice-ocean) fluxes. However, masking
CMLC     and indexing problems make this part of the code not work
CMLC     underneath the ice shelves and the following lines are only here
CMLC     to remind me that this still needs to be sorted out.
CML      shelfIceFac = 0. _d 0
CML      IF ( useShelfIce ) selfIceFac = 1. _d 0
CML      DO j = jMin, jMax
CML       DO i = iMin, iMax
CML        surfForcT = surfaceForcingT(i,j,bi,bj)
CML     &       + shelficeForcingT(i,j,bi,bj) * shelfIceFac
CML        surfForcS = surfaceForcingS(i,j,bi,bj)
CML     &       + shelficeForcingS(i,j,bi,bj) * shelfIceFac
CML       ENDDO
CML      ENDDO
CML#endif /* ALLOW_SHELFICE */

c------------------------------------------------------------------------
c     friction velocity, turbulent and radiative surface buoyancy forcing
c     -------------------------------------------------------------------
c     taux / rho = surfaceForcingU                               (N/m^2)
c     tauy / rho = surfaceForcingV                               (N/m^2)
c     ustar = sqrt( sqrt( taux^2 + tauy^2 ) / rho )                (m/s)
c     bo    = - g * ( alpha*surfaceForcingT +
c                     beta *surfaceForcingS ) / rho            (m^2/s^3)
c     bosol = - g * alpha * Qsw * drF(1) / rho                 (m^2/s^3)
c     boplume = g * (beta * saltPlumeFlux/rhoConst ) /rho      (m^2/s^3)
c             = g * (beta * SPforcingS   /rhoConst ) /rho
c              +g * (alpha* SPforcingT   / ??
c------------------------------------------------------------------------
c     velocity shear
c     --------------
c     Get velocity shear squared, averaged from "u,v-grid"
c     onto "t-grid" (in (m/s)**2):
c     dVsq(k)=(Uref-U(k))**2+(Vref-V(k))**2      at grid levels
c     shsq(k)=(U(k)-U(k+1))**2+(V(k)-V(k+1))**2  at interfaces
c
c     note: Vref can depend on the surface fluxes that is why we compute
c     dVsq in the subroutine that does the surface related stuff
c     (admittedly this is a bit messy)
c------------------------------------------------------------------------

#ifdef ALLOW_SALT_PLUME
      DO j=jMin,jMax
       DO i=iMin,iMax
#ifndef SALT_PLUME_VOLUME
        temp1(i,j,1) = saltPlumeFlux(i,j,bi,bj)
        temp2(i,j,1) = 0. _d 0
        DO k=2,Nr
         temp1(i,j,k) = 0. _d 0
         temp2(i,j,k) = 0. _d 0
        ENDDO
#else /* def SALT_PLUME_VOLUME */
        DO k=1,Nr
         temp1(i,j,k) = SPforcingS(i,j,k,bi,bj)
         temp2(i,j,k) = SPforcingT(i,j,k,bi,bj)
        ENDDO
#endif /* SALT_PLUME_VOLUME */
       ENDDO
      ENDDO
#endif /* ALLOW_SALT_PLUME */

      CALL KPP_FORCING_SURF(
     I     sdens, surfaceForcingU, surfaceForcingV,
     I     surfaceForcingT, surfaceForcingS, adjustColdSST_diag,
     I     Qsw,
#ifdef KPP_ESTIMATE_UREF
     I     dbloc,
#endif /* KPP_ESTIMATE_UREF */
#ifdef ALLOW_SALT_PLUME
     I     temp1, temp2,
#endif /* ALLOW_SALT_PLUME */
     I     ttalpha, ssbeta,
     O     ustar, bo, bosol,
#ifdef ALLOW_SALT_PLUME
     O     boplume,
#endif /* ALLOW_SALT_PLUME */
     O     dVsq,
     I     ikey, iMin, iMax, jMin, jMax, bi, bj, myTime, myThid )

#ifdef ALLOW_AUTODIFF_TAMC
CADJ STORE ustar, bo, bosol, dVsq = comlev1_kpp, key = ikey
# ifdef ALLOW_SALT_PLUME
CADJ STORE boplume = comlev1_kpp, key = ikey
# endif
#endif

c initialize arrays to zero
      DO k = 1, Nr
       DO j = 1-OLy, sNy+OLy
        DO i = 1-OLx, sNx+OLx
         shsq(i,j,k) = p0
        ENDDO
       ENDDO
      ENDDO

c     shsq computation
      DO k = 1, Nrm1
       kp1 = k + 1
       DO j = jMin, jMax
        jm1 = j - 1
        jp1 = j + 1
        DO i = iMin, iMax
         im1 = i - 1
         ip1 = i + 1
         shsq(i,j,k) = p5 * (
     &        (uVel(i,  j,  k,bi,bj)-uVel(i,  j,  kp1,bi,bj)) *
     &        (uVel(i,  j,  k,bi,bj)-uVel(i,  j,  kp1,bi,bj)) +
     &        (uVel(ip1,j,  k,bi,bj)-uVel(ip1,j,  kp1,bi,bj)) *
     &        (uVel(ip1,j,  k,bi,bj)-uVel(ip1,j,  kp1,bi,bj)) +
     &        (vVel(i,  j,  k,bi,bj)-vVel(i,  j,  kp1,bi,bj)) *
     &        (vVel(i,  j,  k,bi,bj)-vVel(i,  j,  kp1,bi,bj)) +
     &        (vVel(i,  jp1,k,bi,bj)-vVel(i,  jp1,kp1,bi,bj)) *
     &        (vVel(i,  jp1,k,bi,bj)-vVel(i,  jp1,kp1,bi,bj)) )
#ifdef KPP_SMOOTH_SHSQ
         shsq(i,j,k) = p5 * shsq(i,j,k) + p125 * (
     &        (uVel(i,  jm1,k,bi,bj)-uVel(i,  jm1,kp1,bi,bj)) *
     &        (uVel(i,  jm1,k,bi,bj)-uVel(i,  jm1,kp1,bi,bj)) +
     &        (uVel(ip1,jm1,k,bi,bj)-uVel(ip1,jm1,kp1,bi,bj)) *
     &        (uVel(ip1,jm1,k,bi,bj)-uVel(ip1,jm1,kp1,bi,bj)) +
     &        (uVel(i,  jp1,k,bi,bj)-uVel(i,  jp1,kp1,bi,bj)) *
     &        (uVel(i,  jp1,k,bi,bj)-uVel(i,  jp1,kp1,bi,bj)) +
     &        (uVel(ip1,jp1,k,bi,bj)-uVel(ip1,jp1,kp1,bi,bj)) *
     &        (uVel(ip1,jp1,k,bi,bj)-uVel(ip1,jp1,kp1,bi,bj)) +
     &        (vVel(im1,j,  k,bi,bj)-vVel(im1,j,  kp1,bi,bj)) *
     &        (vVel(im1,j,  k,bi,bj)-vVel(im1,j,  kp1,bi,bj)) +
     &        (vVel(im1,jp1,k,bi,bj)-vVel(im1,jp1,kp1,bi,bj)) *
     &        (vVel(im1,jp1,k,bi,bj)-vVel(im1,jp1,kp1,bi,bj)) +
     &        (vVel(ip1,j,  k,bi,bj)-vVel(ip1,j,  kp1,bi,bj)) *
     &        (vVel(ip1,j,  k,bi,bj)-vVel(ip1,j,  kp1,bi,bj)) +
     &        (vVel(ip1,jp1,k,bi,bj)-vVel(ip1,jp1,kp1,bi,bj)) *
     &        (vVel(ip1,jp1,k,bi,bj)-vVel(ip1,jp1,kp1,bi,bj)) )
#endif
        ENDDO
       ENDDO
      ENDDO

#ifdef ALLOW_DIAGNOSTICS
      IF ( useDiagnostics ) THEN
       CALL DIAGNOSTICS_FILL(shsq,  'KPPshsq ',0,Nr,2,bi,bj,myThid)
      ENDIF
#endif /* ALLOW_DIAGNOSTICS */
cph(
#ifdef ALLOW_AUTODIFF_TAMC
#ifdef KPP_AUTODIFF_EXCESSIVE_STORE
CADJ STORE shsq = comlev1_kpp, key = ikey
#endif
#endif /* ALLOW_AUTODIFF_TAMC */
cph)

c-----------------------------------------------------------------------
c     solve for viscosity, diffusivity, ghat, and hbl on "t-grid"
c-----------------------------------------------------------------------

#if ( !defined EXCLUDE_PCELL_MIX_CODE && defined  ALLOW_AUTODIFF_TAMC )
CADJ STORE KPPdiffKzS(:,:,:,bi,bj) = comlev1_kpp, key = ikey
CADJ STORE KPPdiffKzT(:,:,:,bi,bj) = comlev1_kpp, key = ikey
#endif
c     precompute background vertical diffusivities, which are needed for
c     matching diffusivities at bottom of KPP PBL
      CALL CALC_3D_DIFFUSIVITY(
     I        bi,bj,1-OLx,sNx+OLx,1-OLy,sNy+OLy,
     I        GAD_SALINITY, .FALSE., .FALSE.,
     O        KPPdiffKzS(1-OLx,1-OLy,1,bi,bj),
     I        myThid)
      CALL CALC_3D_DIFFUSIVITY(
     I        bi,bj,1-OLx,sNx+OLx,1-OLy,sNy+OLy,
     I        GAD_TEMPERATURE, .FALSE., .FALSE.,
     O        KPPdiffKzT(1-OLx,1-OLy,1,bi,bj),
     I        myThid)
#ifndef EXCLUDE_KPP_DOUBLEDIFF
      IF ( KPPuseDoubleDiff ) THEN
C     Add the contribution of double diffusive effects (salt fingering
C     and diffusive convection) here. It would be more logical to add
C     them right after Ri_iwmix within kppmix, but ttalpha, ssbeta, theta
C     and salt are not passed to kppmix and are thus not available there.
       CALL KPP_DOUBLEDIFF(
     I      TTALPHA, SSBETA,
     U      KPPdiffKzT(1-OLx,1-OLy,1,bi,bj),
     U      KPPdiffKzS(1-OLx,1-OLy,1,bi,bj),
     I      ikey,1-OLx,sNx+OLx,1-OLy,sNy+OLy,bi,bj,myThid)
      ENDIF
#endif /* ndef EXCLUDE_KPP_DOUBLEDIFF */
#ifdef ALLOW_AUTODIFF_TAMC
CADJ STORE KPPdiffKzS(:,:,:,bi,bj) = comlev1_kpp, key = ikey
CADJ STORE KPPdiffKzT(:,:,:,bi,bj) = comlev1_kpp, key = ikey
#endif

      CALL KPPMIX (
     I       nzmax(1-OLx,1-OLy,bi,bj), shsq, dVsq, ustar,
     I       maskC(1-OLx,1-OLy,1,bi,bj),
     I       bo, bosol,
#ifdef ALLOW_SALT_PLUME
     I       boplume, SaltPlumeDepth(1-OLx,1-OLy,bi,bj),
#ifdef SALT_PLUME_SPLIT_BASIN
     I       XC(1-OLx,1-OLy,bi,bj), YC(1-OLx,1-OLy,bi,bj),
#endif /* SALT_PLUME_SPLIT_BASIN */
#endif /* ALLOW_SALT_PLUME */
     I       dbloc, Ritop, fCori(1-OLx,1-OLy,bi,bj),
#ifdef SHORTWAVE_HEATING
     I       SWFRac3D  (1-OLx,1-OLy,1,bi,bj),
#endif
     I       KPPdiffKzS(1-OLx,1-OLy,1,bi,bj),
     I       KPPdiffKzT(1-OLx,1-OLy,1,bi,bj),
     I       ikey,
     O       vddiff,
     U       ghat,
     O       hbl,
#ifdef SHORTWAVE_HEATING
     O       kbl,
#endif
     O       kppRib, kppBfsfc,
     I       bi, bj, myTime, myIter, myThid )

c-----------------------------------------------------------------------
c     zero out land values and transfer to global variables
c-----------------------------------------------------------------------

      DO k = 1, Nr
       km1 = max(1,k-1)
       DO j = jMin, jMax
        DO i = iMin, iMax
         KPPviscAz(i,j,k,bi,bj) = vddiff(i,j,k-1,1) * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,km1,bi,bj)
         KPPdiffKzS(i,j,k,bi,bj)= vddiff(i,j,k-1,2) * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,km1,bi,bj)
         KPPdiffKzT(i,j,k,bi,bj)= vddiff(i,j,k-1,3) * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,km1,bi,bj)
         KPPghat(i,j,k,bi,bj)   = ghat(i,j,k)       * maskC(i,j,k,bi,bj)
     &        * maskC(i,j,km1,bi,bj)
        ENDDO
       ENDDO
      ENDDO
      kSurf = 1
      DO j = jMin, jMax
       DO i = iMin, iMax
#ifdef ALLOW_SHELFICE
        IF ( useShelfIce ) kSurf = MAX(1,kTopC(i,j,bi,bj))
#endif /* ALLOW_SHELFICE */
        KPPhbl(i,j,bi,bj) = hbl(i,j) * maskC(i,j,kSurf,bi,bj)
       ENDDO
      ENDDO

c-------------------------------------------------------------------
c     Output KPP inputs and outputs for Python validation
c-------------------------------------------------------------------
      CALL KPP_OUTPUT_VALIDATION(
     I     myIter, bi, bj, myThid,
     I     ustar, bo, bosol, shsq, dbloc, dVsq, Ritop,
     I     kppRib, kppBfsfc
#ifdef ALLOW_SALT_PLUME
     I     , boplume
#endif /* ALLOW_SALT_PLUME */
     I     )

#ifdef KPP_SMOOTH_VISC
c     horizontal smoothing of vertical viscosity
      DO k = 1, Nr
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        KPPviscAz(1-OLx,1-OLy,k,bi,bj),
     I        myThid )
      ENDDO
C jmc: No EXCH inside bi,bj loop !!!
c     _EXCH_XYZ_RL(KPPviscAz  , myThid )
#endif /* KPP_SMOOTH_VISC */

#ifdef KPP_SMOOTH_DIFF
c     horizontal smoothing of vertical diffusivity
      DO k = 1, Nr
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        KPPdiffKzS(1-OLx,1-OLy,k,bi,bj),
     I        myThid )
         CALL SMOOTH_HORIZ (
     I        k, bi, bj,
     U        KPPdiffKzT(1-OLx,1-OLy,k,bi,bj),
     I        myThid )
      ENDDO
#endif /* KPP_SMOOTH_DIFF */

cph(
cph  crucial: this avoids full recomp./call of kppmix
#ifdef ALLOW_AUTODIFF_TAMC
CADJ STORE KPPhbl(:,:,bi,bj) = comlev1_kpp, key = ikey
# ifdef SHORTWAVE_HEATING
CADJ STORE kbl = comlev1_kpp, key = ikey
# endif
#endif /* ALLOW_AUTODIFF_TAMC */
cph)

#ifdef SHORTWAVE_HEATING
      IF ( selectPenetratingSW .GE. 1 ) THEN
#ifdef ALLOW_AUTODIFF_TAMC
C     Avoid uselessly recomputing this block because of re-using worka
CADJ INCOMPLETE worka
#endif
       IF ( KPPuseSWfrac3D ) THEN
C     Determine the fraction of solar shortwave flux penetrating to the
C     bottom of the mixed layer by interpolation.
        DO j=1-OLy,sNy+OLy
         DO i=1-OLx,sNx+OLx
          k = kbl(i,j)
          rFac = MAX( (KPPhbl(i,j,bi,bj)+rF(k))*recip_drF(k), zeroRL )
          worka(i,j) = SWFrac3D(i,j,k,bi,bj)
     &         + rFac*(SWFrac3D(i,j,k+1,bi,bj) - SWFrac3D(i,j,k,bi,bj))
         ENDDO
        ENDDO
       ELSE
C     Compute fraction of solar short-wave flux penetrating to
C     the bottom of the mixing layer.
        DO j=1-OLy,sNy+OLy
         DO i=1-OLx,sNx+OLx
          worka(i,j) = KPPhbl(i,j,bi,bj)
         ENDDO
        ENDDO
        CALL SWFRAC(
     I     (sNx+2*OLx)*(sNy+2*OLy), minusone,
     U     worka,
     I     myTime, myIter, myThid )
       ENDIF
       DO j=1-OLy,sNy+OLy
        DO i=1-OLx,sNx+OLx
         KPPfrac(i,j,bi,bj) = 1. _d 0 - worka(i,j)
        ENDDO
       ENDDO
      ENDIF
#endif /* SHORTWAVE_HEATING */

#ifdef ALLOW_SALT_PLUME
C     Compute fraction of saltplume (flux) penetrating to
C     the bottom of the mixing layer.
#ifdef ALLOW_AUTODIFF_TAMC
C     Avoid uselessly recomputing the previous block because of worka
CADJ INCOMPLETE worka
#endif
      IF ( useSALT_PLUME ) THEN
#ifndef SALT_PLUME_VOLUME
       DO j=1-OLy,sNy+OLy
        DO i=1-OLx,sNx+OLx
         worka(i,j) = KPPhbl(i,j,bi,bj)
#ifdef SALT_PLUME_SPLIT_BASIN
         lon(i,j) = XC(i,j,bi,bj)
         lat(i,j) = YC(i,j,bi,bj)
#endif /* SALT_PLUME_SPLIT_BASIN */
        ENDDO
       ENDDO
       CALL SALT_PLUME_FRAC(
     I      (sNx+2*OLx)*(sNy+2*OLy), minusone,
     I      SaltPlumeDepth(1-OLx,1-OLy,bi,bj),
#ifdef SALT_PLUME_SPLIT_BASIN
     I      lon,lat,
#endif /* SALT_PLUME_SPLIT_BASIN */
     U      worka,
     I      myTime, myIter, myThid )
       DO j=1-OLy,sNy+OLy
        DO i=1-OLx,sNx+OLx
         KPPplumefrac(i,j,bi,bj) = 1. _d 0 - worka(i,j)
        ENDDO
       ENDDO
#else /* SALT_PLUME_VOLUME */
       DO j=1-OLy,sNy+OLy
        DO i=1-OLx,sNx+OLx
         KPPplumefrac(i,j,bi,bj) = 0. _d 0
        ENDDO
       ENDDO
#endif /* SALT_PLUME_VOLUME */
      ENDIF
#endif /* ALLOW_SALT_PLUME */

      ENDIF

#endif /* ALLOW_KPP */

      RETURN
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
CBOP
C !ROUTINE: KPP_CALC_DUMMY

C !INTERFACE: ==========================================================
      SUBROUTINE KPP_CALC_DUMMY(
     I     bi, bj, myTime, myIter, myThid )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE KPP_CALC_DUMMY                                |
C     | o Compute all KPP fields defined in KPP.h                |
C     | o Dummy routine for TAF                                  |
C     *==========================================================*

C !USES: ===============================================================
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "KPP.h"
#include "KPP_PARAMS.h"
#include "GRID.h"
#include "GAD.h"
#ifdef ALLOW_AUTODIFF_TAMC
# include "tamc.h"
#endif /* ALLOW_AUTODIFF_TAMC */

C !INPUT PARAMETERS: ===================================================
c     bi, bj :: Current tile indices
c     myTime :: Current time in simulation
c     myIter :: Current iteration number in simulation
c     myThid :: My Thread Id. number
      INTEGER bi, bj
      _RL     myTime
      INTEGER myIter
      INTEGER myThid

#ifdef ALLOW_KPP
C !LOCAL VARIABLES: ====================================================
      INTEGER i, j, k
#if ( !defined EXCLUDE_PCELL_MIX_CODE && defined  ALLOW_AUTODIFF_TAMC )
      INTEGER ikey
#endif
CEOP

      DO j=1-OLy,sNy+OLy
         DO i=1-OLx,sNx+OLx
            KPPhbl (i,j,bi,bj) = 1.0
            KPPfrac(i,j,bi,bj) = 0.0
#ifdef ALLOW_SALT_PLUME
            KPPplumefrac(i,j,bi,bj) = 0.0
#endif /* ALLOW_SALT_PLUME */
            DO k = 1,Nr
               KPPghat   (i,j,k,bi,bj) = 0.0
               KPPviscAz (i,j,k,bi,bj) = viscArNr(1)
            ENDDO
         ENDDO
      ENDDO

#if ( !defined EXCLUDE_PCELL_MIX_CODE && defined  ALLOW_AUTODIFF_TAMC )
      ikey = bi + (bj-1)*nSx + (ikey_dynamics-1)*nSx*nSy
CADJ STORE KPPdiffKzS(:,:,:,bi,bj) = comlev1_kpp, key = ikey
CADJ STORE KPPdiffKzT(:,:,:,bi,bj) = comlev1_kpp, key = ikey
#endif
      CALL CALC_3D_DIFFUSIVITY(
     I     bi,bj,1-OLx,sNx+OLx,1-OLy,sNy+OLy,
     I     GAD_SALINITY, .FALSE., .FALSE.,
     O     KPPdiffKzS(1-OLx,1-OLy,1,bi,bj),
     I     myThid)
      CALL CALC_3D_DIFFUSIVITY(
     I     bi,bj,1-OLx,sNx+OLx,1-OLy,sNy+OLy,
     I     GAD_TEMPERATURE, .FALSE., .FALSE.,
     O     KPPdiffKzT(1-OLx,1-OLy,1,bi,bj),
     I     myThid)

#endif /* ALLOW_KPP */

      RETURN
      END

C---+----1----+----2----+----3----+----4----+----5----+----6----+----7-|--+----|
#ifdef ALLOW_KPP
CBOP
C !ROUTINE: KPP_OUTPUT_VALIDATION

C !INTERFACE:
      SUBROUTINE KPP_OUTPUT_VALIDATION(
     I     myIter, bi, bj, myThid,
     I     ustar, bo, bosol, shsq, dbloc, dVsq, Ritop,
     I     kppRib, kppBfsfc
#ifdef ALLOW_SALT_PLUME
     I     , boplume
#endif /* ALLOW_SALT_PLUME */
     I     )

C !DESCRIPTION: \bv
C     *==========================================================*
C     | SUBROUTINE KPP_OUTPUT_VALIDATION                         |
C     | o Output KPP inputs and outputs for Python validation    |
C     *==========================================================*
C     | Outputs CSV-formatted data to STDOUT with ES25.16       |
C     | (17 significant digits, 1DMIX-069) for rtol=1e-12 tests |
C     *==========================================================*
C \ev

C !USES:
      IMPLICIT NONE
#include "SIZE.h"
#include "EEPARAMS.h"
#include "PARAMS.h"
#include "DYNVARS.h"
#include "KPP.h"
#include "KPP_PARAMS.h"
#include "GRID.h"
#include "FFIELDS.h"
C     1DMIX-034 part 2: SALT_PLUME.h brings in PlumeMethod/Npower (INTEGER
C     PARAMS common) and SaltPlumeDepth (DYNVARS common) as globals -- no
C     dummy argument needed for those two, unlike boplume below (a LOCAL
C     array in KPP_CALC, which Fortran scoping requires be passed in
C     explicitly, exactly like ustar/bo/bosol above).
#ifdef ALLOW_SALT_PLUME
# include "SALT_PLUME.h"
#endif /* ALLOW_SALT_PLUME */

C !INPUT PARAMETERS:
      INTEGER myIter
      INTEGER bi, bj
      INTEGER myThid
      Real*8 ustar(1-OLx:sNx+OLx,1-OLy:sNy+OLy)
      Real*8 bo(1-OLx:sNx+OLx,1-OLy:sNy+OLy)
      Real*8 bosol(1-OLx:sNx+OLx,1-OLy:sNy+OLy)
      Real*8 shsq(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      Real*8 dbloc(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
C     dVsq, Ritop :: direct KPPMIX inputs not otherwise derivable from
C     the captured state; needed so the standalone-subroutine harness
C     (calls KPPMIX only, not STATEKPP/KPP_FORCING_SURF) can be fed the
C     exact values the full model used.
      Real*8 dVsq(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      Real*8 Ritop(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
C     1DMIX-025: kppRib/kppBfsfc are bldepth's real (post-KPPMIX) bulk
C     Richardson number and final surface buoyancy forcing, passed in
C     from KPP_CALC (a separate subroutine's locals -- Fortran scoping
C     requires these as explicit arguments, not shared automatically).
      Real*8 kppRib(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nr)
      Real*8 kppBfsfc(1-OLx:sNx+OLx,1-OLy:sNy+OLy)
C     1DMIX-034 part 2: boplume(i,j,1) is a LOCAL array in KPP_CALC
C     (declared under #ifdef ALLOW_SALT_PLUME, populated by
C     KPP_FORCING_SURF), so it must be passed explicitly.
#ifdef ALLOW_SALT_PLUME
      Real*8 boplume(1-OLx:sNx+OLx,1-OLy:sNy+OLy,Nrp1)
#endif /* ALLOW_SALT_PLUME */

C !LOCAL VARIABLES:
      INTEGER i, j, k
      INTEGER iMin, iMax, jMin, jMax
      PARAMETER(iMin=1, iMax=sNx, jMin=1, jMax=sNy)
      LOGICAL firstCall
      SAVE firstCall
      DATA firstCall /.TRUE./
CEOP

C     Output all tiles (needed for MPI runs to get full domain)
C     Include tile indices (bi, bj) in output for proper reconstruction

C     Debug: Test if output is working at all
      WRITE(6,'(A,I10,A,I3,A,I3,A,I3)')
     & 'DEBUG: KPP_OUTPUT_VALIDATION, myIter=',myIter,
     & ' bi=',bi,' bj=',bj,' myThid=',myThid

C     Output grid geometry, parameters, and headers once (first call of this run)
C     This ensures parameters are written even when starting from pickup file
      IF ( firstCall ) THEN
       firstCall = .FALSE.
C      --- MODEL PARAMETERS ---
C      Output all runtime parameters needed for KPP validation
C      (real scalars print as ES25.16 = 17 significant digits; were E16.8, 1DMIX-070)
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_MODEL_PARAMETERS ====='
C      Background mixing
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_viscAz=',viscArNr(1)
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_diffKzS=',diffKrNrS(1)
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_diffKzT=',diffKrNrT(1)
C      Physical constants
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_gravity=',gravity
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_rhoConst=',rhoConst
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_HeatCapacity_Cp=',HeatCapacity_Cp
C      Boundary layer depth parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_Ricr=',Ricr
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_cekman=',cekman
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_cmonob=',cmonob
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_concv=',concv
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_hbf=',hbf
C      Surface layer parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_epsilon=',epsilon
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_vonk=',vonk
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_dB_dz=',dB_dz
C      Interior mixing parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_Riinfty=',Riinfty
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_BVSQcon=',BVSQcon
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_difm0=',difm0
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_difs0=',difs0
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_dift0=',dift0
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_difmcon=',difmcon
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_difscon=',difscon
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_diftcon=',diftcon
C      Shape function coefficients
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_conc1=',conc1
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_conam=',conam
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_concm=',concm
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_conc2=',conc2
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_zetam=',zetam
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_conas=',conas
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_concs=',concs
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_conc3=',conc3
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_zetas=',zetas
C      Double diffusion parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_Rrho0=',Rrho0
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_dsfmax=',dsfmax
C      Regularization parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_epsln=',epsln
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_phepsi=',phepsi
C      Nonlocal transport
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_cstar=',cstar
C      Minimum boundary layer depth
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_minKPPhbl=',minKPPhbl
C      Lookup table parameters
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_zmin=',zmin
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_zmax=',zmax
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_umin=',umin
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_umax=',umax
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_deltaz=',deltaz
       WRITE(standardMessageUnit,'(A,ES25.16)')
     &   'PARAM_deltau=',deltau
C      Integer parameters
       WRITE(standardMessageUnit,'(A,I10)')
     &   'PARAM_num_v_smooth_Ri=',num_v_smooth_Ri
C      Boolean/Logical flags - runtime parameters (output as 0 or 1)
       IF (KPP_ghatUseTotalDiffus) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPP_ghatUseTotalDiffus=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPP_ghatUseTotalDiffus=0'
       ENDIF
       IF (KPPuseDoubleDiff) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPuseDoubleDiff=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPuseDoubleDiff=0'
       ENDIF
       IF (LimitHblStable) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_LimitHblStable=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_LimitHblStable=0'
       ENDIF
       IF (KPPwriteState) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPwriteState=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPwriteState=0'
       ENDIF
       IF (KPPuseSWfrac3D) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPuseSWfrac3D=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_KPPuseSWfrac3D=0'
       ENDIF
C      1DMIX-034: runtime useSALT_PLUME flag (PARAMS.h). Without this,
C      the Python port's replay harness has no way to know salt plume
C      is active and silently defaults to allow_salt_plume/use_salt_plume
C      =False, bypassing KPPParameters' own deliberate NotImplementedError
C      guard for this exact case (salt-plume physics is not ported).
       IF (useSALT_PLUME) THEN
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_useSALT_PLUME=1'
       ELSE
        WRITE(standardMessageUnit,'(A)')
     &    'PARAM_useSALT_PLUME=0'
       ENDIF
C      CPP compile-time options (from KPP_OPTIONS.h)
C      These determine which code paths were compiled in
#ifdef KPP_GHAT
       WRITE(standardMessageUnit,'(A)') 'PARAM_use_ghat=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_use_ghat=0'
#endif
#ifdef KPP_SMOOTH_SHSQ
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_shsq=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_shsq=0'
#endif
#ifdef KPP_SMOOTH_DVSQ
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dvsq=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dvsq=0'
#endif
#ifdef KPP_SMOOTH_DBLOC
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dbloc=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dbloc=0'
#endif
#ifdef KPP_SMOOTH_DENS
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dens=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_dens=0'
#endif
#ifdef KPP_SMOOTH_VISC
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_visc=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_visc=0'
#endif
#ifdef KPP_SMOOTH_DIFF
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_diff=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_smooth_diff=0'
#endif
#ifdef KPP_ESTIMATE_UREF
       WRITE(standardMessageUnit,'(A)') 'PARAM_estimate_uref=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_estimate_uref=0'
#endif
#ifdef KPP_DO_NOT_MATCH_DIFFUSIVITIES
       WRITE(standardMessageUnit,'(A)') 'PARAM_match_diffusivities=0'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_match_diffusivities=1'
#endif
#ifdef KPP_DO_NOT_MATCH_DERIVATIVES
       WRITE(standardMessageUnit,'(A)') 'PARAM_match_derivatives=0'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_match_derivatives=1'
#endif
#ifdef KPP_SMOOTH_REGULARISATION
       WRITE(standardMessageUnit,'(A)')
     &   'PARAM_smooth_regularisation=1'
#else
       WRITE(standardMessageUnit,'(A)')
     &   'PARAM_smooth_regularisation=0'
#endif
#ifdef KPP_SCALE_SHEARMIXING
       WRITE(standardMessageUnit,'(A)') 'PARAM_scale_shearmixing=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_scale_shearmixing=0'
#endif
#ifdef EXCLUDE_KPP_SHEAR_MIX
       WRITE(standardMessageUnit,'(A)') 'PARAM_exclude_shear_mix=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_exclude_shear_mix=0'
#endif
#ifdef EXCLUDE_KPP_DOUBLEDIFF
       WRITE(standardMessageUnit,'(A)') 'PARAM_exclude_doublediff=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_exclude_doublediff=0'
#endif
#ifdef ALLOW_KPP_VERTICALLY_SMOOTH
       WRITE(standardMessageUnit,'(A)')
     &   'PARAM_vertically_smooth_ri=1'
#else
       WRITE(standardMessageUnit,'(A)')
     &   'PARAM_vertically_smooth_ri=0'
#endif
C      1DMIX-034: compile-time ALLOW_SALT_PLUME (see PARAM_useSALT_PLUME
C      above for the runtime flag; KPPParameters' NotImplementedError
C      guard fires on either being true).
#ifdef ALLOW_SALT_PLUME
       WRITE(standardMessageUnit,'(A)') 'PARAM_allow_salt_plume=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_allow_salt_plume=0'
#endif
C      1DMIX-034 part 2: PlumeMethod/Npower (SALT_PLUME.h, read from
C      data.salt_plume by salt_plume_readparms.F) and the compile-time
C      SALT_PLUME_VOLUME variant flag -- needed so KPPParameters'
C      narrowed NotImplementedError guard can tell a ported
C      configuration (PlumeMethod=1, Npower=0, SALT_PLUME_VOLUME unset)
C      from an unported one, instead of firing/skipping unconditionally
C      on use_salt_plume alone. PlumeMethod/Npower are only declared
C      under ALLOW_SALT_PLUME (SALT_PLUME.h); SALT_PLUME_VOLUME is
C      checked unconditionally like SALT_PLUME_SPLIT_BASIN elsewhere in
C      this file, since it degrades to "undefined" (0) whenever
C      SALT_PLUME_OPTIONS.h was never even included.
#ifdef ALLOW_SALT_PLUME
       WRITE(standardMessageUnit,'(A,I10)')
     &   'PARAM_PlumeMethod=',PlumeMethod
       WRITE(standardMessageUnit,'(A,I10)')
     &   'PARAM_Npower=',Npower
#endif
#ifdef SALT_PLUME_VOLUME
       WRITE(standardMessageUnit,'(A)') 'PARAM_salt_plume_volume=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_salt_plume_volume=0'
#endif
C      Shortwave penetration
#ifdef SHORTWAVE_HEATING
       WRITE(standardMessageUnit,'(A)') 'PARAM_shortwave_heating=1'
#else
       WRITE(standardMessageUnit,'(A)') 'PARAM_shortwave_heating=0'
#endif
C      selectPenetratingSW/swatt: needed by bldepth whenever
C      SHORTWAVE_HEATING is active (KPPMIX direct "I" argument;
C      see INPUT_SWATT dump below for the swatt profile itself)
       WRITE(standardMessageUnit,'(A,I10)')
     &   'PARAM_selectPenetratingSW=',selectPenetratingSW
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_MODEL_PARAMETERS_END ====='

C      --- GRID GEOMETRY ---
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_GRID_GEOMETRY ====='
       WRITE(standardMessageUnit,'(A)') 'GRID_GEOM_HEADER,k,drF,rF,rC'
       DO k = 1, Nr
        WRITE(standardMessageUnit,101) 'GRID_GEOM',k,
     &    drF(k), rF(k), rC(k)
       ENDDO
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_GRID_GEOMETRY_END ====='

C      --- DATA FORMAT HEADERS ---
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_DATA_HEADERS ====='
       WRITE(standardMessageUnit,'(A)')
     &   'INPUT_STATE_HEADER,i,j,k,theta,salt,u,v'
C      1DMIX-013 fix: the WRITE(202,...) block below used to emit
C      surfaceForcingT/surfaceForcingS (MITgcm's own already-converted,
C      already-sign-adjusted internal forcing terms, computed by
C      external_forcing_surf.F:221-234) into the columns this header
C      calls "q_net"/"fw_flux". Every downstream consumer (this file's
C      own comment below, scripts/parse_mitgcm_split.py, and
C      1D_Mixing_Model/KPP/kpp_core_driver.py::_compute_surface_forcing's
C      documented [W/m^2]/[kg/m^2/s] raw-flux contract) instead expects
C      genuinely raw MITgcm state. Now emits the true raw fields
C      (Qnet, Qsw, EmPmR, saltFlux -- all plain FFIELDS.h COMMON-block
C      state, already in scope via the #include above, no new dummy
C      arguments needed) under explicit *_raw names so this format is
C      never confused with the old (buggy) q_net/fw_flux semantics.
C      Qsw was already raw before this fix (Qsw(i,j,bi,bj) written
C      verbatim) and is kept as Qsw_raw for header-naming consistency.
       WRITE(standardMessageUnit,'(A)')
     &   'INPUT_FORCING_HEADER,i,j,ustar,bo,bosol,tau_x,tau_y,'
     &   //'Qnet_raw,Qsw_raw,EmPmR_raw,saltFlux_raw'
       WRITE(standardMessageUnit,'(A)')
     &   'INPUT_CORIOLIS_HEADER,i,j,f'
C      1DMIX-034 part 2: boplume(1)/SPDepth, needed for the salt-plume
C      contribution to bfsfc (kpp_forcing_surf.F/salt_plume_frac.F).
C      Guarded exactly like INPUT_SWATT below, emitting 0.0/0.0 when
C      ALLOW_SALT_PLUME is not compiled in.
       WRITE(standardMessageUnit,'(A)')
     &   'INPUT_SALTPLUME_HEADER,i,j,boplume,sp_depth'
       WRITE(standardMessageUnit,'(A)')
     &   'INPUT_SWATT_HEADER,i,j,k,swatt'
       WRITE(standardMessageUnit,'(A)')
     &   'OUTPUT_MIXING_HEADER,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat'
       WRITE(standardMessageUnit,'(A)')
     &   'OUTPUT_DIAGNOSTICS_HEADER,i,j,k,shear_sq,buoy_freq_sq,Ri,'
     &   //'dVsq,Ritop'
       WRITE(standardMessageUnit,'(A)')
     &   'OUTPUT_HBL_HEADER,i,j,hbl'
       WRITE(standardMessageUnit,'(A)')
     &   '===== KPP_DATA_HEADERS_END ====='
      ENDIF

C     Output header for this timestep
      WRITE(standardMessageUnit,'(A)')
     &  '===== KPP_VALIDATION_START ====='
      WRITE(standardMessageUnit,'(A,I10,A,I3,A,I3)')
     &  'TIMESTEP=',myIter,',BI=',bi,',BJ=',bj

C     Loop over all grid points and output data
      DO j = jMin, jMax
       DO i = iMin, iMax

C       Skip land points (maskC = 0 at surface)
        IF ( maskC(i,j,1,bi,bj) .EQ. 0. ) CYCLE

C       --- OUTPUT INPUTS ---
C       Grid and state variables (cell centers)
        DO k = 1, Nr
C        Format: INPUT_STATE,i,j,k,theta,salt,uvel,vvel
         WRITE(standardMessageUnit,200) 'INPUT_STATE',i,j,k,
     &     theta(i,j,k,bi,bj),
     &     salt(i,j,k,bi,bj),
     &     uVel(i,j,k,bi,bj),
     &     vVel(i,j,k,bi,bj)
        ENDDO

C       Surface forcing (scalar per column)
C       Capture the exact values KPP uses: ustar, bo, bosol computed by KPP_FORCING_SURF
C       Plus wind stress (tau/rho, unaffected by 1DMIX-013: mass2rUnit=
C       recip_rhoConst here, so surfaceForcingU/V ARE genuinely tau/rho,
C       external_forcing_surf.F:222,224) and the true raw heat/freshwater
C       state (1DMIX-013 fix -- see INPUT_FORCING_HEADER comment above).
C       1DMIX-022 fix: tau_x/tau_y are captured T-grid-centered (averaged
C       with the i+1/j+1 neighbor), matching KPP_FORCING_SURF's own real
C       ustar computation exactly (kpp_forcing_surf.F:191-208: ustar is
C       derived from surfForcU(i,j)+surfForcU(i+1,j), NOT surfForcU(i,j)
C       alone -- surfaceForcingU/V live on the U/V-grid, one point per
C       cell edge, and must be averaged onto the T-grid center where KPP
C       diagnoses ustar/hbl/etc). Dumping the raw single-edge value here
C       (as before) is fine only when the wind-stress field barely varies
C       between adjacent columns (true of this project's earlier 1D/
C       idealized captures) -- for a real, spatially-varying field
C       (global_oce_latlon's Trenberth climatology) it produced systematic
C       ustar errors up to ~7%, which the 1% _validate_forcing_computation
C       gate then reported as a false port defect.
C       Format: INPUT_FORCING,i,j,ustar,bo,bosol,tau_x,tau_y,
C               Qnet_raw,Qsw_raw,EmPmR_raw,saltFlux_raw
        WRITE(standardMessageUnit,202) 'INPUT_FORCING',i,j,
     &    ustar(i,j),
     &    bo(i,j),
     &    bosol(i,j),
     &    0.5 _d 0*(surfaceForcingU(i,j,bi,bj)+
     &              surfaceForcingU(i+1,j,bi,bj)),
     &    0.5 _d 0*(surfaceForcingV(i,j,bi,bj)+
     &              surfaceForcingV(i,j+1,bi,bj)),
     &    Qnet(i,j,bi,bj),
     &    Qsw(i,j,bi,bj),
     &    EmPmR(i,j,bi,bj),
     &    saltFlux(i,j,bi,bj)

C       Coriolis parameter
        WRITE(standardMessageUnit,203) 'INPUT_CORIOLIS',i,j,
     &    fCori(i,j,bi,bj)

C       Salt-plume surface haline buoyancy forcing and its penetration
C       depth (1DMIX-034 part 2). boplume(i,j,1) is KPP_FORCING_SURF's
C       own already-computed local array (kpp_forcing_surf.F:262-273,
C       the SALT_PLUME_VOLUME-undef branch -- confirmed #undef for
C       seaice_obcs, SALT_PLUME_OPTIONS.h:24); SaltPlumeDepth is the
C       existing per-column field already passed verbatim as KPPMIX's
C       own SPDepth argument above (kpp_routines.F:32,116,391-392).
C       Both purely additive captures -- no new Fortran computation.
C       Guarded exactly like INPUT_SWATT below: boplume is only
C       DECLARED under #ifdef ALLOW_SALT_PLUME (this file, ~line 205),
C       so referencing it unconditionally would be a hard compile
C       failure for any experiment (e.g. vermix) that does not compile
C       salt plume in.
#ifdef ALLOW_SALT_PLUME
        WRITE(standardMessageUnit,211) 'INPUT_SALTPLUME',i,j,
     &    boplume(i,j,1),
     &    SaltPlumeDepth(i,j,bi,bj)
#else
        WRITE(standardMessageUnit,211) 'INPUT_SALTPLUME',i,j,
     &    0. _d 0,
     &    0. _d 0
#endif

C       Shortwave attenuation profile (KPPMIX direct "I" argument
C       whenever SHORTWAVE_HEATING is active; Nrp1 levels, from
C       FFIELDS.h, already included above).
C       1DMIX-028 fix: SWFrac3D is only DECLARED in FFIELDS.h under
C       #ifdef SHORTWAVE_HEATING (model/inc/FFIELDS.h:144-153) -- this
C       WRITE previously referenced it unconditionally, a latent bug
C       invisible for every experiment tested so far (all had
C       SHORTWAVE_HEATING defined) but a hard compile failure
C       ("no IMPLICIT type") for vermix's own stock KPP config, which
C       doesn't define it. Guard with the same #ifdef this file already
C       uses at line ~1099 for PARAM_shortwave_heating; write zero swatt
C       when undefined, matching export_kpp_input_for_fortran.py's own
C       existing all-zero fallback for this exact case.
#ifdef SHORTWAVE_HEATING
        DO k = 1, Nr+1
         WRITE(standardMessageUnit,208) 'INPUT_SWATT',i,j,k,
     &     SWFrac3D(i,j,k,bi,bj)
        ENDDO
#else
        DO k = 1, Nr+1
         WRITE(standardMessageUnit,208) 'INPUT_SWATT',i,j,k,
     &     0. _d 0
        ENDDO
#endif

C       --- OUTPUT OUTPUTS ---
C       1DMIX-033 fix: OUTPUT_DIAGNOSTICS (shear_sq, buoy_freq_sq, Ri,
C       dVsq, Ritop) is written in its OWN full loop, unconditionally
C       for every level. Previously this write sat inside the SAME loop
C       as OUTPUT_MIXING and was skipped by OUTPUT_MIXING's own
C       all-zero truncation check (below) -- but shsq/dbloc/dVsq/Ritop
C       are raw physical quantities that exist at every level regardless
C       of whether KPP's mixing *enhancement* (visc_az/diff_kz/ghat) has
C       decayed to exactly zero there. Confirmed on a real capture
C       (vermix, 1DMIX-032/033): whenever OUTPUT_MIXING truncates at the
C       very first level (a genuinely common case for a shallow-hbl,
C       weakly-forced column), the old single-loop code wrote ZERO
C       OUTPUT_DIAGNOSTICS lines for the entire column/timestep, even
C       though the real shsq/dbloc/Ritop were nonzero and physically
C       reasonable throughout. This split is purely additive: it adds
C       OUTPUT_DIAGNOSTICS lines that were previously silently dropped
C       and does not change a single byte of any line that was already
C       written (same formats 207, same values, same per-level order).
        DO k = 1, Nr
C        Format: OUTPUT_DIAGNOSTICS,i,j,k,shear_sq,buoy_freq_sq,
C                richardson,dVsq,Ritop
C        Compute Richardson number: Ri = N²/S²
C        Avoid division by zero
C        dVsq, Ritop are dumped verbatim (unmodified KPPMIX "I"-only
C        arguments) so the standalone-subroutine harness can replay
C        KPPMIX exactly without recomputing them via STATEKPP/
C        KPP_FORCING_SURF.
         IF ( shsq(i,j,k) .GT. 1.0E-20 ) THEN
          WRITE(standardMessageUnit,207) 'OUTPUT_DIAGNOSTICS',i,j,k,
     &      shsq(i,j,k),
     &      dbloc(i,j,k),
     &      dbloc(i,j,k) / shsq(i,j,k),
     &      dVsq(i,j,k),
     &      Ritop(i,j,k)
         ELSE
          WRITE(standardMessageUnit,207) 'OUTPUT_DIAGNOSTICS',i,j,k,
     &      shsq(i,j,k),
     &      dbloc(i,j,k),
     &      0.0D0,
     &      dVsq(i,j,k),
     &      Ritop(i,j,k)
         ENDIF

C        1DMIX-025: kppRib is bldepth's own real bulk Richardson number
C        (kpp_routines.F, now exposed via KPPMIX's new output argument
C        added for this issue) -- dumped unconditionally alongside the
C        diagnostics above so the Python port's own Rib profile can be
C        compared directly against real ground truth, distinguishing a
C        genuine port defect from inert near-zero-denominator noise.
         WRITE(standardMessageUnit,209) 'OUTPUT_RIB',i,j,k,
     &     kppRib(i,j,k)
        ENDDO

C       KPP mixing coefficients (at interfaces, k=1..Nr)
C       1DMIX-035 fix: previously stopped at the first level where all 4
C       outputs happened to be exactly zero, on the assumption that KPP's
C       enhancement is genuinely background/zero below where it truncates.
C       That assumption is false: pkg/kpp/kpp_routines.F::Ri_iwmix adds
C       the background viscosity/diffusivity (viscArNr(1)/diffusKzS/T)
C       UNCONDITIONALLY at every real interior level regardless of KPP's
C       own shear/convective enhancement (kpp_routines.F:1206-1208), so
C       KPPviscAz/KPPdiffKzS/KPPdiffKzT can only be legitimately zero at
C       the surface face (k=1, Ri_iwmix's own explicit diffus(i,0,*)=0
C       convention) or at/below the real seafloor (maskC-masked) -- never
C       at a genuinely wet interior level. Confirmed directly on
C       global_oce_latlon's full-year capture: this early-exit fired at
C       the very first level (where ghat alone can legitimately be zero,
C       satisfying the old all-4-zero check) for 83.5% of wet columns,
C       discarding every deeper level's real, nonzero background-floor
C       data. Same bug class as 1DMIX-033's OUTPUT_DIAGNOSTICS fix; same
C       fix here: write unconditionally for every level. KPPviscAz/
C       KPPdiffKzS/KPPdiffKzT/KPPghat are already the final maskC-masked
C       arrays, so this is exactly as safe as 1DMIX-033's fix -- no
C       existing correctly-written line changes, only previously-
C       discarded real data is now written.
        DO k = 1, Nr
C        Format: OUTPUT_MIXING,i,j,k,visc_az,diff_kz_s,diff_kz_t,ghat
         WRITE(standardMessageUnit,204) 'OUTPUT_MIXING',i,j,k,
     &     KPPviscAz(i,j,k,bi,bj),
     &     KPPdiffKzS(i,j,k,bi,bj),
     &     KPPdiffKzT(i,j,k,bi,bj),
     &     KPPghat(i,j,k,bi,bj)
        ENDDO

C       Boundary layer depth (scalar per column)
        WRITE(standardMessageUnit,205) 'OUTPUT_HBL',i,j,
     &    KPPhbl(i,j,bi,bj)

C       1DMIX-025: bldepth's final (post-LimitHblStable-clamp) surface
C       buoyancy forcing, exposed via KPPMIX's new kppBfsfc output
C       argument -- lets the Python port's own bfsfc/hlimit computation
C       be checked against real ground truth for weakly-forced columns
C       where bfsfc is extremely close to zero (see 1DMIX-025's seaice_obcs
C       finding).
        WRITE(standardMessageUnit,210) 'OUTPUT_BFSFC',i,j,
     &    kppBfsfc(i,j)

       ENDDO
      ENDDO

C     Output footer for this timestep
      WRITE(standardMessageUnit,'(A)')
     &  '===== KPP_VALIDATION_END ====='

C     Format specifications (ES25.16 = 17 significant digits, exact for a double; 1DMIX-069)
 101  FORMAT(A,',',I3,3(',',ES25.16))
 200  FORMAT(A,3(',',I3),4(',',ES25.16))
 202  FORMAT(A,2(',',I3),9(',',ES25.16))
 203  FORMAT(A,2(',',I3),',',ES25.16)
 204  FORMAT(A,3(',',I3),4(',',ES25.16))
 205  FORMAT(A,2(',',I3),',',ES25.16)
 206  FORMAT(A,2(',',I3),',',I3)
 207  FORMAT(A,3(',',I3),5(',',ES25.16))
 208  FORMAT(A,3(',',I3),',',ES25.16)
 209  FORMAT(A,3(',',I3),',',ES25.16)
 210  FORMAT(A,2(',',I3),',',ES25.16)
 211  FORMAT(A,2(',',I3),2(',',ES25.16))

      RETURN
      END

#endif
