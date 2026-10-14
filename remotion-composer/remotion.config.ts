import { Config } from "@remotion/cli/config";

// Offline / restricted-network environments cannot download Remotion's
// Chrome Headless Shell. Point Remotion at a locally installed browser instead.
if (process.env.REMOTION_BROWSER_EXECUTABLE) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER_EXECUTABLE);
}
