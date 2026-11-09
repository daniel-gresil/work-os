---
name: ado-spec-reference-existing-code
description: ADO card specs that mirror an existing feature name the reference file and function in the other repo
metadata:
  node_type: memory
  type: feedback
  originSessionId: df722c2a-edf0-44bc-b6cf-5ebe964718dc
  modified: 2026-10-09T05:20:38.046Z
---

When an ADO card asks for a feature that mirrors something already built in another Lave repo, the
card names the reference file and function (for example `PoToVendorEmail.js` / `poToVendorForm` in
9025_WIP) so the developer can read it instead of reverse-engineering the behaviour.

**Why:** on 2026-10-09, while drafting the SPD Dashboard "PO preview" card, Dan said: "remember you're
writing the spec for the ADO, so you can reference the function name in the 9025. The developer can
look at the 9025 function for reference if they want to."
**How to apply:** while fact-finding for a card, note the file and function names of the pattern being
copied and put them in the description under a "Reference" line. Related: [[analysis-before-changes]].

When the reference lives in another repo, say on the card that the code is copied and that repo is not modified. Dan asked whether the 9149 image task was "related to 9025" because the card cited 9025 functions (2026-11-08).
