# Third-Party Notices

This repository vendors a local copy of MINIMA and selected dependencies under
`third_party/MINIMA`.

MINIMA is distributed under the Apache-2.0 license. See:

- `third_party/MINIMA/LICENSE`
- `third_party/MINIMA/README.md`

MINIMA model weights are not tracked by this repository. Place them under
`third_party/MINIMA/weights/` for local or server-side experiments.

The vendored tree also contains components under their own licenses, including:

- LightGlue: Apache-2.0, except for optional SuperPoint material that is not
  redistributed here.
- LoFTR: Apache-2.0.
- XoFTR: Apache-2.0.
- RoMa: MIT.
- Glue Factory: Apache-2.0, excluding its optional `gluefactory_nonfree`
  implementations, which are not redistributed here.

The Magic Leap SuperGlue/SuperPoint code carries restrictive noncommercial and
non-redistribution terms. UAV-TAlign does not redistribute these files. They
are not used by the journal-scale MINIMA-RoMa/UAV-TAlign evaluation path.
Users who intentionally enable an optional branch requiring these components
must obtain them from the upstream project and comply with its license.

No top-level UAV-TAlign license overrides a third-party license or grants rights
to third-party model weights.
