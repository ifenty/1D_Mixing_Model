# Active lessons

Keep each entry short and independently useful; load detailed evidence when its trigger applies.

- [LL-001] Footer fields `candidate_signature` and `documentation_review.status` have exact, non-obvious required values (not free text) — read `esx/templates/agent_report_guide.md` before writing a report, don't infer from field names.
  Trigger: Dispatching or resuming Bob/Richard for a `scientific_change` review.
- [LL-002] A completed review not referenced in `workflow_records.py selections`'s own output is not "correctable" later — it is discarded, and its work (including any independent check already run) must be redone from scratch under a new identity.
  Trigger: Before building any `--select` file, or before deciding to redispatch a role "to be safe."
- [LL-003] The scientific-signature-drift gate forces a full Bob+Richard reclassification round for any issue left open across another issue's `scientific_change` closure, even when the open issue's own candidate is unchanged.
  Trigger: Starting an issue expected to stay open for a while (e.g. waiting on a long capture/build) — default to `kind=scientific_change` from the first `--prepare` to avoid the reclassification round later.
- [LL-004] Fixing a documentation/workflow-amendment staleness issue at the review-packet level does not propagate to `issue-done.json` or `closed_issues.md` automatically — each must be independently re-applied, or a reviewer will catch the mismatch and return `APPROVE_WITH_FIXES` for Arch's own bookkeeping, not the agent's substantive work.
  Trigger: Any time a `harness_change` issue is amended to `scientific_change` mid-closeout (e.g. after discovering a new test file triggers the tests-changed drift check) — update `issue-done.json`'s `workflow`/`workflow_amendment`/`maintenance.documentation` and rewrite any already-written `closed_issues.md` entry in the same pass as resealing the review packet's own documentation reference, not as a separate later step.
