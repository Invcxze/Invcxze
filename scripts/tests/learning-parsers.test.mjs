import test from "node:test";
import assert from "node:assert/strict";
import { parseMimo, parseSololearn, parseStepik } from "../learning-parsers.mjs";

test("parses the public Stepik profile in Russian", () => {
  assert.deepEqual(parseStepik("0 дней без перерыва 4 дня без перерыва (макс.) 366 задач решено", ["https://stepik.org/cert/2346827"]), {
    solved: 366,
    current_streak: 0,
    best_streak: 4,
    certificates: 1,
    certificate_links: ["https://stepik.org/cert/2346827"],
  });
});

test("parses SoloLearn English metrics", () => {
  assert.deepEqual(parseSololearn("Level 12 24,680 XP 8 courses completed 17 day streak Certificates: 6"), {
    xp: 24680,
    level: 12,
    streak: 17,
    courses: 8,
    certificates: 6,
  });
});

test("parses the public SoloLearn profile without streak data", () => {
  assert.deepEqual(parseSololearn("Vladislav Khramenko 25 850 XP Russia · Уровень 16 Сертификаты"), {
    xp: 25850,
    level: 16,
    streak: null,
    courses: null,
    certificates: null,
  });
});

test("parses Mimo English metrics", () => {
  assert.deepEqual(parseMimo("Current path Python Developer 68% complete 91 lessons completed 12 day streak"), {
    streak: 12,
    completed: 91,
    progress: 68,
    path: "Python Developer",
  });
});
