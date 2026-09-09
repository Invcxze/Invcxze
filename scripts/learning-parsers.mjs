function compact(value) {
  return String(value ?? "").replace(/[\u00a0\u202f]/g, " ").replace(/\s+/g, " ").trim();
}

function integer(value) {
  if (value == null) return null;
  const normalized = String(value).replace(/[^\d]/g, "");
  return normalized ? Number.parseInt(normalized, 10) : null;
}

function firstNumber(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return integer(match[1]);
  }
  return null;
}

function firstText(text, patterns) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return compact(match[1]);
  }
  return null;
}

function assertAuthenticated(text, service) {
  const normalized = compact(text).toLowerCase();
  const loginOnly = [
    "log in to continue",
    "sign in to continue",
    "войдите, чтобы продолжить",
    "create an account or log in",
  ];
  if (loginOnly.some((needle) => normalized.includes(needle))) {
    throw new Error(`${service} session is no longer authenticated`);
  }
}

export function parseStepik(text, certificateLinks = []) {
  const body = compact(text);
  const solved = firstNumber(body, [
    /(\d[\d\s]*)\s+(?:problems?|задач(?:и|у)?|заданий)\s+(?:solved|решено)/i,
    /(?:problems? solved|решено задач)\s*[:—-]?\s*(\d[\d\s]*)/i,
  ]);
  const bestStreak = firstNumber(body, [
    /(\d+)\s+(?:day|days|день|дня|дней)\s+(?:in a row\s+\(max\.?\)|без перерыва\s+\(макс\.?\))/i,
    /(?:longest|max(?:imum)?|макс(?:имальная)?)\s+(?:streak|серия)\s*[:—-]?\s*(\d+)/i,
  ]);
  const currentStreak = firstNumber(body, [
    /(\d+)\s+(?:day|days|день|дня|дней)\s+(?:in a row|без перерыва)(?!\s+\(max)/i,
    /(?:current streak|текущая серия)\s*[:—-]?\s*(\d+)/i,
  ]);

  if (solved == null) throw new Error("Stepik solved-problems count was not found");
  return {
    solved,
    current_streak: currentStreak,
    best_streak: bestStreak,
    certificates: certificateLinks.length,
    certificate_links: certificateLinks,
  };
}

export function parseSololearn(text) {
  assertAuthenticated(text, "SoloLearn");
  const body = compact(text);
  const xp = firstNumber(body, [
    /(\d{1,3}(?:[ ,.\u00a0\u202f]\d{3})+|\d+)\s*XP\b/i,
    /\bXP\s*[:—-]\s*(\d{1,3}(?:[ ,.\u00a0\u202f]\d{3})+|\d+)/i,
  ]);
  const level = firstNumber(body, [
    /(?:level|уровень)\s*[:—-]?\s*(\d+)/i,
    /\bLVL\.?\s*(\d+)/i,
  ]);
  const streak = firstNumber(body, [
    /(\d+)\s*(?:day|days|день|дня|дней)\s*(?:streak|серия)/i,
    /(?:streak|серия)\s*[:—-]?\s*(\d+)/i,
  ]);
  const courses = firstNumber(body, [
    /(\d+)\s*(?:courses? completed|completed courses?|пройденных курсов)/i,
    /(?:courses? completed|completed courses?|пройдено курсов|заверш[её]нные курсы)\s*[:—-]\s*(\d+)/i,
  ]);
  const certificates = firstNumber(body, [
    /(?:certificates?|сертификаты?)\s*[:—-]\s*(\d+)/i,
  ]);

  if ([xp, level, streak, courses, certificates].every((value) => value == null)) {
    throw new Error("SoloLearn metrics were not found; the page layout may have changed");
  }
  return { xp, level, streak, courses, certificates };
}

export function parseMimo(text) {
  assertAuthenticated(text, "Mimo");
  const body = compact(text);
  const streak = firstNumber(body, [
    /(\d+)\s*(?:day|days|день|дня|дней)\s*(?:streak|серия)/i,
    /(?:streak|серия)\s*[:—-]?\s*(\d+)/i,
  ]);
  const completed = firstNumber(body, [
    /(\d+)\s*(?:lessons?|exercises?|уроков|упражнений)\s*(?:completed|done|пройдено|выполнено)/i,
    /(?:lessons?|exercises?|уроков|упражнений)\s+(?:completed|done|пройдено|выполнено)\s*[:—-]\s*(\d+)/i,
  ]);
  const progress = firstNumber(body, [
    /(\d{1,3})\s*%\s*(?:complete|completed|progress|пройдено|прогресс)/i,
    /(?:progress|прогресс)\s*[:—-]?\s*(\d{1,3})\s*%/i,
  ]);
  const path = firstText(body, [
    /(?:current path|learning path|текущий путь)\s*[:—-]?\s*([^|•]{2,80}?)(?=\s+\d{1,3}\s*%|$)/i,
  ]);

  if ([streak, completed, progress, path].every((value) => value == null)) {
    throw new Error("Mimo metrics were not found; the page layout may have changed");
  }
  return { streak, completed, progress, path };
}

export { compact };
