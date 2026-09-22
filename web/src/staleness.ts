/** Whether the examples baked into this page are older than the Python on disk right now.
 *
 * `pysources.ts` is generated and gitignored, so a `git pull` that adds or edits an example
 * never touches it, and a `vite preview` can go on serving a `dist/` built days earlier with
 * neither one saying so. `GENERATED_AT`, frozen into the bundle at generate time, is compared
 * here against `/__bench/generated-at` - a route `vite.config.ts`'s `bench:staleness` plugin
 * answers by walking the same two source trees live, in both `npm run dev` and `npm run
 * preview`. A static deploy has no such route behind it, so the fetch fails there and this
 * says nothing, rather than ever guessing.
 */
import { GENERATED_AT } from "./generated/pysources";

const ENDPOINT = "/__bench/generated-at";

/** True once `newestOnDisk` is later than `generatedAt` - the comparison alone, so a test can
 * call it without a server. */
export const stale = (generatedAt: number, newestOnDisk: number): boolean => newestOnDisk > generatedAt;

/** What to say about it, plainly and short enough for the status bar pill itself: which
 * command fixes it. The fuller story - why, and that the server needs restarting too - is
 * `STALE_HINT`, for a title tooltip beside it. */
export const STALE_MESSAGE = "stale examples - run npm --prefix web run generate";

/** The longer version of `STALE_MESSAGE`, for a tooltip: what happened and everything the
 * one-line command leaves out. */
export const STALE_HINT =
  "the examples in this app are older than the files on disk - " +
  "run `npm ci --prefix web && npm --prefix web run generate`, then restart the dev or " +
  "preview server, to see what was merged";

function newestFrom(body: unknown): number | null {
  if (typeof body !== "object" || body === null || !("newest" in body)) return null;
  const found = (body as { newest: unknown }).newest;
  return typeof found === "number" ? found : null;
}

/** Ask the running server what is newest on disk, and say whether this bundle is behind it.
 * Resolves `false` whenever the question can't be answered - no such route, a network error -
 * so a production deploy with nothing behind it is silent rather than wrongly flagged. */
export async function bundleStale(fetchImpl: typeof fetch = fetch): Promise<boolean> {
  try {
    const res = await fetchImpl(ENDPOINT);
    if (!res.ok) return false;
    const newest = newestFrom(await res.json());
    return newest !== null && stale(GENERATED_AT, newest);
  } catch {
    return false;
  }
}
