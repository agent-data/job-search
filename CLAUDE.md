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

## Never use an idiom to state a simple fact

No idiom, figure of speech, or literary phrase standing in for a plain statement — however common or
obvious the phrase seems. If you mean "the same error showed up in two different places", write that.
Do not write "the same mistake at two removes".

The clear, unambiguous version is always better. There is no case where a reader benefits from
decoding a figure of speech to reach a fact you could have stated directly. Being understood on the
first reading is the whole goal; nothing is traded away by writing plainly.

Personification is the same failure: a gate does not see, a contract does not know, a test does not
care. Say what the code does.

All three of these were written during this project:

| Written | Should have been |
|---|---|
| "the same mistake at two removes" | the same error showed up in two different places |
| "gates that can see the defect" | gates that actually catch these bugs |
| "the pack has an ownership metaphor, not a boundary" | nothing in the pack stops one skill doing another skill's work |

## Never state a measurable fact without measuring it

If a number, a count, a size, or a "this file contains X" claim can be settled with `grep`, `wc`, or a
one-line script, run it before writing the sentence. Do not estimate, recall, or infer.

This applies inside plans and design docs, not only in chat. Eleven blocking defects in the 2026-07-22
audit-remediation plan came from sentences like "the invariants are already in `run-lifecycle.md`" (13
of the 14 were not), "the two files over 5,000 words" (there are four), and "nineteen substrings"
(there are eighteen). Each was one command away from being caught, and each was written as settled
fact. The full set is in `docs/superpowers/reviews/2026-07-22-plan-conflict-sweep.md`.

When you cite a measurement, cite the command that produced it, so a reader can re-run it.
