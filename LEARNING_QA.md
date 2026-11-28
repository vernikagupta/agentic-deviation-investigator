# Learning Q&A

Learning notes from building this project. Newest at the bottom.

---

## AWS

### What is IAM Identity Center, and what was its purpose for us?
**What it is:** the AWS service for managing who can sign in to AWS and what they can do, in one place.
- Users and groups are created once, or connected to the company's login system (for example Microsoft
  Entra ID or Okta).
- People sign in at one portal page, then pick the AWS account and access level.
- Access levels are **permission sets** (for example "ReadOnly", "Developer"). Behind the scenes each
  becomes an IAM role in each account.
- Every sign-in (console or CLI, `aws configure sso`) gives **temporary credentials** that expire after a
  few hours.

**Why companies use it**
- Many AWS accounts (dev, test, prod, per team): one login for all.
- Someone leaves: disable them once, access to every account is gone.
- No long-lived access keys on laptops (the most common cause of leaks).

**Why it needs AWS Organizations:** it gives access across multiple accounts, and a group of accounts is
managed through an organization.

**Its purpose for us:** only CLI credentials that expire on their own, instead of access keys on the laptop.
- We skipped it: creating an organization ends the free plan and expires the free tier credits immediately.
- For one person with one account, `aws login` gives the same benefit without an organization.

**Interview line:** "In a company I'd use IAM Identity Center with SSO and permission sets across accounts.
For my single-account project I used `aws login` for short-lived CLI credentials, for the same reason:
no long-lived keys."

### So I create an organization in Identity Center, add groups and roles, and people get access to all environments?
Close, but three corrections:
1. **The organization is created in AWS Organizations, not in Identity Center.** Organizations groups several
   AWS accounts (for example dev, test, prod) under one management account. Identity Center sits on top and
   manages who can sign in to them.
2. **In Identity Center you create permission sets, not roles.** You create users and groups, and permission
   sets (access levels like ReadOnly, Developer, Admin). When a permission set is assigned to an account, AWS
   creates the matching IAM role there automatically.
3. **People get only what is assigned, not all environments.** Each assignment = who (user or group) +
   which account + which permission set.

   | Group | Dev account | Prod account |
   |---|---|---|
   | Data engineers | Developer | ReadOnly |
   | QA | ReadOnly | ReadOnly |
   | Platform admins | Admin | Admin |

   No assignment for prod = no access to prod. This is **least privilege**.

**Corrected sentence:** "In AWS Organizations I group my accounts (dev, test, prod). In IAM Identity Center I
create users, groups and permission sets, then assign each group a permission set in specific accounts.
People get only the access that is assigned."

### What is the `aws login` session? Does it expire if I close the terminal? How do I check it?
**What it is:** `aws login` gives the CLI temporary credentials (a key that works for a limited time),
saved in a cache folder under the user's `.aws` folder. Not stored in the terminal.

**Closing the terminal:** does not end it. New terminals, VS Code and reboots keep working until expiry.

**How long:** the CLI refreshes the credentials automatically for up to 12 hours after login. Then run
`aws login` again.

**Check if active:** `aws sts get-caller-identity` (free, changes nothing).
- Active: prints user ID, account, ARN.
- Expired: error saying credentials/token expired or asking to log in.

**End early:** `aws logout` deletes the cached credentials. Do it at the end of the day.

**Security:** while active, anyone using my Windows account can run AWS commands as me, so lock the laptop.
Still much safer than access keys, which never expire on their own.

**For later:** some tools (possibly Terraform, boto3) may not read `aws login` credentials directly yet.
Check when setting up Terraform; there is a standard workaround.

---

## Data

### What time zone are the historian timestamps in?
| File | Time column | Time zone | How to tell |
|---|---|---|---|
| `assembly_summary.csv` before 1 Oct 2025 | `FIT_Cycle_Window` ("start - end") | Not stated | No marker (deliberate ambiguity) |
| `assembly_summary.csv` from 1 Oct 2025 | `Cycle_Start_UTC`, `Cycle_End_UTC` | UTC | Column name, value ends in `Z` |
| `post_use_tests.csv` | `Test_End_UTC` | UTC | Column name, `Z` |
| `test_signals.csv` | `timestamp` | UTC | Ends in `Z` |
| `cart_alarms.csv` | `alarm_time` | UTC | Ends in `Z` |

- **`Z`** at the end of an ISO 8601 time means UTC (zero offset).
- **No marker: never guess.**
  1. Ask the system owner (automation team for the historian) and record the answer in the data docs.
  2. Prove it with data: find the same test in a UTC source (`test_signals.csv` for that cart). If the signal
     times fall inside the summary window as written, it is UTC. A fixed shift (e.g. 5:30 h) means local time.
- Other systems differ: CMMS is local time (IST, UTC+5:30); ERP and QC give local dates only.

### What does `Z` mean in a timestamp?
- `Z` at the end = UTC ("Zulu"). `2025-03-04T21:41:10Z` = 21:41:10 UTC.
- Same moment with offsets: `...T21:41:10+00:00` (UTC) or `2025-03-05T03:11:10+05:30` (IST).
- No `Z` and no offset (e.g. `2025-03-04 21:41:10`) = time zone unknown.
- **Pipeline rule:** in silver, convert every timestamp to UTC and store it time-zone-aware. A timestamp
  without a time zone never gets past silver.

