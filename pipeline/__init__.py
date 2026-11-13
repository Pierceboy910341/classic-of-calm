"""Classic of Calm — notebook-02 post-production pipeline (CPU only).

Modules
-------
qa        automated checks on candidate wavs -> JSON report + score; mp3 previews
layer     optional CC0 instrument ornaments + shared reverb
master    gentle EQ / compression-lite / loudness normalisation / tail fades
compile   sequencing (selection.json or Camelot+BPM auto order), crossfades, chapters
visuals   seamless loop video, caption bars, compilation.mp4, thumbnail.png
metadata  youtube.txt (title, description, chapters, tracklist, bestiary card, tags)
run_week  one entry point: ``python -m pipeline.run_week --week 2026-W47 ...``

Binding spec: docs/05-system-design.md; audio rules: docs/03-music-bible.md.
"""

__version__ = "0.1.0"
