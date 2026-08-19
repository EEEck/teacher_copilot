const BACKEND_TRUE_ALIASES = new Set(["1", "on", "t", "true", "y", "yes"]);

/** Match Pydantic's accepted truthy strings for the backend BETA_ENABLED bool. */
export function parseBetaEnabled(value: string | undefined): boolean {
  return value !== undefined && BACKEND_TRUE_ALIASES.has(value.toLowerCase());
}
