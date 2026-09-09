import { existsSync } from "node:fs";
import process from "node:process";
import { chromium } from "playwright";

const localCandidates = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
];

export function launchChromium(options = {}) {
  const configured = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  const executablePath = configured || localCandidates.find(existsSync);
  return chromium.launch({ ...options, ...(executablePath ? { executablePath } : {}) });
}
