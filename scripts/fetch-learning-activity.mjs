import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { launchChromium } from "./browser.mjs";
import { parseStepik } from "./learning-parsers.mjs";

const outputPath = path.resolve(process.argv[2] ?? "data/learning-activity.json");
const now = new Date().toISOString();

async function readPrevious() {
  try {
    return JSON.parse(await fs.readFile(outputPath, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return { version: 1, platforms: {} };
    throw error;
  }
}

function safeError(error) {
  return String(error?.message ?? error).replace(/https?:\/\/\S+/g, "[url]").slice(0, 180);
}

function retained(previous, status, error = null) {
  return {
    ...(previous ?? {}),
    status,
    checked_at: now,
    ...(error ? { error: safeError(error) } : {}),
  };
}

async function pageText(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForLoadState("networkidle", { timeout: 20_000 }).catch(() => {});
  await page.locator("body").waitFor({ state: "visible", timeout: 20_000 });
  return page.locator("body").innerText({ timeout: 20_000 });
}

async function collectStepik(browser, previous) {
  const context = await browser.newContext({ locale: "en-US" });
  try {
    const page = await context.newPage();
    const text = await pageText(page, "https://stepik.org/users/634260482/profile");
    const certificateLinks = await page
      .locator('a[href*="/cert/"]')
      .evaluateAll((links) => [...new Set(links.map((link) => link.href))]);
    return {
      name: "Stepik",
      url: "https://stepik.org/users/634260482/profile",
      status: "ok",
      checked_at: now,
      ...parseStepik(text, certificateLinks),
    };
  } catch (error) {
    return retained(previous, "stale", error);
  } finally {
    await context.close();
  }
}

async function fetchText(url, headers = {}) {
  const response = await fetch(url, {
    headers: {
      Accept: "text/html,application/json",
      "User-Agent": "invcxze-profile-learning-card/1.0",
      ...headers,
    },
  });
  if (!response.ok) throw new Error(`Request failed with HTTP ${response.status}`);
  return response.text();
}

async function collectSololearn(previous) {
  try {
    const url = "https://www.sololearn.com/en/profile/24797541";
    const html = await fetchText(url);
    const initialMatch = html.match(/window\.initialData\s*=\s*(\{.*?\});/s);
    if (!initialMatch) throw new Error("SoloLearn public page token was not found");
    const initialData = JSON.parse(initialMatch[1]);
    const publicToken = initialData.jwtAuthPublicToken;
    if (!publicToken) throw new Error("SoloLearn public token was not found");

    const apiUrl = "https://api2.sololearn.com/v2/userinfo/v3/profile/24797541?sections=1,3,7,8";
    const payload = JSON.parse(
      await fetchText(apiUrl, { Authorization: `Bearer ${publicToken}` }),
    );
    const user = payload.userDetails;
    if (!user || Number(user.id) !== 24797541) {
      throw new Error("SoloLearn public profile response was incomplete");
    }
    const certificates = Array.isArray(payload.certificates) ? payload.certificates : [];
    return {
      name: "SoloLearn",
      url,
      status: "ok",
      checked_at: now,
      xp: Number(user.xp),
      level: Number(user.level),
      followers: Number(user.followers),
      following: Number(user.following),
      certificates: certificates.length,
      certificate_names: certificates.map((certificate) => certificate.name),
      certificate_links: certificates.map((certificate) => certificate.shareUrl),
    };
  } catch (error) {
    return retained(previous, "stale", error);
  }
}

const previous = await readPrevious();
const browser = await launchChromium({ headless: true });
let platforms;
try {
  const stepik = await collectStepik(browser, previous.platforms?.stepik);
  const sololearn = await collectSololearn(previous.platforms?.sololearn);
  const mimo = { ...(previous.platforms?.mimo ?? {}), status: "snapshot" };
  platforms = { stepik, sololearn, mimo };
} finally {
  await browser.close();
}

const result = { version: 1, generated_at: now, platforms };
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");

for (const [id, platform] of Object.entries(platforms)) {
  console.log(`${id}: ${platform.status}`);
}
