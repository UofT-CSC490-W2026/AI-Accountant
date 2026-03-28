function pad(value: number) {
  return value.toString().padStart(2, "0");
}

export function formatIsoDateTime(value: string) {
  const normalized = value.trim();

  const dateOnlyMatch = normalized.match(/^(\d{4}-\d{2}-\d{2})$/);

  if (dateOnlyMatch) {
    return `${dateOnlyMatch[1]} 00:00:00`;
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return formatClockTime(date);
}

export function formatClockTime(value: Date) {
  return [
    `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`,
    `${pad(value.getHours())}:${pad(value.getMinutes())}:${pad(value.getSeconds())}`,
  ].join(" ");
}
