# SPD Mfg - Dashboard: domain glossary

Terms as used on the **SPD Mfg - Dashboard** sheet and the code that reads it. Column S-ids are the
dashboard's own row-1 identifiers; numeric ids in row 2 point at the matching Lave column.

## Downsized (S1264)

A job's sizing mode, chosen by SPD when the job is entered. One of four values:

| Value | Meaning |
|---|---|
| **No** | Men's regular fit. Standard bucket codes. |
| **Yes-M** | Men's oversized fit (Boxy, OVRSZD bodies). Men's downsized bucket codes. |
| **Yes-W** | Women's sizing. Women's bucket codes. |
| **TBD** | Not decided yet. No bucket codes. |

It drives the **Mill Blank Order Size Codes** (S1057 to S1067): the bucket code each label size orders
from the mill. The three code sets are defined by the formulas in those columns and nothing else.
The word "downsized" is historical; the value also carries gender, which is why Yes is split into W and M.

On WIP Lavanderia the same fact is column 6184 "Downsize", which only knows Yes or No. Yes-W and Yes-M
both map to Yes; TBD leaves the Lavanderia value alone.

## Bucket code

A mill blank size expressed as S1 (XS) through S10 (6X). S0 means no blank is ordered for that label size.
1X is a label size with no bucket of its own: it shares S5 with XL for women's jobs and gets S0 for men's.

## Production Qty - Print Size (S1015 to S1019, S1055, S1020 to S1024)

Units to print per label size, XS to 6X. 1X lives in S1055, out of numeric order. The "standard"
bucket codes under Downsized = No follow this block one to one.

## Sizing Map tab

A label size to mill blank size table by Mode and Gender, read by the laveapparel.com/spd order form
only. Not used by the dashboard formulas and not in service as of 2026-09-22.

## PO Preview

The email Customer Service sends for a new job on WIP Planned before the formal PO is issued: a "New Job"
heading, the ship date, and the job row as a table. Sent from the dashboard by the "Send PO Preview" menu
(spec: ADO card under Epic 351, 2026-10-09).
_Avoid_: PO email, job preview, new job email

## Email Sent (S1271)

The date the PO Preview for that row went out. Blank means not sent yet; Customer Service filters on it to
find jobs still waiting. Stamped by the send, not typed.

## Distribution list (Lists tab)

The To and Cc addresses a dashboard email goes to, kept on the Lists tab in a block laid out like 9025's
EmailGroups tab (Group, To, Cc). Read at send time; editing the sheet changes recipients, not the code.
_Avoid_: email group, recipients list