### The assembly summary window is 5-6 h, but a batch takes ~1.5 days. What does the window represent?
- **One filter assembly's preparation:** from build start to PUPSIT end (build, wet, Pre-IT, autoclave,
  re-wet, PUPSIT).
- **Not included:** filling (18-28 h), post-use test (separate file `post_use_tests.csv`, arrives later),
  changeover.

```
Batch (about 1.5 days including changeover)
|-- Cart 1 assembly: build ... PUPSIT      (5-6.5 h)   <- one summary row
|-- Cart 2 assembly: build ... PUPSIT      (5-6.5 h)   <- one summary row, overlaps cart 1
|-------------------- Filling (18-28 h) --------------------|
                                                     Post-use test (both carts)
                                                     Changeover (5-10 h)
```

- Normal batch = 2 summary rows (one per cart), overlapping, near the start of the batch.
- Failed assembly = 3+ rows (the replacement gets its own row with a later window).
- Batch start/end come from MES. Matching = relating the short assembly window to the long MES window.

### Do we use both carts for every batch?
Yes, every batch uses both carts on its line.
- **Cart 1 (formulation):** filters the solution during transfer from the preparation vessel; removes most
  bacteria early.
- **Cart 2 (final fill):** final sterilizing filter right before the filler; guarantees sterility.
- Two filters in series is common practice: if one has a problem, the other still protects the product.

**In the data**
- Each cart has its own assembly, Pre-IT, PUPSIT and post-use test → 2 summary rows per normal batch.
- Carts never move between lines (line A: A1, A2; line B: B1, B2; line C: C1, C2).
- Both assemblies of a batch share the same autoclave cycle and often the same filter lot.

**Why it helps investigations**
- The two carts of one batch share lot, autoclave cycle, crew and room. Only the cart differs.
- One cart rises, the other stays normal on the same batches → probably the cart (seal, sensor).
- Both rise together → look at what they share: lot, autoclave cycle, crew.

### What exactly is a cart, and why two carts?
**The cart is the test machine. The filter is the thing being tested.**

**What a cart is:** a stainless-steel trolley with an automated integrity tester:
- gas connection (compressed air or nitrogen),
- pressure regulator and valves (pressurize the filter to 2500 mbar),
- pressure sensor (and flow measurement),
- **Correction (from web search):** automated testers usually do not measure flow on the outlet side. They
  pressurize the inlet side, close it off, measure how fast the inlet pressure drops (pressure decay), and
  calculate the diffusion flow from that. Reason: nothing touches the sterile outlet side. A leak in the
  cart makes the inlet pressure drop faster, so it is counted as filter flow. Temperature changes also
  affect the result. Our synthetic data simplifies this (reports a flow value; pressure falls faster on a
  leak).
- For photos, search "filter integrity test trolley" or "PUPSIT trolley" (supplier pages; keep supplier
  names out of the repo).

### Is the flow value at StepIndex 1300 the right value?
Yes. The flow at **StepIndex 1300** is the valid result of a test attempt.

**Why 1300**
- 1300 = "test complete". The cart has finished measuring; the value stored here is the final result.
- Before 1300 the value is still changing:
  - 200-400: pressurizing, flow high and falling.
  - 500-600: stabilization and checks.
  - 1200: measuring, flow still settling (incomplete wetting shows it starting high and falling here).
- After 1300: 1400 releases pressure, 1500 cleans up. Flow values there mean nothing.
- 9999 = aborted. No valid result; the cart reports 0.
- SOP-FIT-001: "The final diffusion flow is valid at StepIndex 1300."

**Check it yourself:** for the last attempt of a test, the flow at 1300 should match the summary value
(`PreIT_Flow` / `PUPSIT_Flow`) approximately (a few hundredths difference from signal noise). If it matches,
the right rows were found.

---

## Data exploration

### How do I know what to check next when exploring a new table?
Don't memorise steps like "split the tag". Ask the same 7 questions of every table, in order. The next
step comes out of the answers.

1. **What is one row?** Look at `head()`. What makes a row unique (the key)?
   Signals: timestamp + tag.
2. **Does each column hold one fact, or several packed together?** If a column hides two facts, you
   cannot filter or group by either one until you split it.
3. **What are the distinct values in each text column?** `value_counts()`, `nunique()`. Shows messy
   variants (e.g. cart name written 4 ways).
4. **What are the ranges of each number column, per group?** `describe()` grouped by category. Shows
   units, outliers, impossible values.
5. **Time:** first and last date, gaps, where the format changes, late rows, duplicates on the key.
6. **What does the project need from this table?** Work backwards. E.g. later we want "the flow result for
   each test on each cart". Which columns does that need?
7. **Compare with `data/README.md`.** Did I find everything it lists? Anything it does not list?

**Example: how "split the tag" comes out of these questions**
- Q3: `value_counts()` on `tag` shows 36 values like `FITC_A1.DiffFlow`, `FITC_A1.Pressure`.
- Q2: each tag holds two facts: which cart (`FITC_A1`) and which signal (`DiffFlow`).
- Q6: we need results per cart and per signal. Packed into one column, you cannot filter "all flow
  readings for cart A1".
- So split it. Same reasoning as `FIT_Cycle_Window` in table 1 (start and end in one string).

**How to use it:** put the 7 questions in the top markdown cell of each table notebook and work through
them in order.
