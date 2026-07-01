# Optional Login (Guest Mode) + Remove Recovery Email

**Date:** 2026-07-01
**Status:** Approved (design)

## Goal

Let people use the simulation without logging in. Guests can create worlds, run
simulations, and use every interactive feature — they simply can't persist saves
until they sign in. Also remove the recovery-email feature entirely.

## Background / Key Constraint

The backend already gates **only** the `/saves` endpoints behind auth
(`UserIdDep` in `engine/main.py`). All world-creation and simulation endpoints
are auth-free, and worlds live in server RAM keyed by `world_id`
(`engine/state.py`). Therefore **no backend changes are required** — a guest can
already exercise the full simulation; they only lack a token for `/saves`.

This is a frontend-only change in `web/`.

## Scope

In scope:
1. Remove the recovery-email field and all supporting code/comments.
2. Add a guest ("play without an account") path.
3. Gate saving behind sign-in, with an inline sign-in modal that preserves the
   in-progress simulation.

Out of scope: backend auth changes, changes to how worlds are stored, any change
to the simulation engine.

## Component Changes

### 1. Remove recovery email

- `web/components/AuthScreen.tsx` (form): delete the `recoveryEmail` state, the
  recovery-email `<input>` block (signup only), and remove `recovery_email` from
  the `signUp` `options.data` payload. Signup metadata becomes
  `{ username: normalizeUsername(username) }`.
- `web/lib/auth.ts`: remove the paragraph of comments describing the optional
  recovery email (lines ~9-11). No functional code lives there for recovery
  email, so nothing else changes.

### 2. Reusable `<AuthForm>`

Extract the auth form (username + password inputs, mode toggle, submit/error/info
handling — everything currently inside `AuthScreen`'s `<form>` and the mode
toggle) into a new `AuthForm` component so it can render both full-screen and
inside a modal.

- New: `web/components/AuthForm.tsx`
  - Props: `{ onSuccess?: () => void; compact?: boolean }`.
  - Contains all the auth logic currently in `AuthScreen.submit` (login/signup,
    username validation, synthetic email, "already taken" handling, the
    signIn-after-signUp fallback).
  - On successful login/signup it calls `onSuccess?.()`. (The global
    `onAuthStateChange` in `page.tsx` remains the source of truth for session
    state; `onSuccess` is only a UI hook so callers can close a modal.)
  - `compact` toggles minor layout (used in the save modal vs. full screen). If
    `compact` adds no real value during implementation, it may be dropped.
- `web/components/AuthScreen.tsx` becomes a thin wrapper: the title/logo block,
  then `<AuthForm />`, then the guest button (below).

### 3. Guest entry

- `AuthScreen` gains an `onGuest: () => void` prop and renders a
  **"PLAY WITHOUT AN ACCOUNT"** button below the auth form (styled like the
  existing ghost/secondary buttons).
- `web/app/page.tsx`:
  - Add `const [guest, setGuest] = useState(false)`.
  - Render `<AuthScreen onGuest={() => { setGuest(true); setPhase("saves"); }} />`.
  - Define a derived `canProceed = !!session || guest`.
  - `reset()` sets `setPhase(canProceed ? "saves" : "auth")`.
  - Bootstrap `getSession()`: unchanged for the session case; when no session,
    stay on `auth` (guest is false initially).
  - `onAuthStateChange`: when a session arrives, `setGuest(false)`, set token,
    and move to `saves` only if `prev === "auth"` (unchanged), so an in-progress
    guest sim is preserved when they sign in mid-game. When session is null, only
    force `auth` + `reset()` on an actual `SIGNED_OUT` event — do **not** kick a
    guest (who never had a session) back to auth.

### 4. Saves screen — guest variant

`web/components/SavesScreen.tsx` gains a `guest: boolean` prop (passed from
`page.tsx`) and an `onSignIn: () => void` prop.

- When `guest`: skip the `api.listSaves()` call entirely (it would 401); render
  the existing empty state plus a hint line: "Playing as guest — sign in to save
  your progress."
- Header button: when `guest`, show **"SIGN IN"** (calls `onSignIn`, which sets
  `phase = "auth"`; guest stays true so world state is preserved) instead of
  "SIGN OUT".
- "+ NEW SIMULATION" behaves identically for guests.

### 5. Guest SAVE → inline sign-in modal

The title-bar SAVE button (`page.tsx`) stays visible for guests.

- When `!session` (guest) and SAVE is clicked, open a **sign-in-to-save** modal
  instead of `SaveModal`.
- New: `web/components/SaveSignInModal.tsx` (or a small branch inside the
  existing modal area): a modal shell (matching existing modal styling) with a
  heading like "Sign in to save your simulation" and an embedded `<AuthForm>`.
- On `onSuccess`, close the sign-in modal and open the normal `SaveModal`. The
  world remains in server RAM under the same `world_id`; the now-present auth
  token lets `createSave` succeed.
- `page.tsx` state: reuse a single modal-intent flag, e.g.
  `showSaveModal: false | "auth" | "save"`, or two booleans. When SAVE is
  clicked: `session ? open SaveModal : open SaveSignInModal`.

## Data Flow

- Guest chooses "play without an account" → `guest=true`, phase `saves`
  (empty, guest variant).
- Guest starts a new simulation → identical to logged-in flow; all
  world/simulate calls succeed without a token.
- Guest clicks SAVE → sign-in-to-save modal → embedded `AuthForm` signs in →
  `onAuthStateChange` sets the session/token and clears guest → sign-in modal
  closes → `SaveModal` opens → `createSave` persists the existing `world_id`.

## Error Handling

- Guest never calls `/saves` list/create/etc. until authenticated, so no 401s in
  the normal guest path.
- Auth errors inside the embedded `AuthForm` render exactly as they do today
  (existing error/info UI moves with the extracted form).
- If a guest's world was evicted from server RAM (LRU cap) before they sign in
  and save, `createSave` sends the still-in-memory `world`/`result` from client
  state in the request body (per current `createSave` signature), so eviction of
  the working copy does not block the save.

## Testing

Manual verification (no automated frontend tests exist in this repo):
1. Load app, click "play without an account" → lands on empty guest saves screen
   with the guest hint and a "SIGN IN" button.
2. Start a new simulation as guest, run at least one day → works end to end.
3. Click SAVE as guest → sign-in-to-save modal appears with the auth form.
4. Sign in / register in that modal → modal closes, SaveModal opens, save
   succeeds, and the save appears after reload while logged in.
5. From the guest saves screen, click "SIGN IN" → auth screen; sign in →
   normal saves screen with existing saves.
6. Signup form no longer shows a recovery-email field; a new account is created
   without recovery metadata.
7. Existing logged-in flow (sign in → saves → load/save/delete/sign out)
   unchanged.

## YAGNI notes

- No "convert guest world to a save automatically" beyond the inline sign-in →
  SaveModal path.
- `compact` prop on `AuthForm` is optional polish; drop if it adds no value.
- No migration for existing `recovery_email` metadata — it simply stops being
  read or written.
