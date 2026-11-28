// ADDED [PROMPT #36]: journal swaps, autosave, citation panels and keyboard focus.
(() => {
  const job = document.querySelector("#journal-job");
  const live = document.querySelector("#journal-live");
  const write = document.querySelector('[data-testid="write-journal"]');
  const saves = new WeakMap();
  const openers = new WeakMap();

  function updateAnchor() {
    document.getElementById("first-unsupported")?.removeAttribute("id");
    const mark = document.querySelector("#journal-body mark.unsupported");
    if (mark) mark.id = "first-unsupported";
  }

  function showDraft(template) {
    const body = document.getElementById("journal-body");
    const fresh = template.content.querySelector("#journal-body");
    // Insert refreshed siblings around the original editors so focus, selection,
    // pending timers and in-flight saves all stay attached to the same nodes.
    for (const child of Array.from(body.children)) {
      if (!child.matches("[data-journal-editor], [data-dirty]")) child.remove();
    }
    let cursor = body.firstElementChild;
    for (const child of Array.from(fresh.children)) {
      const kept = child.id && document.getElementById(child.id);
      if (kept && kept.parentElement === body) {
        cursor = kept.nextElementSibling;
      } else {
        body.insertBefore(child, cursor);
        htmx.process(child);
      }
    }
    live.textContent = job.querySelector("[data-draft-announcement]").textContent;
    job.replaceChildren();
    write.textContent = "Regenerate";
    write.disabled = false;
    updateAnchor();
    // CHANGED [PROMPT #36]: review fix, never pull focus out of a kept editor (JR-S4).
    if (!document.activeElement?.closest("[data-journal-editor]")) {
      [...body.querySelectorAll("h2")].find((h) => !h.closest("[data-journal-editor]"))?.focus();
    }
  }

  document.addEventListener("input", event => {
    const editor = event.target.closest("[data-journal-editor]");
    if (editor) editor.toggleAttribute("data-dirty", event.target.value !== event.target.defaultValue);
  });

  document.addEventListener("htmx:beforeRequest", event => {
    const {elt, xhr} = event.detail;
    if (elt === write) {
      write.disabled = true;
      write.dataset.previous = write.textContent;
      write.textContent = "Generating… your edits are kept.";
      live.textContent = "";
    }
    if (elt.matches("textarea[hx-put]")) {
      const editor = elt.closest("[data-journal-editor]");
      saves.set(elt, {xhr, text: elt.value});
      editor.querySelector("[role=status]").textContent = "Saving…";
    }
    if (elt.matches("button.cite")) {
      openers.set(document.getElementById(elt.getAttribute("aria-controls")), elt);
    }
  });

  document.addEventListener("htmx:confirm", event => {
    const button = event.detail.elt;
    // Skip duplicate input/blur requests before hx-sync can abort the active save.
    if (button.matches("textarea[hx-put]")) {
      const pending = saves.get(button);
      if (button.value === (pending ? pending.text : button.defaultValue)) event.preventDefault();
      return;
    }
    if (!button.matches("[data-editor-done]")) return;
    const editor = button.closest("[data-journal-editor]");
    const field = editor.querySelector("textarea");
    if (editor.hasAttribute("data-dirty") || saves.has(field)) {
      event.preventDefault();
      editor.dataset.closeAfterSave = "";
      if (saves.get(field)?.text !== field.value) htmx.trigger(field, "blur");
    }
  });

  function reportError(box) {
    write.disabled = false;
    write.textContent = write.dataset.previous || write.textContent;
    live.textContent = box.querySelector("strong")?.textContent || box.textContent.trim();
    box.tabIndex = -1;
    box.focus();
  }

  document.addEventListener("htmx:beforeSwap", event => {
    const {target, xhr} = event.detail;
    if (target === job && xhr.status >= 400) event.detail.shouldSwap = true;
  });

  document.addEventListener("htmx:afterRequest", event => {
    const {elt, xhr, successful} = event.detail;
    if (elt === write && !xhr.status) {
      job.textContent = "Connection lost.";
      reportError(job);
    }
    const save = saves.get(elt);
    if (!save || xhr !== save.xhr) return;
    saves.delete(elt);
    const editor = elt.closest("[data-journal-editor]");
    const status = editor.querySelector("[role=status]");
    if (!successful) {
      const error = new DOMParser().parseFromString(xhr.responseText || "", "text/html");
      status.textContent = "Not saved: " + (error.querySelector("strong")?.textContent ||
        "Connection lost; your text is still here.");
      delete editor.dataset.closeAfterSave;
      return;
    }
    elt.defaultValue = save.text;
    editor.toggleAttribute("data-dirty", elt.value !== save.text);
    updateAnchor();
    if ("closeAfterSave" in editor.dataset) {
      if (editor.hasAttribute("data-dirty")) htmx.trigger(elt, "blur");
      else editor.querySelector("[data-editor-done]").click();
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) return;
    for (const field of document.querySelectorAll("[data-dirty] textarea")) {
      fetch(field.getAttribute("hx-put"), {
        method: "PUT", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: field.value}), keepalive: true
      }).catch(() => {});
    }
  });

  function closePanel(panel) {
    const opener = openers.get(panel);
    panel.replaceChildren();
    if (opener) {
      opener.setAttribute("aria-expanded", "false");
      opener.focus();
    }
  }

  document.addEventListener("click", event => {
    const close = event.target.closest("[data-close-citation]");
    if (close) closePanel(close.closest("aside").parentElement);
    if (event.target.closest('a[href="#journal-trace"]')) document.querySelector("#journal-trace").open = true;
  });
  document.addEventListener("keydown", event => {
    const panel = event.target.closest(".citation-panel");
    if (panel && event.key === "Escape") closePanel(panel.parentElement);
  });

  document.addEventListener("htmx:afterSwap", event => {
    const template = job.querySelector("template[data-journal-result]");
    if (template) return showDraft(template);
    const error = job.querySelector("[role=alert]");
    if (error && job.contains(event.target)) return reportError(error);
    const notice = job.querySelector("[data-journal-notice]");
    if (notice) {
      live.textContent = notice.textContent;
      job.replaceChildren();
      write.disabled = false;
      write.textContent = write.dataset.previous;
      write.focus();
    }
    const panel = event.target;
    if (openers.has(panel)) {
      for (const cite of panel.parentElement.querySelectorAll("button.cite")) {
        cite.setAttribute("aria-expanded", String(cite === openers.get(panel)));
      }
      panel.querySelector("[data-close-citation]")?.focus();
    }
    if (panel.matches("[data-journal-editor]")) {
      // CHANGED [PROMPT #36]: review fix, caret at the end of the text.
      const area = panel.querySelector("textarea");
      area.focus();
      area.setSelectionRange(area.value.length, area.value.length);
    }
    else if (panel.matches('section[id^="p-"]')) panel.querySelector('[data-testid^="edit-"]')?.focus();
    updateAnchor();
  });
})();
