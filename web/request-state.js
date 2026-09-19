export function createReadGeneration() {
  let generation = 0;
  return {
    begin() {
      generation += 1;
      return generation;
    },
    isCurrent(candidate) {
      return candidate === generation;
    },
  };
}

export function clearSubmittedDraft(fields, submitted) {
  for (const [name, element] of Object.entries(fields)) {
    if (element.value === submitted[name]) element.value = "";
  }
}
