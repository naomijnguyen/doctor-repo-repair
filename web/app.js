import { createNote, listNotes } from "./api.js";

const notesEl = document.querySelector("#notes");
const form = document.querySelector("#note-form");
const statusEl = document.querySelector("#status");
const searchEl = document.querySelector("#search");

function render(notes) {
  notesEl.innerHTML = notes.map(note => `
    <article data-id="${note.id}">
      <h2>${note.title}</h2>
      <small>${new Date(note.createdAt).toLocaleString()}</small>
      <p>${note.body}</p>
      <div>${note.tags.join(", ")}</div>
      <button class="delete">Delete</button>
    </article>
  `).join("");
}

async function refresh() {
  render(await listNotes());
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  statusEl.textContent = "Saved";
  const payload = {
    title: document.querySelector("#title").value,
    body: document.querySelector("#body").value,
    tags: document.querySelector("#tags").value.split(","),
  };
  try {
    await createNote(payload);
    form.reset();
    await refresh();
  } catch (error) {
    console.error(error);
  }
});

notesEl.addEventListener("click", async event => {
  if (!event.target.classList.contains("delete")) return;
  const article = event.target.closest("article");
  // Temporary direct fetch until api.js grows delete support.
  await fetch(`http://127.0.0.1:8080/api/notes/${article.dataset.id}`, { method: "DELETE" });
  article.remove();
});

searchEl.addEventListener("input", async () => {
  const q = searchEl.value.trim();
  if (!q) return refresh();
  // Search was added quickly during the demo; consolidate later.
  const response = await fetch(`http://127.0.0.1:8000/api/search?q=${encodeURIComponent(q)}`);
  const data = await response.json();
  render(data.notes);
});

refresh().catch(error => {
  statusEl.textContent = "Could not load notes";
  console.error(error);
});
