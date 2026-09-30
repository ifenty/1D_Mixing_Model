#!/usr/bin/env python3
"""1DMIX-054: write pickup_ggl90.0000000001.{data,meta} for the CONSTRUCTED lab_sea + GGL90 runs.

Why it is needed: the stock lab_sea run restarts from `pickup.0000000001` (startTime=3600 s,
deltaT=3600 s => nIter0=1). With nIter0 != 0, GGL90_INIT_VARIA calls GGL90_READ_PICKUP, which
requires `pickup_ggl90.<nIter0>` and STOPs if it is missing (KPP is diagnostic and has no pickup,
so the stock input never had one). The file written here holds the TKE field a cold start would
have: GGL90_INIT_VARIA sets GGL90TKE = GGL90TKEmin * maskC (non-IDEMIX branch), and data.ggl90 leaves
GGL90TKEmin at its MITgcm default 1.E-11. Dry points are also filled with 1.E-11 (they are never
used; the port replay skips land columns and marks below-seafloor levels NaN).
Format = what GGL90_READ_PICKUP reads: one 3-D record (Nr=23 levels of the 20x16 global grid), float64
big-endian (prec = precFloat64), x fastest, k slowest; the .meta mirrors pickup.0000000001.meta.
usage: make_pickup_ggl90.py <output_dir>
"""
import struct
import sys
from pathlib import Path

NX, NY, NR = 20, 16, 23
TKEMIN = 1.0e-11   # MITgcm default GGL90TKEmin (pkg/ggl90/ggl90_readparms.F)

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / 'pickup_ggl90.0000000001.data').write_bytes(struct.pack('>%dd' % (NX * NY * NR), *([TKEMIN] * (NX * NY * NR))))
(out / 'pickup_ggl90.0000000001.meta').write_text(
    " nDims = [   2 ];\n"
    " dimList = [\n"
    "    20,    1,   20,\n"
    "    16,    1,   16\n"
    " ];\n"
    " dataprec = [ 'float64' ];\n"
    " nrecords = [    23 ];\n"
    " timeStepNumber = [          1 ];\n"
    " timeInterval = [  3.600000000000E+03 ];\n"
    " nFlds = [    1 ];\n"
    " fldList = {\n"
    " 'GGL90TKE'\n"
    " };\n")
print('wrote', out / 'pickup_ggl90.0000000001.data', NX * NY * NR * 8, 'bytes')
