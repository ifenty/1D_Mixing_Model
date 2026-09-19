Test Case Summary
==================

Grid Configuration
------------------
Nr: 12
Total depth: 140.00 m
drF range: 2.0 to 30.0 m

Initial State
-------------
Theta: 22.00 to 8.80 degC
Salt: 34.60 to 35.20 psu
U velocity: 0.140 to 0.008 m/s
V velocity: 0.070 to 0.005 m/s

Surface Forcing
---------------
Momentum (tau_x, tau_y): (0.100, 0.040) m^2/s^2
Net heat flux: -120.0 W/m^2
Shortwave flux: 45.0 W/m^2
Freshwater flux: 0.000000 m/s
Surface T forcing: -2.919832e-05 degC*m/s

Physical Parameters
-------------------
Gravity: 9.81 m/s^2
Reference density: 1029.0 kg/m^3
Heat capacity: 3994.0 J/(kg*K)
Coriolis: 1.00e-04 1/s

Python KPP Port Output
----------------------
KPPhbl: 14.77 m
Max KPPviscAz: 2.859713e-01 m^2/s
Max KPPdiffKzT: 2.845920e-01 m^2/s
Max KPPdiffKzS: 2.845920e-01 m^2/s
Max KPPghat: 3.293333e+00 m/s^2

Files
-----
inputs.npz          - Numpy arrays of all inputs
outputs_kpp_port.npz - Expected outputs from Python KPP port
input.bin           - Binary input for MITgcm wrapper
README.txt          - This file

To test MITgcm wrapper
----------------------
cd ../../
ln -sf test_case_001/input.bin input.bin
./kpp_wrapper > test_case_001/wrapper_output.csv

Then compare wrapper_output.csv with outputs_kpp_port.npz
