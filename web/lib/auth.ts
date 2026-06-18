// Username-based auth on top of Supabase.
//
// Supabase Auth only logs in by email, so each account gets a permanent
// synthetic email derived from its username: `<username>@<AUTH_EMAIL_DOMAIN>`.
// The username is what the player types; the synthetic email is internal
// plumbing they never see. Username uniqueness comes for free from Supabase's
// email-uniqueness guarantee.
//
// An optional real recovery email is collected at signup and stored in
// user_metadata. The flow that actually sends a reset link to it is added later
// (see docs); storing it now means existing accounts work once that ships.

// Domain for synthetic login emails. Never receives mail, so it just needs to
// be a syntactically valid domain. Overridable so it can match deployments.
export const AUTH_EMAIL_DOMAIN =
  process.env.NEXT_PUBLIC_AUTH_EMAIL_DOMAIN || "users.mirofish.app";

export const USERNAME_MIN = 3;
export const USERNAME_MAX = 20;

// Lowercase and trim. Does not strip invalid characters — validateUsername
// reports those so the user can fix them rather than having input silently
// mangled.
export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase();
}

// Returns an error message if the username is invalid, or null if it's valid.
// Operates on the normalized form.
export function validateUsername(raw: string): string | null {
  const username = normalizeUsername(raw);
  if (username.length < USERNAME_MIN) {
    return `Username must be at least ${USERNAME_MIN} characters`;
  }
  if (username.length > USERNAME_MAX) {
    return `Username must be at most ${USERNAME_MAX} characters`;
  }
  if (!/^[a-z0-9_]+$/.test(username)) {
    return "Username can only use letters, numbers, and underscores";
  }
  return null;
}

// Maps a username to its synthetic Supabase login email. Assumes the username
// has already passed validateUsername.
export function usernameToEmail(raw: string): string {
  return `${normalizeUsername(raw)}@${AUTH_EMAIL_DOMAIN}`;
}
