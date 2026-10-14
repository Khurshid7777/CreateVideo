import { Config } from "@remotion/cli/config";

// Sandboxed machines (CI, cloud sessions) may block Remotion's browser download.
// Point REMOTION_BROWSER_EXECUTABLE at a local Chrome or Chromium headless shell instead.
if (process.env.REMOTION_BROWSER_EXECUTABLE) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER_EXECUTABLE);
}
