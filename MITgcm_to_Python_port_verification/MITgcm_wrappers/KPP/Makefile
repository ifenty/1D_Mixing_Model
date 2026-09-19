# Makefile for KPP standalone wrapper
#
# Builds kpp_wrapper executable from MITgcm KPP sources

# Compiler
FC = gfortran

# Compiler flags
# MITgcm uses fixed-form Fortran (.F files)
FFLAGS = -fdefault-real-8 -fconvert=big-endian -O2 -g
FFLAGS += -ffixed-line-length-132  # Allow longer lines in fixed form
FFLAGS += -fallow-argument-mismatch  # For gfortran 10+
FFLAGS += -cpp  # Enable C preprocessor
FFLAGS += '-D_d=d'  # MITgcm double precision kind specifier (converts _d 0 → d 0 → d0)

# Include directories
INCLUDES = -I./include -I./mitgcm_src

# Source directories
SRCDIR = src
MITGCMDIR = mitgcm_src

# Use our simple pressure_for_eos instead of full MITgcm version
# (Full version requires totPhiHyd and other infrastructure)

# Object directory
OBJDIR = build

# Target executable
TARGET = kpp_wrapper

# Source files
WRAPPER_SRC = $(SRCDIR)/kpp_wrapper.F
STUB_SRC = $(SRCDIR)/stubs.F
GRID_SRC = $(SRCDIR)/ini_wrapper_grid.F $(SRCDIR)/set_wrapper_grid.F
PRESSURE_SRC = $(SRCDIR)/pressure_for_eos_simple.F

# MITgcm source files
MITGCM_SRCS = \
	$(MITGCMDIR)/kpp_calc.F \
	$(MITGCMDIR)/kpp_readparms.F \
	$(MITGCMDIR)/kpp_output_validation.F \
	$(MITGCMDIR)/kpp_routines.F \
	$(MITGCMDIR)/kpp_init_fixed.F \
	$(MITGCMDIR)/kpp_forcing_surf.F \
	$(MITGCMDIR)/find_rho.F \
	$(MITGCMDIR)/find_alpha.F \
	$(MITGCMDIR)/ini_eos.F \
	$(MITGCMDIR)/swfrac.F

# All source files (Note: pressure_for_eos from SRCDIR not MITGCMDIR)
SRCS = $(WRAPPER_SRC) $(STUB_SRC) $(GRID_SRC) $(PRESSURE_SRC) $(MITGCM_SRCS)

# Object files
OBJS = $(patsubst %.F,$(OBJDIR)/%.o,$(notdir $(SRCS)))

# Default target
all: $(TARGET)

# Create build directory
$(OBJDIR):
	mkdir -p $(OBJDIR)

# Link executable
$(TARGET): $(OBJDIR) $(OBJS)
	$(FC) $(FFLAGS) $(OBJS) -o $(TARGET)
	@echo "Successfully built $(TARGET)"

# Compile wrapper source
$(OBJDIR)/kpp_wrapper.o: $(WRAPPER_SRC)
	$(FC) $(FFLAGS) $(INCLUDES) -c $< -o $@

# Compile stub source
$(OBJDIR)/stubs.o: $(STUB_SRC)
	$(FC) $(FFLAGS) $(INCLUDES) -c $< -o $@

# Compile grid initialization sources
$(OBJDIR)/%.o: $(SRCDIR)/%.F
	$(FC) $(FFLAGS) $(INCLUDES) -c $< -o $@

# Compile MITgcm sources
$(OBJDIR)/%.o: $(MITGCMDIR)/%.F
	$(FC) $(FFLAGS) $(INCLUDES) -c $< -o $@

# Clean build artifacts
clean:
	rm -rf $(OBJDIR) $(TARGET)

# Phony targets
.PHONY: all clean

# Display help
help:
	@echo "KPP Wrapper Makefile"
	@echo "--------------------"
	@echo "Targets:"
	@echo "  all     - Build kpp_wrapper executable (default)"
	@echo "  clean   - Remove build artifacts"
	@echo "  help    - Display this help message"
