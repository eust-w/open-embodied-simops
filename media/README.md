# Project Introduction Media

This video is a project introduction, not simulator execution footage. It uses
actual local workbench screenshots, original workflow/schema diagrams and an
original synthesized tone track. No robot footage, sample results, external
stock media, cloned voice, or benchmark numbers are fabricated.

The workbench screenshots show a clean local environment with no GPU job run.
Catalog availability labels are not independently verified runtime health.
Portrait frames crop the same desktop screenshot rather than pretending to be
a mobile interface. Chinese and English copy are burned in; SRT files are also
produced. No narration is included.

## Rebuild

Capture the actual local UI into `output/source/generate.jpg`, `datasets.jpg`
and `training.jpg`. Do not replace the screenshots with mocked UI data.

```sh
python -m pip install pillow
python media/render_intro.py --font /path/to/locally-installed-CJK-font
```

FFmpeg must be on PATH. The font must permit your intended use; it is not
redistributed. Generated videos and private publication evidence stay ignored
under `media/output/`. Original screenshots and code belong to this project;
any embedded third-party software remains under its upstream license.

Outputs: 1920×1080 and 1080×1920 H.264/AAC MP4, matching covers, bilingual SRT,
and a SHA-256 manifest. Inspect every scene and verify the repository's public
visibility before using open-source launch copy.
