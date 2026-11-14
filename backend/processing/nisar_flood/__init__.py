"""NISAR flood rhythm (N1, N2, N4, N5) for Tanaw.

Pipeline: CMR search -> windowed GCOV read -> per-pass water rule ->
permanent-water mask -> flood rhythm / flooded vegetation / polarization view
-> PNG + GeoTIFF + manifest exports served by ``app/nisar_api.py``.

Nothing in this package fabricates NISAR observations. Data built from the
synthetic fixtures in ``synthetic.py`` carries ``dataKind == "synthetic"``.
"""

CODE_VERSION = "tanaw-nisar-flood/1.0"
