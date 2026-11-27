"""Generate the full synthetic dataset.

Usage:
    python -m datagen.generate            # writes to ./data
    python -m datagen.generate --out tmp  # writes somewhere else
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

from . import config as C
from .docs import write_docs
from .export import Exporter
from .simulate import Simulator


def main(out: Path, seed: int = C.SEED) -> None:
    t0 = time.time()
    for sub in ("raw", "reference", "eval", "docs"):
        shutil.rmtree(out / sub, ignore_errors=True)
    truth = Simulator(seed).run()
    frames = truth.frames()
    Exporter(frames, out, seed).run()
    write_docs(out)
    print(f"batches={len(frames['batches'])} assemblies={len(frames['assemblies'])} "
          f"test_attempts={len(frames['attempts'])} work_orders={len(frames['work_orders'])} "
          f"deviations={len(frames['deviations'])} ({time.time() - t0:.1f}s) -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=C.SEED)
    args = ap.parse_args()
    main(Path(args.out), args.seed)
