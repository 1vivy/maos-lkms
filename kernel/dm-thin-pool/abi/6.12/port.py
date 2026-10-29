# SPDX-License-Identifier: GPL-2.0-only
"""ABI declaration for the 6.12 kernel line.

The 6.12 profile is ``verified``: this directory's vendored ``src/`` tree was
proven against the 6.12 branch and stays byte-identical.  There is no edit
programme and no shared port function runs.  This file names the one branch
the proof covers, so another 6.12 branch fails staging instead of inheriting
a proof that does not apply.
"""

LINE = "6.12"
PROFILE = "verified"
VERIFIED_BRANCH = "android16-6.12"

# The verified profile stages the vendored tree and applies no edits.
SOURCES = ()
