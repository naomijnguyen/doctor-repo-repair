const API_BASE = "http://127.0.0.1:8000";

export async function listNotes() {
  const response = await fetch(`${API_BASE}/api/notes`);
  if (!response.ok) throw new Error("Could not load notes");
  return (await response.json()).notes;
}

export async function createNote(payload) {
  const response = await fetch(`${API_BASE}/api/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Could not save note");
  return response.json();
}
