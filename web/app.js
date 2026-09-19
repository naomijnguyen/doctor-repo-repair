import { createNote, deleteNote, listNotes, searchNotes } from "./api.js";
import { clearSubmittedDraft, createReadGeneration } from "./request-state.js";

const notesEl = document.querySelector("#notes");
const form = document.querySelector("#note-form");
const statusEl = document.querySelector("#status");
const searchEl = document.querySelector("#search");
const submitButton = form.querySelector('button[type="submit"]');
const titleEl = document.querySelector("#title");
const bodyEl = document.querySelector("#body");
const tagsEl = document.querySelector("#tags");
const readGeneration = createReadGeneration();
let savePending = false;

function setStatus(message, kind = "info") {
  statusEl.textContent = message;
  statusEl.dataset.kind = kind;
}

function makeElement(tagName, text, className) {
  const element = document.createElement(tagName);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function render(notes, query = searchEl.value.trim()) {
  notesEl.replaceChildren();

  if (!notes.length) {
    const empty = makeElement("p", query
      ? "No notes match that search."
      : "No notes yet. Add the first one above.", "empty-state");
    notesEl.append(empty);
    return;
  }

  for (const note of notes) {
    const article = document.createElement("article");
    article.dataset.id = note.id;

    const heading = makeElement("h2", note.title);
    const timestamp = makeElement("time", "Created just now");
    const createdAt = note.createdAt;
    if (createdAt) {
      const date = new Date(createdAt);
      if (!Number.isNaN(date.getTime())) {
        timestamp.dateTime = createdAt;
        timestamp.textContent = date.toLocaleString();
      }
    }

    article.append(heading, timestamp);
    if (note.body) article.append(makeElement("p", note.body));

    if (note.tags.length) {
      const tags = makeElement("ul", "", "tags");
      tags.setAttribute("aria-label", "Tags");
      for (const tag of note.tags) tags.append(makeElement("li", tag));
      article.append(tags);
    }

    const actions = makeElement("div", "", "note-actions");
    const deleteButton = makeElement("button", "Delete", "delete");
    deleteButton.type = "button";
    deleteButton.setAttribute("aria-label", `Delete ${note.title}`);
    actions.append(deleteButton);
    article.append(actions);
    notesEl.append(article);
  }
}

async function refresh() {
  const generation = readGeneration.begin();
  const query = searchEl.value.trim();
  let notes;
  try {
    notes = query ? await searchNotes(query) : await listNotes();
  } catch (error) {
    if (!readGeneration.isCurrent(generation)) return null;
    throw error;
  }
  if (!readGeneration.isCurrent(generation)) return null;
  render(notes, query);
  return query;
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (savePending) return;
  savePending = true;
  submitButton.disabled = true;
  setStatus("Saving…");
  const submitted = {
    title: titleEl.value,
    body: bodyEl.value,
    tags: tagsEl.value,
  };
  const payload = {
    title: submitted.title,
    body: submitted.body,
    tags: submitted.tags.split(",").map(tag => tag.trim()).filter(Boolean),
  };
  try {
    await createNote(payload);
    clearSubmittedDraft({ title: titleEl, body: bodyEl, tags: tagsEl }, submitted);
    setStatus("Note saved.", "success");
    try {
      await refresh();
    } catch {
      setStatus("Note saved, but the list could not refresh.", "error");
    }
  } catch (error) {
    setStatus(error.message || "Could not save note.", "error");
  } finally {
    savePending = false;
    submitButton.disabled = false;
  }
});

notesEl.addEventListener("click", async event => {
  const deleteButton = event.target.closest(".delete");
  if (!deleteButton) return;
  const article = deleteButton.closest("article");
  deleteButton.disabled = true;
  setStatus("Deleting…");
  try {
    await deleteNote(article.dataset.id);
    article.remove();
    setStatus("Note deleted.", "success");
    try {
      await refresh();
    } catch {
      setStatus("Note deleted, but the list could not refresh.", "error");
    }
  } catch (error) {
    deleteButton.disabled = false;
    setStatus(error.message || "Could not delete note.", "error");
  }
});

searchEl.addEventListener("input", async () => {
  setStatus("Searching…");
  try {
    const query = await refresh();
    if (query === null) return;
    setStatus(query ? "Search complete." : "Notes loaded.", "success");
  } catch (error) {
    setStatus(error.message || "Could not search notes.", "error");
  }
});

setStatus("Loading notes…");
refresh().catch(error => {
  setStatus(error.message || "Could not load notes.", "error");
});
