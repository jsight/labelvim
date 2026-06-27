# LabelVim manual testing guide

A repeatable script for exercising the GUI by hand. Use it twice:

1. **Now (baseline)** — run it against the current app to record what works and
   what's already buggy.
2. **After the canvas rewrite** (Phase 2: gur-c5ee6b23.3–.6) — run the same
   steps to confirm no regressions and that the SSOT refactor fixed the
   save/restore/edit/undo drift.

Record results in the checklist at the bottom (copy it per run).

## Golden fixtures

`examples/golden/` contains pre-made annotation files over the bundled
`examples/*.jpg` images (all 640×426). Each targets a scenario:

| Image | File | Scenario |
|-------|------|----------|
| 33924 | `33924.json` | one rectangle (simplest render) |
| 33931 | `33931.json` | three rectangles, different categories (list/select/delete) |
| 33932 | `33932.json` | one pentagon polygon (polygon render + vertex edit) |
| 33933 | `33933.json` | mixed rectangle + polygon |
| 33939 | `33939.json` | edge cases: tiny, flush-to-border, near-full, two overlapping |
| 33946 | `33946.json` | six rectangles (object-list + undo stress) |

Every golden file round-trips exactly through `AnnotationDocument`, so
**load → save should not change the file** (see Test 2).

## Launch & setup

```bash
uv run python main.py
# verbose logs (the old print() traces) if you want them:
LABELVIM_LOG_LEVEL=DEBUG uv run python main.py
```

1. On the task dialog, pick **Object Detection** (rectangles) or **Segmentation**
   (polygons) depending on the test.
2. **Open Dir** → select `examples/`.
3. **Save Dir** → select `examples/golden/`.
4. Click an image in the file list (e.g. `33931`). Its golden annotations should
   appear.

## Controls (vim-like, modal)

| Key | Action |
|-----|--------|
| `I` | enter **EDIT** mode (status shows EDIT) |
| `Esc` | back to **NORMAL** mode |
| `H` `J` `K` `L` / arrows | move the cursor left/down/up/right |
| `Shift` + move | larger step |
| `C` | create/start a box at the cursor |
| `Enter` | complete the current move/placement |
| Buttons | Open Dir, Save Dir, Save, Edit Object, Delete Annotation, Clear Annotation, zoom in/out/fit, next/previous, Export |

## Tests

### Test 1 — Load & render (gate: USER draw/edit/undo, render half)
For each golden image 33924, 33931, 33932, 33933, 33939, 33946:
- Select it and confirm the shapes draw in the right places with the right
  category labels in the object list.
- 33939: confirm the border rect (top-left), the tiny rect, the near-full rect,
  and the two overlapping rects all render.

**Expect:** every shape visible; counts match the table.

### Test 2 — Save / reload round-trip (gate: USER save/reload)
1. Load `33931`, make **no changes**, click **Save**.
2. In a terminal: `git diff examples/golden/33931.json` → **expect no diff**.
3. Switch to another image and back (or reopen the dir); confirm shapes reload
   identically.
4. Now move/edit a shape, Save, navigate away and back → the change persists and
   re-save is stable.

**Expect:** unchanged save is a no-op diff; edits persist exactly.

### Test 3 — Draw a new rectangle (gate: USER draw/edit/undo)
1. Object Detection mode, load `33924`.
2. Press `C`, position with `hjkl`, press `C`/`Enter` to place the opposite
   corner (per current create flow), confirm a new box appears and is added to
   the object list.

**Expect:** new rectangle drawn and listed.

### Test 4 — Draw a polygon (Segmentation mode)
1. Segmentation mode, load `33932`.
2. Add a few polygon points and close the polygon.

**Expect:** polygon created; existing pentagon still intact.

### Test 5 — Edit a vertex (gate: USER draw/edit/undo)
1. Load `33932`, press `I` (EDIT), select the polygon, move a vertex with the
   cursor, `Enter` to commit, `Esc` to exit.

**Expect:** only the dragged vertex moves; shape otherwise intact.

### Test 6 — Move a whole shape
1. Load `33931`, select a rectangle, move it, commit.

**Expect:** the whole rectangle translates; others unchanged.

### Test 7 — Undo / redo (gate: USER draw/edit/undo)
1. Load `33946` (6 rects). Delete one, move another, draw a new one.
2. Undo repeatedly back to the original 6; then redo forward.

**Expect:** each undo reverts exactly one change; redo replays it; final state
matches start after full undo.

### Test 8 — Delete / clear
1. Load `33931`, select a rect, **Delete Annotation** → it's removed from canvas
   and list. **Clear Annotation** → all gone. Undo restores.

### Test 9 — Export (gate: USER COCO/mask export)
1. With `examples/golden` as save dir, use **Export** for COCO JSON, and mask
   export with/without image.
2. Open the output; confirm bboxes/polygons/categories and image dimensions
   (640×426) match.

## Results checklist (copy per run)

```
Run: [ baseline | post-rewrite ]   Date: __________   Commit: __________

Test 1 Load & render        [ pass | fail ]  notes:
Test 2 Save/reload round    [ pass | fail ]  notes:
Test 3 Draw rectangle       [ pass | fail ]  notes:
Test 4 Draw polygon         [ pass | fail ]  notes:
Test 5 Edit vertex          [ pass | fail ]  notes:
Test 6 Move shape           [ pass | fail ]  notes:
Test 7 Undo/redo            [ pass | fail ]  notes:
Test 8 Delete/clear         [ pass | fail ]  notes:
Test 9 Export               [ pass | fail ]  notes:
```

Anything that fails in the **baseline** run is a known starting bug, not a
regression — note it so we can confirm the rewrite fixes (or at least doesn't
worsen) it.
