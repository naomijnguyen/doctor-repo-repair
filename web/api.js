const API_BASE = "http://127.0.0.1:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.error?.message || payload.message || message;
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) return null;
  return response.json();
}

export async function listNotes() {
  return (await request("/api/notes")).notes;
}

export async function createNote(payload) {
  return request("/api/notes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteNote(noteId) {
  return request(`/api/notes/${encodeURIComponent(noteId)}`, {
    method: "DELETE",
  });
}

export async function searchNotes(query) {
  return (await request(`/api/search?q=${encodeURIComponent(query)}`)).notes;
}
