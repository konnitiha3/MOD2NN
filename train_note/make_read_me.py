import os
import glob
import re

files = glob.glob("**/*" ,recursive=True)
files.sort()
notes = []
for f in files:
    if re.match(r'.*ipynb', f):
        notes.append(f)

md = ""
for note in notes:
    md = md + "### " + os.path.splitext(note)[0] + "\n"
    md = md + "[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/konnitiha3/MOD2NN/blob/master/train_note/" + note + ")\n"

with open("README.md", mode="w") as f:
    f.write(md)