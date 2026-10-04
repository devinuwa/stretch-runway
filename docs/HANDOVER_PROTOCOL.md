# HANDOVER_PROTOCOL — real-user validation

Purpose: find out honestly whether Stretch speaks to the problem he described, not to collect praise. He has consented to his reaction being used in the write-up. His private numbers stay private.

## 1. Rules

1. **Do not script his reaction.** You may give him a task; you may not tell him what to think, and you must not ask leading questions ("isn't that helpful?").
2. **Record what he actually says and does**, including confusion, silence, criticism and "I wouldn't use it". Negative findings go in the article too.
3. **Never claim the tool "solved" his situation.** The strongest honest claims are limited to what he said ("he said ...", "he asked ...").
4. His numbers: he chooses between **sample data** and **his own numbers**. If his own: run with `STRETCH_HANDOVER=1` (in-memory, metadata-only traces, "Session mode" banner), do not screen-record, do not screenshot, do not paste anything into an agent. Clear the session at the end.
5. Verbatim quotes only, lightly trimmed for length with `[...]`, never reworded. Ask permission again for any quote that mentions his family, amounts or name. Anonymise by default unless he says otherwise.

## 2. Setup (2 minutes)

- `STRETCH_HANDOVER=1`, Ollama running, laptop on mains power, other heavy apps closed.
- Start screen -> "Use sample data" or "Enter my own numbers" (his choice).
- Tell him: "Try it however you like. Tell me what you're thinking out loud. Nothing here is saved."
- Keep a notes file at `handover/private/NOTES.md` (**gitignored**). Timestamp entries.

## 3. Tasks (give them neutrally, one at a time)

1. "Put in your situation however you'd normally describe it." (observe: does he type, struggle, ask what to write)
2. "Look at what it understood and fix anything that's wrong." (observe the confirmation card)
3. "Ask it a question you'd actually want to know about your money." (note the exact question, even if it fails)
4. "Now ask what happens if the next money comes late and smaller." (the one fixed task; he may phrase it his own way)

## 4. After the tasks: open questions (ask in this order, say nothing else, then stay quiet)

1. "What did you take from that result?"
2. "Was anything confusing?"
3. "Was there a question you wanted to ask that it couldn't answer?"
4. "Earlier you told me about running low and not knowing when the next money arrives. How does this relate to that, if at all?"
5. "Would you open this again? Why or why not?"
6. "What's missing?"

## 5. Evidence capture template (copy to `handover/private/NOTES.md`)

```
Date/time (WAT):            Mode: sample | own numbers      LLM state: up | down
Duration of session:
Task 1 - what he did / said (verbatim):
Task 2 - confirmation card: what he corrected / didn't understand:
Task 3 - his own question (verbatim) and what the tool did:
Task 4 - result shown; what he said (verbatim):
Confusions observed (with timestamps):
Failures observed (model errors, latency, wrong plans):
Answers to the open questions (verbatim):
Anything he asked for that does not exist:
Consent for quotes: yes / no / partially (note exactly which):
Anonymise? yes / no
Observer's own interpretation (kept separate from his words):
```

## 6. What goes public

After the session, produce `handover/REACTION.md` (this file **is** committed) containing only: that a real handover happened and when, whether sample or his own data was used (without numbers), his approved verbatim quotes, observed confusions and failures, and what was changed or left as future work. No amounts, no balances, no dates tied to his real money. The article may report only what is in `REACTION.md`. If no handover happens before the cutoff, `REACTION.md` says exactly that, and the article does not imply otherwise.

## 7. Cleanup

Clear session in the UI; confirm `data/` is unchanged; delete any scratch recordings of his own numbers; verify `git status` shows nothing from `handover/private/`.
