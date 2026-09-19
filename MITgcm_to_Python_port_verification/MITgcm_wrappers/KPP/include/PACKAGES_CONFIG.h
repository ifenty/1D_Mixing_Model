C $Header$
C $Name$

C     Package flags for KPP wrapper
C     Simplified for standalone KPP - only enable KPP package

#ifndef PACKAGES_CONFIG_H
#define PACKAGES_CONFIG_H

#include "CPP_EEOPTIONS.h"

C     Enable KPP package
#define ALLOW_KPP

C     Disable all other packages
#undef ALLOW_TIMEAVE
#undef ALLOW_DIAGNOSTICS
#undef ALLOW_MNEC
#undef ALLOW_GENERIC_ADVDIFF
#undef ALLOW_AUTODIFF
#undef ALLOW_SEAICE
#undef ALLOW_OBCS
#undef ALLOW_EXCH2
#undef ALLOW_THSICE
#undef ALLOW_SALT_PLUME
#undef ALLOW_SHELFICE
#undef ALLOW_GGL90

#endif /* PACKAGES_CONFIG_H */
