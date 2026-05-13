# Contract: Keyboard shortcuts

The workspace registers a single keyboard listener (`shortcuts.js`) that fires only when the
shell is loaded and focus is within the workspace root (`<main id="workspace">`). Inside form
fields and `<dialog>` overlays, all bindings except `Escape` are disabled so user typing flows
unimpeded.

On macOS `Cmd` is the modifier; on Windows/Linux `Ctrl`. The table uses `Mod` to mean both.

## Bindings (v1)

| Keys | Action | Where active |
|---|---|---|
| `Mod+K` | Open command palette overlay | Workspace |
| `Esc` | Close active overlay (palette, help, dialog), or unfocus active form field | Anywhere |
| `Mod+W` | Close active tab | Workspace, not inside form fields |
| `Mod+Shift+W` | Close all tabs (then auto-open default graph tab per FR-021) | Workspace |
| `Alt+ArrowRight` | Switch to next tab (wraps) | Workspace |
| `Alt+ArrowLeft` | Switch to previous tab (wraps) | Workspace |
| `Alt+1` … `Alt+9` | Jump to tab N (1-indexed) | Workspace |
| `Alt+Shift+ArrowRight` | Move active tab right in the bar | Workspace |
| `Alt+Shift+ArrowLeft` | Move active tab left in the bar | Workspace |
| `[` | Collapse/expand the navigation tree | Workspace, not inside form fields |
| `Mod+/` | Open help overlay listing all bindings | Workspace |
| `?` | Same as `Mod+/` — convention from Gmail/GitHub | Workspace, not inside form fields |

## Palette-internal bindings

Active only while the command palette is open:

| Keys | Action |
|---|---|
| `ArrowDown` / `ArrowUp` | Move highlight |
| `Enter` | Activate highlighted result in the active tab |
| `Mod+Enter` | Activate highlighted result in a new tab |
| `Esc` | Close the palette |
| `Tab` | Cycle through filter chips (Objects / Workspace actions) |

## Browser-default overrides

`Mod+W` and `Alt+1..9` override real browser bindings. The contract:
- The shell calls `preventDefault()` on the corresponding `KeyboardEvent`.
- The `?` help overlay documents this explicitly.
- The override is in force ONLY while the workspace has focus; clicking out (e.g., into the URL
  bar) restores native behaviour.

`Mod+T` (new browser tab) and `Mod+Shift+T` (reopen closed tab) are explicitly NOT overridden.
Opening new workspace tabs uses the tree, the command palette, or middle-click — never `Mod+T`.

## Configuration

Bindings are fixed in v1 (per spec assumptions). A future preference pane MAY surface a JSON
binding map; the registry in `shortcuts.js` is structured so the binding table is data, not
code, in anticipation of that change.

## Accessibility

- Every interactive surface that has a shortcut MUST also be reachable by mouse and by `Tab`
  focus — shortcuts are accelerators, not the only path.
- The help overlay (`Mod+/` or `?`) is itself a focusable, screen-reader-friendly `<dialog>` so
  screen-reader users can discover the bindings.
- Tab bar uses `role="tablist"` with arrow-key roving focus per WAI-ARIA Tabs Pattern.
