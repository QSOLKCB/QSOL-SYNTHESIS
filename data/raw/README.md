# Raw discovery data

This directory is the default destination for network collectors.

Files here are **discovery snapshots**, not curated synthesis inputs. Running a collector must not silently rewrite data/projects.json, data/publications.json, data/relationships.json, or the paper.

Typical commands:

~~~bash
python scripts/collect_github.py
python scripts/collect_zenodo.py
~~~

Review raw diffs and promote supported records manually into the curated corpus.
