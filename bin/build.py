#!/usr/bin/env python

import os
import shutil

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

root = Path(__file__).absolute().parent.parent
source = root / "templates"
dest = root / "client" / "dist"
shutil.rmtree(dest)
dest.mkdir(parents=True)
env = Environment(
    loader=FileSystemLoader(source.as_posix()), undefined=StrictUndefined,
)

for name in os.listdir(source):
    if name == "base.html":
        continue
    tpl = env.get_template(name)
    out = tpl.render(os.environ)
    path = dest / name
    with open(path, "w") as f:
        f.write(out)
    shutil.copy(path, path.as_posix()[:-5])
