import { createNote, deleteNote, listNotes, searchNotes } from "./api.js";

const notesEl = document.querySelector("#notes");
const form = document.querySelector("#note-form");
const statusEl = document.querySelector("#status");
const searchEl = document.querySelector("#search");
const submitButton = form.querySelector('button[type="submit"]');
let searchVersion = 0;

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

function render(notes) {
  notesEl.replaceChildren();

  if (!notes.length) {
    const empty = makeElement("p", searchEl.value.trim()
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
  const query = searchEl.value.trim();
  render(query ? await searchNotes(query) : await listNotes());
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  submitButton.disabled = true;
  setStatus("Saving…");
  const payload = {
    title: document.querySelector("#title").value,
    body: document.querySelector("#body").value,
    tags: document.querySelector("#tags").value.split(",").map(tag => tag.trim()).filter(Boolean),
  };
  try {
    await createNote(payload);
    form.reset();
    await refresh();
    setStatus("Note saved.", "success");
  } catch (error) {
    setStatus(error.message || "Could not save note.", "error");
  } finally {
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
    await refresh();
    setStatus("Note deleted.", "success");
  } catch (error) {
    deleteButton.disabled = false;
    setStatus(error.message || "Could not delete note.", "error");
  }
});

searchEl.addEventListener("input", async () => {
  const currentVersion = ++searchVersion;
  setStatus("Searching…");
  try {
    const query = searchEl.value.trim();
    const notes = query ? await searchNotes(query) : await listNotes();
    if (currentVersion !== searchVersion) return;
    render(notes);
    setStatus(query ? "Search complete." : "Notes loaded.", "success");
  } catch (error) {
    if (currentVersion !== searchVersion) return;
    setStatus(error.message || "Could not search notes.", "error");
  }
});

setStatus("Loading notes…");
refresh().catch(error => {
  setStatus(error.message || "Could not load notes.", "error");
});
