# CLAUDE.md

Coding agents working on this repo: read **[AGENTS.md](AGENTS.md)** — the entry-point map. It
points to the architecture, the agent-first core beliefs, the design/exec plans, and the runtime
single source of truth in `shared/references/`.

## Write concretely — never swap a concrete thing for an abstraction

Applies to **all** generated text: chat replies, docs, plans, code comments, docstrings, commit
messages, and every word shipped inside a skill or reference.

**Name the thing itself, not the concept it belongs to.** Say "call the API" or "use the documented
endpoint" — not "call the contract". Say "the `runs/` folder holds more than one kind of file" — not
"a broad glob is not a run-record definition".

**Use specialized terminology only where it adds necessary precision**, and pair it with the verbs
practitioners actually use with it. You call an endpoint, read a file, run a test, append an event.
You do not call a contract or admit a sidecar.

**Before finalizing any wording, check every technical phrase for natural collocation:** would an
experienced practitioner actually say it this way? Rewrite anything that is merely interpretable, or
technically defensible but unusually compressed, clever, formal, or academic.

Worked example — this line shipped in this repo and is the failure mode:

> A broad `runs/*.json` glob is not a run-record definition: it would admit the binding sidecar.

It takes three readings to extract one simple fact. Say it plainly instead:

> The `runs/` folder holds several kinds of file, not just run records. To find a run record, match
> the filename against the run-id timestamp format — don't glob `runs/*.json`, because that also
> picks up `detail-model-binding.json`, which isn't a run.

If a sentence needs a second reading to yield its point, rewrite it.
